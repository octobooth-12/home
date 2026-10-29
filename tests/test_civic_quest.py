"""Host-side checks for the Civic Quest app using a fake 2026 runtime."""

import builtins
from pathlib import Path
import sys
import unittest
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1] / "badge/apps/civic_quest"

BUTTONS = ("BUTTON_UP", "BUTTON_DOWN", "BUTTON_LEFT", "BUTTON_RIGHT",
           "BUTTON_SELECT", "BUTTON_BACK", "BUTTON_HOME", "BUTTON_MENU")
NAV_AND_SELECT = ("BUTTON_UP", "BUTTON_DOWN", "BUTTON_LEFT", "BUTTON_RIGHT", "BUTTON_SELECT")


class Obj:
    """Accepts any attribute or call so drawing primitives are no-ops."""

    def __getattr__(self, name):
        return Obj()

    def __call__(self, *args, **kwargs):
        return Obj()


class FakeBadge:
    def __init__(self):
        self.ticks = 1000
        self.ticks_delta = 16
        self.key = None

    def mode(self, *_):
        pass

    def pressed(self, button=None):
        return button is not None and button == self.key

    def held(self, button=None):
        return False

    def released(self, button=None):
        return False


class FakeScreen:
    width = 320
    height = 240

    def __init__(self):
        self.font = None
        self.pen = None
        self.antialias = None
        self.drawn = []

    def measure_text(self, s):
        return (len(s) * 7, 12)

    def text(self, s, x, y):
        self.drawn.append(s)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class FakeState:
    saved = {}

    @classmethod
    def load(cls, name, data):
        if name in cls.saved:
            data.update(cls.saved[name])

    @classmethod
    def save(cls, name, data):
        cls.saved[name] = data


class CivicQuestTests(unittest.TestCase):
    def setUp(self):
        FakeState.saved = {}
        self.badge = FakeBadge()
        self.screen = FakeScreen()
        fakes = {
            "badge": self.badge,
            "screen": self.screen,
            "image": Obj(),
            "font": Obj(),
            "color": Obj(),
            "shape": Obj(),
            "vec2": Obj(),
            "rect": Obj(),
            "mat3": Obj(),
            "run": lambda f: None,
            "is_dir": lambda p: False,
            "HIRES": 1,
            "VSYNC": 2,
        }
        for i, name in enumerate(BUTTONS):
            fakes[name] = "b%d" % i
        self.patches = [mock.patch.object(builtins, k, v, create=True) for k, v in fakes.items()]
        self.patches.append(mock.patch("os.chdir"))
        self.patches.append(mock.patch.dict(sys.modules, {"badgeware": mock.Mock(State=FakeState)}))
        for p in self.patches:
            p.start()
        sys.modules.pop("cq_content", None)
        sys.path.insert(0, str(APP_DIR))
        self.ns = {"__name__": "civic_quest_test"}
        exec(compile((APP_DIR / "__init__.py").read_text(), "civic_quest", "exec"), self.ns)
        self.C = self.ns["C"]
        self.game = self.ns["game"]

    def tearDown(self):
        sys.path.remove(str(APP_DIR))
        sys.modules.pop("cq_content", None)
        for p in reversed(self.patches):
            p.stop()

    def press(self, name):
        self.badge.key = getattr(builtins, name)
        self.badge.ticks += 1000
        self.ns["update"]()
        self.badge.key = None

    def candidate_strings(self):
        out = set()
        for c in self.C.CANDIDATES:
            out.update((c["name"], c["first"], c["last"]))
        return out

    def drawn_names(self):
        names = self.candidate_strings()
        return [s for s in self.screen.drawn if any(n in s for n in names)]

    def choose_key(self):
        g = self.game
        if g.mode == "level" and g.step_kind() == "quiz" and g.phase == "ask":
            qd = g.steps[g.step_i][1][g.qi]
            return "BUTTON_SELECT" if g.choice == qd["answer"] else "BUTTON_DOWN"
        return "BUTTON_SELECT"

    def play_to_certificate(self, on_frame=None):
        for _ in range(2000):
            if self.game.mode == "certificate":
                return
            key = self.choose_key()
            self.assertIn(key, NAV_AND_SELECT)
            self.press(key)
            if on_frame:
                on_frame()
        self.fail("playthrough did not reach the certificate")

    def test_full_playthrough_with_dpad_and_select_only(self):
        self.play_to_certificate()
        progress = self.ns["progress"]
        self.assertEqual(progress["done"], [True] * 5)
        expected = [self.ns["total_questions"](i) for i in range(5)]
        self.assertEqual(progress["best"], expected)
        self.press("BUTTON_SELECT")
        self.assertEqual(self.game.mode, "title")

    def test_candidates_hidden_until_reveal_then_shown_equally(self):
        g = self.game
        state = {"revealed": False}

        def check():
            if g.mode == "level" and g.li == 3 and g.step_kind() == "reveal":
                state["revealed"] = True
            if not state["revealed"]:
                self.assertEqual(self.drawn_names(), [], "candidate named before reveal")
            self.screen.drawn = []

        self.play_to_certificate(check)
        self.assertTrue(state["revealed"])

        self.ns["progress"]["done"] = [True, True, True, False, False]
        g.enter_level(3)
        g.start_step(1, 1)
        g.reveal_t = self.badge.ticks - 5000
        self.screen.drawn = []
        g.draw()
        for c in self.C.CANDIDATES:
            self.assertIn(c["first"], self.screen.drawn)
            self.assertIn(c["last"], self.screen.drawn)

    def test_hidden_content_never_names_candidates_before_level_four(self):
        names = self.candidate_strings()
        blob = repr(self.C.LEVELS[:3]) + repr(self.C.PROPOSALS) + repr(self.C.ISSUES)
        for n in names:
            self.assertNotIn(n, blob)

    def test_ballot_is_forgotten_and_never_saved(self):
        g = self.game
        g.enter_level(4)
        g.start_step(1, 1)
        order = list(g.ballot_order)
        self.assertEqual(sorted(order), [0, 1, 2])
        self.press("BUTTON_DOWN")
        self.press("BUTTON_SELECT")
        self.assertEqual(g.ballot_mark, 1)
        self.press("BUTTON_SELECT")
        self.assertEqual(g.ballot_phase, "cast")
        self.assertIsNone(g.ballot_mark)
        self.assertIsNone(g.ballot_order)
        self.play_to_certificate()
        saved = FakeState.saved["civic_quest"]
        self.assertEqual(set(saved), {"done", "best"})
        text = repr(saved)
        for n in self.candidate_strings():
            self.assertNotIn(n, text)
        for p in self.C.PLATFORMS:
            self.assertNotIn(p, text)

    def test_leave_blank_is_allowed(self):
        g = self.game
        g.enter_level(4)
        g.start_step(1, 1)
        for _ in range(3):
            self.press("BUTTON_DOWN")
        self.press("BUTTON_SELECT")
        self.assertEqual(g.ballot_mark, 3)
        self.press("BUTTON_SELECT")
        self.assertEqual(g.ballot_phase, "cast")

    def test_explore_requires_every_card(self):
        g = self.game
        g.enter_level(2)
        g.start_step(1, 1)
        presses = 0
        while g.step_kind() == "explore":
            self.press("BUTTON_SELECT")
            presses += 1
            self.assertLess(presses, 20)
        self.assertEqual(len(g.seen), 12)

    def test_wrong_answers_score_lower_but_still_progress(self):
        g = self.game
        g.enter_level(0)
        g.start_step(1, 1)
        while g.mode == "level":
            qd = g.steps[g.step_i][1][g.qi] if g.step_kind() == "quiz" else None
            if qd and g.phase == "ask" and g.choice == qd["answer"]:
                self.press("BUTTON_DOWN")
            self.press("BUTTON_SELECT")
        self.assertEqual(g.mode, "complete")
        self.assertEqual(self.ns["progress"]["best"][0], 0)
        self.assertTrue(self.ns["progress"]["done"][0])

    def test_left_returns_to_map_from_first_page(self):
        g = self.game
        g.enter_level(0)
        self.press("BUTTON_LEFT")
        self.assertEqual(g.mode, "map")
        self.press("BUTTON_LEFT")
        self.assertEqual(g.mode, "title")

    def test_locked_levels_and_reset(self):
        g = self.game
        g.go("map", 1, 2)
        self.press("BUTTON_SELECT")
        self.assertEqual(g.mode, "map")
        self.ns["progress"]["done"][0] = True
        g.go("reset", 1, 0)
        self.press("BUTTON_DOWN")
        self.press("BUTTON_SELECT")
        self.assertEqual(self.ns["progress"]["done"], [False] * 5)
        self.assertEqual(g.mode, "title")

    def test_corrupt_saved_state_is_sanitized(self):
        p = {"done": [True, "yes"], "best": [3, -1, 500], "ballot": "X"}
        self.ns["sanitize"](p)
        self.assertEqual(set(p), {"done", "best"})
        self.assertEqual(p["done"], [True, False, False, False, False])
        self.assertEqual(p["best"], [3, 0, 0, 0, 0])

    def test_content_shape(self):
        C = self.C
        self.assertLessEqual(len(C.LEVELS), 5)
        self.assertEqual(len(C.CANDIDATES), len(C.PLATFORMS))
        self.assertEqual(len(C.ISSUES), 4)
        for row in C.PROPOSALS:
            self.assertEqual(len(row), len(C.ISSUES))
        for c in C.CANDIDATES:
            self.assertEqual(len(c["short"]), len(C.ISSUES))
        for level in C.LEVELS:
            for kind, data in level["steps"]:
                if kind == "quiz":
                    for qd in data:
                        self.assertTrue(0 <= qd["answer"] < len(qd["options"]))
                        self.assertTrue(qd["why"])
        (APP_DIR / "cq_content.py").read_text().encode("ascii")
        (APP_DIR / "__init__.py").read_text().encode("ascii")

    def test_pages_fit_with_rough_metrics(self):
        avail = self.ns["AVAIL"]
        for li in range(len(self.C.LEVELS)):
            for kind, data in self.ns["level_steps"](li):
                if kind == "read":
                    for page in data:
                        self.assertLessEqual(self.ns["rows_bottom"](page["rows"]), avail)


if __name__ == "__main__":
    unittest.main()
