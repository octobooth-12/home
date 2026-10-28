import json
import sys
import types
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "badge" / "apps" / "bm83_remote"
sys.path.insert(0, str(APP))

import artwork
import models
import protocol
from transport import Remote


KEY = bytes(range(32))
KEY_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
HELLO = (b'BMW1.096f38d323e01956a7bc160938326c97.'
         b'{"v":1,"type":"hello","nonce":"0011223344556677"}')
WELCOME = (b'BMW1.c2dab9f96a0180159c08a0e79172335a.'
           b'{"v":1,"type":"welcome","nonce":"0011223344556677",'
           b'"unit":"a1b2c3d4","client":1}')
COMMAND = (b'BMW1.5387ab92ebeffd1b35acf87b66a761ee.'
           b'{"v":1,"type":"cmd","unit":"a1b2c3d4","client":1,'
           b'"seq":1,"token":"BT_PLAY"}')


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.incoming = []

    def setblocking(self, value):
        pass

    def sendto(self, packet, peer):
        self.sent.append(packet)
        return len(packet)

    def recvfrom(self, size):
        if self.incoming:
            return self.incoming.pop(0), ("192.168.1.10", 8767)
        raise OSError(11)

    def close(self):
        pass


def np_state():
    return {
        "power_on": True, "connected": True, "aux": False,
        "clock_advancing": True, "play_status": 1, "eq_index": 1,
        "duration_ms": 180000, "position_ms": 5000, "position_age_ms": 0,
        "title": "Title", "artist": "Artist", "album": "Album", "eq": "ROCK",
    }


def response(remote, seq, token):
    return protocol.encode(KEY, {
        "v": 1, "type": "state", "unit": remote.unit, "client": remote.client,
        "seq": seq, "dup": False, "np": np_state(), "ble": None,
    }, maximum=1200)


class ProtocolTests(unittest.TestCase):
    def test_contract_vectors(self):
        hello = {"v": 1, "type": "hello", "nonce": "0011223344556677"}
        welcome = {"v": 1, "type": "welcome", "nonce": "0011223344556677",
                   "unit": "a1b2c3d4", "client": 1}
        command = {"v": 1, "type": "cmd", "unit": "a1b2c3d4",
                   "client": 1, "seq": 1, "token": "BT_PLAY"}
        self.assertEqual(protocol.key_bytes(KEY_HEX), KEY)
        self.assertEqual(protocol.encode(KEY, hello), HELLO)
        self.assertEqual(protocol.encode(KEY, welcome), WELCOME)
        self.assertEqual(protocol.encode(KEY, command), COMMAND)
        self.assertEqual(protocol.decode(KEY, COMMAND), command)

    def test_authentication_and_size_limits(self):
        corrupted = bytearray(COMMAND)
        corrupted[10] ^= 1
        self.assertIsNone(protocol.decode(KEY, bytes(corrupted)))
        self.assertIsNone(protocol.decode(KEY, COMMAND + b"x" * 1200))
        with self.assertRaises(ValueError):
            protocol.encode(KEY, {"v": 1, "type": "cmd", "data": "x" * 300})


class PlaybackTests(unittest.TestCase):
    def test_freshness_source_age_and_clock_projection(self):
        playback = models.Playback()
        self.assertTrue(playback.accept(np_state(), 1000))
        self.assertEqual(playback.position(1500), 5500)
        self.assertIsNone(playback.position(7000))
        self.assertFalse(playback.fresh(7000))

    def test_paused_clock_is_frozen_and_stale_status_expires(self):
        playback = models.Playback()
        state = np_state()
        state.update(play_status=2, clock_advancing=True, position_ms=20000)
        playback.accept(state, 100)
        state = dict(state, position_ms=25000, position_age_ms=100)
        playback.accept(state, 200)
        self.assertEqual(playback.position(500), 20000)
        self.assertIsNone(playback.position(6200))

    def test_elapsed_wraps_badge_tick_counter(self):
        playback = models.Playback()
        playback.accept(np_state(), 0xffffff00)
        self.assertTrue(playback.fresh(0x00000010))

    def test_wire_char_limit_allows_non_ascii_metadata(self):
        state = np_state()
        state["title"] = "é" * 50
        self.assertTrue(models.valid_np(state))


class SettingsTests(unittest.TestCase):
    def test_ble_expiry_clamps_removed_selection_before_indexing(self):
        old_choices = ["power", "pair", "eq", "erase", "wifi", "ble"]
        new_choices = old_choices[:-1]
        old_index = len(old_choices) - 1
        current_index = models.clamp_setting_index(old_index, len(new_choices))
        self.assertEqual(new_choices[current_index], "wifi")
        self.assertEqual(models.clamp_setting_index(current_index, 0), 0)

class BleTests(unittest.TestCase):
    def status(self, sequence=7, session=1, mode=0, flags=15, error=0,
               req_client=None, req_seq=None):
        return {"session": session, "sequence": sequence, "mode": mode,
                "flags": flags, "error": error, "req_client": req_client,
                "req_seq": req_seq}

    def test_confirm_requires_matching_correlation_pair(self):
        ble = models.BleControl()
        ble.accept(self.status(), 0)
        self.assertTrue(ble.begin(True, 4, 9, 0))
        ble.accept(self.status(sequence=8, mode=2, flags=2,
                               req_client=None, req_seq=None), 100)
        ble.tick(100)
        self.assertEqual(ble.result, "Unconfirmed (superseded)")

    def test_confirm_pause_requires_matching_new_status(self):
        ble = models.BleControl()
        ble.accept(self.status(), 0)
        self.assertTrue(ble.begin(True, 4, 9, 0))
        ble.accept(self.status(sequence=8, mode=2, flags=2,
                               req_client=4, req_seq=9), 100)
        ble.tick(100)
        self.assertEqual(ble.result, "Confirmed")

    def test_failed_and_restarted_requests_are_not_success(self):
        ble = models.BleControl()
        ble.accept(self.status(), 0)
        ble.begin(True, 4, 9, 0)
        ble.accept(self.status(sequence=8, mode=3, flags=2, error=1,
                               req_client=4, req_seq=9), 100)
        ble.tick(100)
        self.assertEqual(ble.result, "Failed")
        ble = models.BleControl()
        ble.accept(self.status(), 0)
        ble.begin(True, 4, 9, 0)
        ble.accept(self.status(sequence=1, session=2, mode=2, flags=2,
                               req_client=4, req_seq=9), 100)
        ble.tick(100)
        self.assertEqual(ble.result, "Unconfirmed (restarted)")


class TransportTests(unittest.TestCase):
    def make_remote(self):
        remote = Remote("192.168.1.10", 8767, KEY)
        remote.socket.close()
        remote.socket = FakeSocket()
        remote.unit, remote.client = "a1b2c3d4", 1
        return remote

    def test_volume_press_release_are_serialized(self):
        remote = self.make_remote()
        remote.volume("BT_VOLUP")
        remote.release_volume()
        remote.step(10)
        sent = [protocol.decode(KEY, packet)["token"] for packet in remote.socket.sent]
        self.assertEqual(sent, ["BT_VOLUP_P"])
        remote.socket.incoming.append(response(remote, 1, "BT_VOLUP_P"))
        remote.step(11)
        sent = [protocol.decode(KEY, packet)["token"] for packet in remote.socket.sent]
        self.assertEqual(sent, ["BT_VOLUP_P", "BT_VOLUP_R"])
        self.assertEqual(protocol.decode(KEY, remote.socket.sent[1])["seq"], 2)

    def test_release_retry_reuses_sequence_and_blocks_poll(self):
        remote = self.make_remote()
        remote.queue_command("BT_VOLDN_R")
        remote.step(0)
        remote.step(150)
        remote.step(300)
        remote.step(450)
        first = protocol.decode(KEY, remote.socket.sent[0])
        self.assertEqual(remote.pending["attempts"], 4)
        remote.step(600)
        self.assertTrue(remote.pending["stalled"])
        remote.step(1599)
        self.assertEqual(len(remote.socket.sent), 4)
        remote.step(1600)
        self.assertEqual(len(remote.socket.sent), 5)
        self.assertTrue(all(protocol.decode(KEY, packet)["seq"] == first["seq"]
                            for packet in remote.socket.sent))
        self.assertIn("no reply", remote.feedback)

    def test_lost_release_reply_recovers_before_queued_action(self):
        remote = self.make_remote()
        remote.queue_command("BT_VOLUP_R")
        remote.queue_command("BT_NEXT")
        remote.step(0)
        first = remote.socket.sent[0]
        for now in (150, 300, 450, 600, 1600):
            remote.step(now)
        self.assertTrue(remote.pending["stalled"])
        self.assertEqual(len(remote.socket.sent), 5)
        self.assertTrue(all(packet == first for packet in remote.socket.sent))

        duplicate = protocol.decode(KEY, response(remote, 1, "BT_VOLUP_R"))
        duplicate["dup"] = True
        remote.socket.incoming.append(protocol.encode(KEY, duplicate, maximum=1200))
        remote.step(1601)
        next_command = protocol.decode(KEY, remote.socket.sent[-1])
        self.assertEqual((next_command["token"], next_command["seq"]),
                         ("BT_NEXT", 2))
        self.assertEqual(remote.pending["token"], "BT_NEXT")

    def test_lost_non_idempotent_reply_is_not_replayed(self):
        remote = self.make_remote()
        remote.last_poll = 0
        remote.queue_command("BT_PLAY")
        for now in (0, 150, 300, 450, 600):
            remote.step(now)
        self.assertEqual(len(remote.socket.sent), 4)
        self.assertIsNone(remote.pending)
        self.assertEqual(remote.feedback, "BT_PLAY: no reply")
        remote.step(1000)
        self.assertEqual(protocol.decode(KEY, remote.socket.sent[-1])["token"], "STATUS")

    def test_retry_after_lost_reply_is_deduplicated(self):
        remote = self.make_remote()
        remote.last_poll = 0
        remote.queue_command("BT_PLAY")
        remote.step(10)
        first = remote.socket.sent[0]
        remote.step(160)
        self.assertEqual(remote.socket.sent[1], first)
        reply = protocol.decode(KEY, response(remote, 1, "BT_PLAY"))
        reply["dup"] = True
        remote.socket.incoming.append(protocol.encode(KEY, reply, maximum=1200))
        remote.step(161)
        self.assertIsNone(remote.pending)
        self.assertEqual(remote.feedback, "BT_PLAY: sent (reply)")

    def test_rehello_does_not_replay_uncertain_action(self):
        remote = self.make_remote()
        remote.last_poll = 0
        remote.queue_command("NET_RETRY")
        remote.step(10)
        remote.socket.incoming.append(protocol.encode(KEY, {
            "v": 1, "type": "rehello", "client": 1, "seq": 1,
        }))
        remote.step(11)
        hello = protocol.decode(KEY, remote.socket.sent[-1])
        self.assertEqual(hello["type"], "hello")
        self.assertIn("delivery unconfirmed", remote.feedback)
        remote.socket.incoming.append(protocol.encode(KEY, {
            "v": 1, "type": "welcome", "nonce": hello["nonce"],
            "unit": "a1b2c3d4", "client": 2,
        }))
        remote.step(1012)
        commands = [protocol.decode(KEY, packet) for packet in remote.socket.sent]
        self.assertEqual([m["token"] for m in commands if m["type"] == "cmd"],
                         ["NET_RETRY", "STATUS"])
        self.assertIn("delivery unconfirmed", remote.feedback)

    def test_volume_release_is_retried_after_rehello(self):
        remote = self.make_remote()
        remote.queue_command("BT_VOLUP_R")
        remote.step(10)
        remote.socket.incoming.append(protocol.encode(KEY, {
            "v": 1, "type": "rehello", "client": 1, "seq": 1,
        }))
        remote.step(11)
        hello = protocol.decode(KEY, remote.socket.sent[-1])
        remote.socket.incoming.append(protocol.encode(KEY, {
            "v": 1, "type": "welcome", "nonce": hello["nonce"],
            "unit": "a1b2c3d4", "client": 2,
        }))
        remote.step(12)
        commands = [protocol.decode(KEY, packet) for packet in remote.socket.sent
                    if protocol.decode(KEY, packet)["type"] == "cmd"]
        self.assertEqual([(m["token"], m["client"], m["seq"]) for m in commands],
                         [("BT_VOLUP_R", 1, 1), ("BT_VOLUP_R", 2, 1)])


JPEG = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00\xff\xd9"
MBID = "12345678-1234-1234-1234-123456789abc"
CAA_URL = "https://coverartarchive.org/release-group/" + MBID + "/front-250"
ARCHIVE_URL = "https://archive.org/download/mbid-x/mbid-x-1_thumb250.jpg"
STORAGE_URL = "https://dn721601.ca.archive.org/0/items/mbid-x/mbid-x-1_thumb250.jpg"
DEEZER_SEARCH_URL = "https://api.deezer.com/search/album?limit=8&q=Artist%20album"
DEEZER_COVER_URL = ("https://cdn-images.dzcdn.net/images/cover/" + "0" * 32
                    + "/250x250-000000-80-0-0.jpg")
MUSICBRAINZ = json.dumps({"count": 1, "release-groups": [{
    "id": MBID, "score": 100, "title": "Album", "secondary-types": [],
    "artist-credit": [{"name": "Artist", "artist": {
        "id": "01234567-1234-1234-1234-123456789abc", "name": "Artist"}}],
}]}).encode()
DEEZER = json.dumps({"total": 1, "data": [{
    "type": "album", "id": 301775, "title": "Album", "record_type": "album",
    "artist": {"name": "Artist"}, "cover_medium": DEEZER_COVER_URL,
}]}).encode()
MUSICBRAINZ_EMPTY = b'{"count": 0, "release-groups": []}'
MUSICBRAINZ_BUSY = (b'{"error": "The MusicBrainz web server is currently busy. '
                    b'Please try again later."}\n')


class FakeImage:
    @staticmethod
    def load(data, width, height):
        return (bytes(data), width, height)


class FirmwareRequest:
    """Mirrors the stock fetch request: polling pumps the transfer, success is a
    one-shot truthy value, and any non-2xx status only sets error (never truthy)."""

    def __init__(self, path, status=200, body=b"", location=None, polls=0, fail=None):
        self.path, self.status, self.body, self.polls = path, status, body, polls
        self.fail = fail
        self.error = None
        self.state = "Idle"
        self.reported = False
        self._fetch = types.SimpleNamespace(
            http_status=status,
            http_response_headers={"Location": location} if location else {})

    def poll(self):
        if self.reported:
            return False
        if self.polls > 0:
            self.polls -= 1
            return False
        self.reported = True
        if self.fail:
            self.error = self.fail
            self.state = "Error: %r" % (self.fail,)
            return False
        with open(self.path, "wb") as file:
            file.write(self.body)
        if self.status >= 300:
            self.error = ValueError("HTTP error %d" % self.status)
            self.state = "Error: HTTP error %d" % self.status
            return False
        self.state = "Done"
        return True

    def __bool__(self):
        return self.poll()

    @property
    def done(self):
        return self.poll()


class FirmwareFetch:
    """Scripted replacement for the fetch module; routes match by URL prefix.

    A route's reply may be a list: its replies are served in order and the last
    one repeats.

    Like the stock firmware, a request keeps its socket until gc.collect() runs and
    only POOL sockets exist: a request made with the pool full fails with ENOMEM at
    its first poll however much heap is free."""

    POOL = 5

    def __init__(self, routes):
        self.routes = routes
        self.urls = []
        self.requests = []
        self.open = 0

    def collect(self):
        self.open = 0

    def url(self, url, headers):
        self.urls.append(url)
        reply = next(reply for prefix, reply in self.routes if url.startswith(prefix))
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        outer = self

        class Builder:
            def to(self, path):
                fail = OSError(12, "ENOMEM") if outer.open >= outer.POOL else None
                outer.open += 1
                request = FirmwareRequest(path, fail=fail, **reply)
                outer.requests.append(request)
                return request

        return Builder()


class ArtworkTests(unittest.TestCase):
    def install(self, routes):
        original, had_image = artwork.fetch, hasattr(artwork, "image")
        original_image, original_gc = getattr(artwork, "image", None), artwork.gc

        def restore():
            artwork.fetch = original
            artwork.gc = original_gc
            if had_image:
                artwork.image = original_image
            elif hasattr(artwork, "image"):
                del artwork.image

        self.addCleanup(restore)
        artwork.fetch = FirmwareFetch(routes)
        artwork.gc = types.SimpleNamespace(collect=artwork.fetch.collect)
        artwork.image = FakeImage
        return artwork.fetch

    @staticmethod
    def drive(art, steps=80):
        for step in range(1, steps + 1):
            art.step(step * 50, True)

    def start_caa(self, art, directory):
        art.key, art.artist, art.album, art.group = "0123456789abcdef", "Artist", "Album", MBID
        art._request_url(CAA_URL, "caa", artwork.MAX_JPEG, 0)
        self.assertEqual(art.stage, "caa")

    def test_full_pipeline_follows_cover_art_archive_redirects(self):
        import tempfile
        fake = self.install([
            ("https://musicbrainz.org/", dict(body=MUSICBRAINZ, polls=2)),
            (CAA_URL, dict(status=307, location=ARCHIVE_URL, body=b"See: " + ARCHIVE_URL.encode(), polls=1)),
            (ARCHIVE_URL, dict(status=302, location=STORAGE_URL)),
            (STORAGE_URL, dict(body=JPEG, polls=2)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            art.start("Artist", "Album", 0)
            self.drive(art)
            self.assertEqual(fake.urls[1:], [CAA_URL, ARCHIVE_URL, STORAGE_URL])
            self.assertEqual(art.image[1:], (16, 16))
            self.assertEqual(art.message, "")
            self.assertEqual(art.stage, "")
            names = sorted(path.name for path in Path(directory).iterdir())
            self.assertEqual(len(names), 1)
            self.assertTrue(names[0].endswith(".jpg"))

    def test_consecutive_lookups_collect_sockets_before_each_request(self):
        import tempfile
        fake = self.install([
            ("https://musicbrainz.org/", dict(body=MUSICBRAINZ)),
            (CAA_URL, dict(status=307, location=ARCHIVE_URL)),
            (ARCHIVE_URL, dict(status=302, location=STORAGE_URL)),
            (STORAGE_URL, dict(body=JPEG)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            for lookup in range(3):
                begin = lookup * 10000
                for cached in Path(directory).glob("*.jpg"):
                    cached.unlink()
                art.key = None
                art.start("Artist", "Album", begin)
                for step in range(1, 81):
                    art.step(begin + step * 50, True)
                self.assertIsNotNone(art.image, "lookup %d" % lookup)
                self.assertEqual(art.message, "")
        self.assertEqual(len(fake.urls), 12)
        self.assertGreater(len(fake.urls), fake.POOL)

    def test_http_error_is_noticed_immediately_and_cleans_up(self):
        import tempfile
        self.install([("https://musicbrainz.org/", dict(status=404, body=b"missing", polls=1))])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            art.start("Artist", "Album", 0)
            art.step(50, True)
            self.assertEqual(art.stage, "mb")
            art.step(100, True)
            self.assertEqual(art.message, "Artwork unavailable")
            self.assertEqual(art.stage, "")
            self.assertIsNone(art.request)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_busy_musicbrainz_is_retried_after_the_request_gap(self):
        import tempfile
        fake = self.install([
            ("https://musicbrainz.org/", [dict(status=503, body=MUSICBRAINZ_BUSY),
                                          dict(body=MUSICBRAINZ)]),
            (CAA_URL, dict(status=307, location=ARCHIVE_URL)),
            (ARCHIVE_URL, dict(status=302, location=STORAGE_URL)),
            (STORAGE_URL, dict(body=JPEG)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            art.start("Artist", "Album", 0)
            art.step(50, True)
            self.assertEqual((art.stage, len(fake.urls)), ("mb-wait", 1))
            art.step(1100, True)
            self.assertEqual(len(fake.urls), 1)
            art.step(1150, True)
            self.assertEqual((art.stage, len(fake.urls)), ("mb", 2))
            self.assertEqual(fake.urls[0], fake.urls[1])
            for step in range(24, 200):
                art.step(step * 50, True)
            self.assertEqual(art.image[1:], (16, 16))
            self.assertEqual(art.message, "")
            self.assertEqual([path.suffix for path in Path(directory).iterdir()], [".jpg"])

    def test_busy_fallback_query_is_retried_with_the_fallback_query(self):
        import tempfile
        fake = self.install([
            ("https://musicbrainz.org/", [dict(body=MUSICBRAINZ_EMPTY),
                                          dict(status=503, body=MUSICBRAINZ_BUSY),
                                          dict(body=MUSICBRAINZ)]),
            (CAA_URL, dict(status=307, location=ARCHIVE_URL)),
            (ARCHIVE_URL, dict(status=302, location=STORAGE_URL)),
            (STORAGE_URL, dict(body=JPEG)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            art.start("Artist", "Album", 0)
            self.drive(art, 400)
            self.assertNotEqual(fake.urls[0], fake.urls[1])
            self.assertEqual(fake.urls[1], fake.urls[2])
            self.assertEqual(fake.urls[3:], [CAA_URL, ARCHIVE_URL, STORAGE_URL])
            self.assertEqual(art.image[1:], (16, 16))

    def test_only_server_busy_statuses_are_retried_and_retries_are_bounded(self):
        import tempfile
        for status, retried in ((429, True), (502, True), (503, True), (504, True),
                                (400, False), (404, False), (500, False)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                fake = self.install([("https://musicbrainz.org/",
                                      dict(status=status, body=MUSICBRAINZ_BUSY))])
                art = artwork.Artwork(directory=directory)
                art.start("Artist", "Album", 0)
                self.drive(art, 400)
                self.assertEqual(len(fake.urls), 1 + (artwork.MB_RETRIES if retried else 0))
                self.assertEqual(art.message, "Artwork unavailable")
                self.assertEqual(art.stage, "")
                self.assertIsNone(art.request)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_retry_budget_is_per_lookup(self):
        import tempfile
        fake = self.install([("https://musicbrainz.org/",
                              dict(status=503, body=MUSICBRAINZ_BUSY))])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            for lookup, album in enumerate(("Album", "Other")):
                begin = lookup * 30000
                before = len(fake.urls)
                art.start("Artist", album, begin)
                for step in range(1, 401):
                    art.step(begin + step * 50, True)
                self.assertEqual(len(fake.urls) - before, 1 + artwork.MB_RETRIES, album)
                self.assertEqual(art.message, "Artwork unavailable")

    def test_fuzzy_fallback_query_is_tried_for_every_lookup(self):
        import tempfile
        fake = self.install([("https://musicbrainz.org/", dict(body=MUSICBRAINZ_EMPTY))])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            for lookup, album in enumerate(("Album", "Other")):
                begin = lookup * 30000
                before = len(fake.urls)
                art.start("Artist", album, begin)
                for step in range(1, 401):
                    art.step(begin + step * 50, True)
                self.assertEqual(len(fake.urls) - before, 2, album)
                self.assertEqual(art.message, "No matching cover")

    def test_missing_cover_art_archive_image_falls_back_to_deezer(self):
        import tempfile
        fake = self.install([
            (CAA_URL, dict(status=404, body=b"<html>nope</html>")),
            (DEEZER_SEARCH_URL, dict(body=DEEZER, polls=1)),
            (DEEZER_COVER_URL, dict(body=JPEG)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            self.start_caa(art, directory)
            self.drive(art)
            self.assertEqual(fake.urls, [CAA_URL, DEEZER_SEARCH_URL, DEEZER_COVER_URL])
            self.assertEqual(art.image[1:], (16, 16))
            self.assertEqual([path.suffix for path in Path(directory).iterdir()], [".jpg"])

    def test_redirect_to_unlisted_host_is_never_requested(self):
        import tempfile
        fake = self.install([
            (CAA_URL, dict(status=302, location="https://evil.example/archive.org/x.jpg")),
            (DEEZER_SEARCH_URL, dict(status=404)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            self.start_caa(art, directory)
            self.drive(art)
            self.assertEqual(fake.urls, [CAA_URL, DEEZER_SEARCH_URL])
            self.assertIsNone(art.image)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_redirect_loop_is_bounded(self):
        import tempfile
        hops = ["https://archive.org/%d" % index for index in range(6)]
        routes = [(CAA_URL, dict(status=302, location=hops[0]))]
        routes += [(hops[i], dict(status=302, location=hops[i + 1])) for i in range(5)]
        routes.append((DEEZER_SEARCH_URL, dict(status=404)))
        fake = self.install(routes)
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            self.start_caa(art, directory)
            self.drive(art)
            self.assertEqual(fake.urls, [CAA_URL] + hops[:artwork.MAX_REDIRECTS]
                             + [DEEZER_SEARCH_URL])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_redirect_without_location_falls_back_to_deezer(self):
        import tempfile
        fake = self.install([
            (CAA_URL, dict(status=302)),
            (DEEZER_SEARCH_URL, dict(status=404)),
        ])
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            self.start_caa(art, directory)
            self.drive(art)
            self.assertEqual(fake.urls, [CAA_URL, DEEZER_SEARCH_URL])

    def test_allowed_urls_check_the_parsed_host(self):
        for url in ("https://musicbrainz.org/ws/2/x?fmt=json", CAA_URL, ARCHIVE_URL,
                    STORAGE_URL, DEEZER_SEARCH_URL, DEEZER_COVER_URL,
                    "https://ARCHIVE.ORG/download/x"):
            self.assertTrue(artwork._allowed_url(url), url)
        for url in ("http://archive.org/x", "https://evil.example/a.archive.org/x",
                    "https://archive.org.evil.example/x", "https://notarchive.org/x",
                    "https://user@archive.org/x", "https://archive.org:8443/x",
                    "https://archive.org?x=1", "https://archive.org/a b",
                    "https://archive.org/a\r\nHost: evil", "https://", "", None,
                    "https://archive.org/" + "a" * 512, "/relative/path"):
            self.assertFalse(artwork._allowed_url(url), url)

    def test_deezer_search_uses_plain_text_query(self):
        art = artwork.Artwork(directory="/nonexistent/bm83-test")
        urls = []
        art._request_url = lambda url, stage, limit, now, hops=0: urls.append((url, stage))
        art.artist, art.album = "Daft Punk", "Homework (Remastered 2021)"
        art._start_deezer(0)
        self.assertEqual(urls, [("https://api.deezer.com/search/album?limit=8&q="
                                 "Daft%20Punk%20homework", "deezer-search")])

    def test_unicode_artwork_metadata_uses_character_bound(self):
        art = artwork.Artwork(directory="/nonexistent/bm83-test")
        art.start("é" * 50, "ö" * 50, 0)
        self.assertNotEqual(art.message, "Artwork metadata too long")

    def test_deezer_images_are_decoded_and_cached_for_both_endpoints(self):
        import tempfile
        import shutil
        class FakeImage:
            @staticmethod
            def load(data, width, height):
                return (bytes(data), width, height)
        artwork.image = FakeImage
        jpeg = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00\xff\xd9"
        directory = tempfile.mkdtemp()
        try:
            for stage in ("deezer-image", "deezer-canonical"):
                art = artwork.Artwork(directory=directory)
                art.key, art.artist, art.album = stage, "Artist", "Album"
                art.stage = stage
                art.limit = artwork.MAX_JPEG
                art.temp = art._path(stage, ".tmp")
                art.request = True
                with open(art.temp, "wb") as file:
                    file.write(jpeg)
                art._complete_file(10)
                self.assertEqual(art.image[1:], (16, 16))
                self.assertTrue(art.path.endswith(".jpg"))
                self.assertEqual(art.stage, "")
        finally:
            shutil.rmtree(directory)
            del artwork.image

    def test_deezer_image_request_uses_jpeg_accept_header(self):
        class DummyRequest:
            pass
        class FakeFetch:
            headers = None

            @classmethod
            def url(cls, url, headers):
                cls.headers = headers
                return cls()

            @staticmethod
            def to(path):
                return DummyRequest()
        directory = "/state/bm83_test_art"
        art = artwork.Artwork(directory=directory)
        art.key = "0123456789abcdef"
        artwork.fetch = FakeFetch
        try:
            art._request_url(
                "https://cdn-images.dzcdn.net/images/cover/"
                + "0" * 32 + "/250x250-000000-80-0-0.jpg",
                "deezer-image", artwork.MAX_JPEG, 0)
            self.assertEqual(FakeFetch.headers["Accept"], "image/jpeg")
        finally:
            artwork.fetch = None

    def test_matching_requires_score_unique_artist_album_and_non_compilation(self):
        group_id = "12345678-1234-1234-1234-123456789abc"
        group = {
            "id": group_id, "score": 99, "title": "Homework",
            "artist-credit": [{"name": "Daft Punk",
                              "artist": {"id": "01234567-1234-1234-1234-123456789abc",
                                         "name": "Daft Punk"}}],
            "secondary-types": [],
        }
        data = {"count": 1, "release-groups": [group]}
        self.assertEqual(artwork._match_group(data, "Daft Punk", "Homework"), group_id)
        self.assertIsNone(artwork._match_group(
            {"count": 1, "release-groups": [dict(group, score=94)]},
            "Daft Punk", "Homework"))
        self.assertIsNone(artwork._match_group(
            {"count": 1, "release-groups": [dict(group, **{"secondary-types": ["Compilation"]})]},
            "Daft Punk", "Homework"))

    def test_progressive_jpeg_is_rejected(self):
        progressive = (b"\xff\xd8\xff\xc2\x00\x08\x08\x00\x10\x00\x10"
                       b"\x03\x01\x11\x00\xff\xd9")
        with self.assertRaisesRegex(ValueError, "Progressive"):
            artwork._jpeg_dimensions(progressive)

    def test_oversize_completed_download_removes_temp_file(self):
        import tempfile
        class Request:
            error = None
            done = True

            def __bool__(self):
                return self.done

        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            path = art._path("0123456789abcdef", ".tmp")
            with open(path, "wb") as file:
                file.write(b"x" * 5)
            art.key = "0123456789abcdef"
            art.stage = "caa"
            art.limit = 4
            art.request = Request()
            art.temp = path
            art.step(1, True)
            self.assertFalse(Path(path).exists())
            self.assertEqual(art.message, "Artwork response too large")

    def test_rejected_caa_images_never_accumulate_in_cache(self):
        import tempfile
        class Request:
            error = None
            done = True

            def __bool__(self):
                return True

        progressive = (b"\xff\xd8\xff\xc2\x00\x08\x08\x00\x10\x00\x10"
                       b"\x03\x01\x11\x00\xff\xd9")
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            for index in range(6):
                art.key = "%016x" % index
                art.stage = "caa"
                art.limit = artwork.MAX_JPEG
                art.request = Request()
                art.temp = art._path(art.key, ".tmp")
                with open(art.temp, "wb") as file:
                    file.write(progressive)
                with self.assertRaisesRegex(ValueError, "Progressive"):
                    art._complete_file(index)
                art._use_deezer({"total": 0, "data": []}, index)
                self.assertEqual(art.message, "No matching cover")
                self.assertFalse(Path(art._path(art.key, ".jpg")).exists())
            names = [path.name for path in Path(directory).iterdir()]
            cached = [name for name in names if name.endswith(".jpg")]
            partial = [name for name in names if name.endswith(".tmp")]
            self.assertEqual(cached, [])
            self.assertEqual(partial, [])

    def test_timeout_keeps_one_temp_until_fetch_finishes_then_cleans_it(self):
        import tempfile
        class Request:
            error = None
            done = False

            def __bool__(self):
                return self.done

        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            request = Request()
            path = art._path("0123456789abcdef", ".tmp")
            with open(path, "wb") as file:
                file.write(b"partial")
            art.started = 0
            art.stage = "mb"
            art.request = request
            art.temp = path
            art.step(45001, True)
            self.assertEqual(art.message, "Artwork lookup timed out")
            self.assertTrue(Path(path).exists())
            self.assertIs(art.abandoned[0], request)
            request.done = True
            art.step(45002, True)
            self.assertFalse(Path(path).exists())
            self.assertIsNone(art.abandoned)

    def test_album_change_serializes_cleanup_and_exit_removes_partial(self):
        import tempfile
        class Request:
            error = None
            done = False

            def __bool__(self):
                return self.done

        class FakeFetch:
            paths = []

            class Builder:
                def to(self, path):
                    with open(path, "wb") as file:
                        file.write(b"partial")
                    FakeFetch.paths.append(path)
                    return Request()

            @classmethod
            def url(cls, url, headers):
                return cls.Builder()

        original_fetch = artwork.fetch
        with tempfile.TemporaryDirectory() as directory:
            art = artwork.Artwork(directory=directory)
            old_request = Request()
            old_path = art._path("old-key", ".tmp")
            with open(old_path, "wb") as file:
                file.write(b"partial")
            art.request, art.temp, art.stage = old_request, old_path, "mb"
            art.key, art.artist, art.album = "old-key", "Old Artist", "Old Album"
            artwork.fetch = FakeFetch
            try:
                art.start("New Artist", "New Album", 1)
                self.assertEqual(art.stage, "fetch-wait")
                self.assertEqual(FakeFetch.paths, [])
                old_request.done = True
                art.step(2, True)
                self.assertFalse(Path(old_path).exists())
                self.assertEqual(len(FakeFetch.paths), 1)
                new_path = FakeFetch.paths[0]
                self.assertTrue(Path(new_path).exists())
                art.close()
                self.assertFalse(Path(new_path).exists())
            finally:
                artwork.fetch = original_fetch
                art.close()


if __name__ == "__main__":
    unittest.main()
