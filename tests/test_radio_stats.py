"""Host-only checks using synthetic, non-identifying Wi-Fi metadata."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


APP = Path(__file__).resolve().parents[1] / "badge" / "apps" / "radio_stats"
SPEC = importlib.util.spec_from_file_location("radio_core", APP / "radio_core.py")
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)


def observation(channel, rssi):
    return (None, None, channel, rssi, None, None)


class AggregateTests(unittest.TestCase):
    def test_exact_bucket_boundaries_and_channels(self):
        rows = [observation(channel, rssi) for channel, rssi in (
            (1, -59), (1, -60), (6, -61), (6, -75), (14, -76), (14, -126))]
        stats = core.aggregate(rows)
        self.assertEqual(rows, [])
        self.assertEqual(stats["total"], 6)
        self.assertEqual(stats["signals"], [2, 2, 2])
        self.assertEqual(stats["channels"], [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 2])
        self.assertEqual(stats["strongest"], -59)
        self.assertEqual(stats["unknown_channel"], 0)
        self.assertEqual(stats["unknown_signal"], 0)

    def test_empty_and_unknown_measurements(self):
        self.assertEqual(core.aggregate([])["total"], 0)
        self.assertIsNone(core.aggregate([])["strongest"])
        stats = core.aggregate([observation(0, 0), observation(36, -127),
                                observation(-1, -128), observation(6, 1)])
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["unknown_channel"], 3)
        self.assertEqual(stats["unknown_signal"], 4)
        self.assertEqual(stats["signals"], [0, 0, 0])
        self.assertIsNone(stats["strongest"])

    def test_identifying_fields_are_not_accessed(self):
        class GuardedRow(tuple):
            def __getitem__(self, index):
                if index not in (2, 3):
                    raise AssertionError("Identifier field accessed")
                return super().__getitem__(index)

        self.assertEqual(core.aggregate([GuardedRow(observation(1, -60))])["total"], 1)

    def test_invalid_results_are_explicit_errors(self):
        for row in (None, (), (None, None, 1), observation("1", -60),
                    observation(1, None), observation(True, -60), observation(1, False)):
            with self.subTest(row=row), self.assertRaises(core.ScanError):
                core.aggregate([row])


class RadioTests(unittest.TestCase):
    def setUp(self):
        self.station = Mock()
        self.ap = Mock()
        self.station.active.return_value = False
        self.ap.active.return_value = False
        self.station.scan.return_value = [observation(6, -55)]
        self.network = types.SimpleNamespace(STA_IF=0, AP_IF=1)
        self.network.WLAN = Mock(side_effect=lambda interface:
                                 (self.station, self.ap)[interface])

    def test_passive_only_and_radio_disabled_after_success(self):
        stats = core.passive_snapshot(self.network)
        self.assertEqual(stats["total"], 1)
        self.station.scan.assert_called_once_with(passive=True)
        self.assertEqual(self.station.active.call_args_list,
                         [unittest.mock.call(), unittest.mock.call(True), unittest.mock.call(False)])
        self.station.connect.assert_not_called()
        self.station.disconnect.assert_not_called()
        self.ap.active.assert_called_once_with()

    def test_existing_station_or_ap_is_never_changed(self):
        for interface in (self.station, self.ap):
            self.station.reset_mock()
            self.ap.reset_mock()
            self.station.active.return_value = interface is self.station
            self.ap.active.return_value = interface is self.ap
            with self.assertRaisesRegex(core.ScanError, "already in use"):
                core.passive_snapshot(self.network)
            self.station.scan.assert_not_called()
            self.assertTrue(all(not call.args for call in self.station.active.call_args_list))
            self.assertTrue(all(not call.args for call in self.ap.active.call_args_list))

    def test_unsupported_passive_keyword_has_no_fallback(self):
        self.station.scan.side_effect = TypeError("keyword unsupported")
        with self.assertRaisesRegex(core.ScanError, "Passive scan unsupported"):
            core.passive_snapshot(self.network)
        self.station.scan.assert_called_once_with(passive=True)
        self.station.active.assert_called_with(False)

    def test_failures_always_release_owned_station(self):
        for failure in (OSError("sensitive driver detail"), core.ScanError("Invalid scan result")):
            self.station.reset_mock()
            self.station.scan.side_effect = failure
            with self.assertRaises(core.ScanError) as raised:
                core.passive_snapshot(self.network)
            self.assertNotIn("sensitive", str(raised.exception))
            self.station.active.assert_called_with(False)

    def test_enable_and_cleanup_failures_are_reported(self):
        for effects, message in (([False, OSError("enable"), None], "Radio operation failed"),
                                 ([False, None, OSError("disable")], "Radio shutdown failed")):
            self.station.active.side_effect = effects
            with self.assertRaisesRegex(core.ScanError, message):
                core.passive_snapshot(self.network)
            self.station.active.assert_called_with(False)

    def test_missing_api_does_not_activate_radio(self):
        with self.assertRaisesRegex(core.ScanError, "Wi-Fi API unavailable"):
            core.passive_snapshot(types.SimpleNamespace())

    def test_bad_driver_results_still_disable_radio(self):
        self.station.scan.return_value = [observation("invalid", -60)]
        with self.assertRaisesRegex(core.ScanError, "Invalid scan measurement"):
            core.passive_snapshot(self.network)
        self.station.active.assert_called_with(False)


class UITests(unittest.TestCase):
    def setUp(self):
        self.keys = set()
        self.screen = Mock(width=320, height=240)
        self.badge = Mock(ticks_delta=16)
        self.badge.pressed.side_effect = lambda button: button in self.keys
        self.namespace = {
            "badge": self.badge, "screen": self.screen, "image": Mock(),
            "font": Mock(), "color": Mock(), "shape": Mock(), "run": Mock(),
            "HIRES": 1, "VSYNC": 2,
            "BUTTON_SELECT": "select", "BUTTON_LEFT": "left", "BUTTON_RIGHT": "right",
        }
        source = (APP / "__init__.py").read_text()
        with patch.dict(sys.modules, {"radio_core": core, "network": None}), \
                patch("os.chdir"), patch.object(sys, "path", list(sys.path)):
            exec(compile(source, str(APP / "__init__.py"), "exec"), self.namespace)
        self.now = 0
        self.namespace["time"] = types.SimpleNamespace(
            ticks_ms=lambda: self.now,
            ticks_diff=lambda a, b: (a - b + (1 << 29)) % (1 << 30) - (1 << 29))

    def update(self, *buttons):
        self.keys = set(buttons)
        self.screen.reset_mock()
        self.namespace["update"]()
        return [call.args[0] for call in self.screen.text.call_args_list]

    def test_no_startup_scan_and_unavailable_error_on_request(self):
        scan = Mock()
        self.namespace["passive_snapshot"] = scan
        self.assertIn("Select takes one passive snapshot.", self.update())
        self.assertIn("Listening for access points...", self.update("select"))
        scan.assert_not_called()
        self.assertIn("Wi-Fi API unavailable", self.update())
        scan.assert_not_called()
        self.assertFalse(self.namespace["pending"])
        self.namespace["run"].assert_called_once_with(self.namespace["update"])

    def test_snapshot_pages_age_and_retry_clear_stale_data(self):
        self.namespace["network"] = Mock()
        scan = Mock(return_value=core.aggregate([observation(6, -60)]))
        self.namespace["passive_snapshot"] = scan
        self.update("select")
        self.assertIn("1 APs observed / 0s ago", self.update())
        scan.assert_called_once()
        self.now += 1000
        self.assertIn("1 APs observed / 1s ago", self.update("right"))
        self.assertIn("Strongest: -60 dBm",
                      [call.args[0] for call in self.screen.text.call_args_list])
        self.assertIn("Observed APs by channel", self.update("left"))
        scan.side_effect = core.ScanError("Radio operation failed")
        self.update("select")
        self.assertIsNone(self.namespace["stats"])
        self.assertIn("Radio operation failed", self.update())

    def test_zero_snapshot_is_not_an_error(self):
        self.namespace["network"] = Mock()
        self.namespace["passive_snapshot"] = Mock(return_value=core.aggregate([]))
        self.update("select")
        self.assertIn("0 APs observed / 0s ago", self.update())
        self.assertIn("Strongest: --", self.update("right"))
        self.assertIsNone(self.namespace["error"])
        for _ in range(10):
            self.update()
        self.namespace["passive_snapshot"].assert_called_once()

    def test_cleanup_error_warns_that_radio_may_be_enabled(self):
        self.namespace["network"] = Mock()
        self.namespace["passive_snapshot"] = Mock(
            side_effect=core.ScanError("Radio shutdown failed"))
        self.update("select")
        labels = self.update()
        self.assertIn("Radio may still be enabled.", labels)
        self.assertIn("Restart badge before retrying.", labels)

    def test_age_starts_after_blocking_scan_and_handles_tick_wrap(self):
        self.namespace["network"] = Mock()
        self.now = (1 << 30) - 100

        def delayed_scan(network):
            self.now = (self.now + 10000) % (1 << 30)
            return core.aggregate([])

        self.namespace["passive_snapshot"] = delayed_scan
        self.update("select")
        self.assertIn("0 APs observed / 0s ago", self.update())
        self.now += 1000
        self.assertIn("0 APs observed / 1s ago", self.update())


if __name__ == "__main__":
    unittest.main()
