import math
import os
import random
import sys

APP_NAME = "civic_quest"
APP_DIRS = ("/remote/apps/civic_quest", "/system/apps/civic_quest")


def _app_dir():
    for path in APP_DIRS:
        try:
            if is_dir(path):
                return path
        except Exception:
            pass
    return APP_DIRS[-1]


APP_DIR = _app_dir()
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from badgeware import State
import cq_content as C

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

W = screen.width
H = screen.height

BG = color.rgb(13, 17, 23)
PANEL = color.rgb(22, 27, 34)
PANEL_2 = color.rgb(33, 39, 48)
LINE = color.rgb(48, 54, 61)
TEXT = color.rgb(201, 209, 217)
BRIGHT = color.rgb(240, 246, 252)
DIM = color.rgb(125, 133, 144)
ACCENT = color.rgb(88, 166, 255)
GOOD = color.rgb(63, 185, 80)
WARN = color.rgb(210, 153, 34)
GOLD = color.rgb(227, 179, 65)
PAPER = color.rgb(238, 235, 226)
INK = color.rgb(36, 41, 47)
INK_DIM = color.rgb(110, 115, 120)

# Equal-weight colours for platforms X, Y, Z (and their candidates).
PLATFORM_PENS = (
    color.rgb(57, 197, 187),
    color.rgb(240, 128, 170),
    color.rgb(163, 140, 255),
)
LEVEL_PENS = (
    color.rgb(88, 166, 255),
    color.rgb(63, 185, 80),
    color.rgb(163, 140, 255),
    color.rgb(240, 136, 62),
    color.rgb(227, 179, 65),
)

F_BIG = font.ignore
F_H = font.absolute
F_BODY = font.nope
F_SMALL = font.ark
LH_H = 18
LH_B = 15
LH_S = 13

MX = 14
HEADER_H = 24
BODY_TOP = 34
FOOTER_Y = H - 22
BODY_BOTTOM = FOOTER_Y - 6
AVAIL = BODY_BOTTOM - BODY_TOP
TEXT_W = W - 2 * MX

LEVEL_COUNT = len(C.LEVELS)
TRANSITION_MS = 220


# ---------------------------------------------------------------- utilities

def now():
    return badge.ticks


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ease(t):
    t = clamp(t, 0.0, 1.0)
    return 1 - (1 - t) ** 3


def measure(s, f):
    screen.font = f
    return screen.measure_text(s)[0]


def wrap(s, width, f):
    screen.font = f
    lines = []
    for para in s.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = word if not cur else cur + " " + word
            if not cur or screen.measure_text(trial)[0] <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def text(s, x, y, f, pen):
    screen.font = f
    screen.pen = pen
    screen.text(s, int(x), int(y))


def text_c(s, y, f, pen, cx=None):
    cx = W / 2 if cx is None else cx
    text(s, cx - measure(s, f) / 2, y, f, pen)


def text_r(s, xr, y, f, pen):
    text(s, xr - measure(s, f), y, f, pen)


def rrect(x, y, w, h, r, pen):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(x, y, w, h, r))


def rrect_line(x, y, w, h, r, pen, t=1):
    screen.pen = pen
    screen.shape(shape.rounded_rectangle(x, y, w, h, r).stroke(t))


def rect(x, y, w, h, pen):
    screen.pen = pen
    screen.rectangle(int(x), int(y), int(w), int(h))


def dot(x, y, r, pen):
    screen.pen = pen
    screen.circle(vec2(x, y), r)


def seg(x0, y0, x1, y1, w, pen):
    screen.pen = pen
    screen.shape(shape.line(x0, y0, x1, y1, w))


def icon_check(cx, cy, s, pen, w=2):
    seg(cx - s, cy, cx - s * 0.3, cy + s * 0.7, w, pen)
    seg(cx - s * 0.3, cy + s * 0.7, cx + s, cy - s * 0.7, w, pen)


def icon_cross(cx, cy, s, pen, w=2):
    seg(cx - s, cy - s, cx + s, cy + s, w, pen)
    seg(cx - s, cy + s, cx + s, cy - s, w, pen)


def icon_sign(cx, cy, kind):
    dot(cx, cy, 5, GOOD if kind == "plus" else WARN)
    rect(cx - 3, cy - 0.5, 6, 2, BG)
    if kind == "plus":
        rect(cx - 0.5, cy - 3, 2, 6, BG)


def icon_star(cx, cy, r, pen, filled=True):
    s = shape.star(cx, cy, 5, r * 0.45, r)
    screen.pen = pen
    screen.shape(s if filled else s.stroke(1.5))


def icon_lock(cx, cy, pen):
    rrect_line(cx - 3, cy - 7, 6, 8, 3, pen, 1.5)
    rrect(cx - 5, cy - 2, 10, 8, 2, pen)


def chevron(cx, cy, direction, pen, s=3):
    dx, dy = direction
    if dx:
        seg(cx - dx * s / 2, cy - s, cx + dx * s / 2, cy, 1.5, pen)
        seg(cx + dx * s / 2, cy, cx - dx * s / 2, cy + s, 1.5, pen)
    else:
        seg(cx - s, cy - dy * s / 2, cx, cy + dy * s / 2, 1.5, pen)
        seg(cx, cy + dy * s / 2, cx + s, cy - dy * s / 2, 1.5, pen)


def stars_for(correct, total):
    if total <= 0:
        return 1
    return 1 + (correct * 2) // total


def shuffled(seq):
    items = list(seq)
    for i in range(len(items) - 1, 0, -1):
        j = random.getrandbits(16) % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items


# ------------------------------------------------------------------- layout

def layout_page(page):
    """Turn a content page into one or more fitted pages of drawable rows."""
    blocks = []
    for item in page["items"]:
        kind = item[0]
        rows = []
        if kind == "h":
            lines = wrap(item[1], TEXT_W, F_H)
            rows = [("h", MX, i * LH_H, line, 0) for i, line in enumerate(lines)]
            height = len(lines) * LH_H + 5
        elif kind == "p":
            lines = wrap(item[1], TEXT_W, F_BODY)
            rows = [("p", MX, i * LH_B, line, 0) for i, line in enumerate(lines)]
            height = len(lines) * LH_B + 6
        elif kind in ("plus", "minus"):
            lines = wrap(item[1], TEXT_W - 18, F_BODY)
            rows = [(kind, MX + 18, i * LH_B, line, i == 0) for i, line in enumerate(lines)]
            height = len(lines) * LH_B + 5
        elif kind == "note":
            lines = wrap(item[1], TEXT_W - 10, F_SMALL)
            rows = [("note", MX + 10, i * LH_S + 1, line, len(lines) * LH_S if i == 0 else 0)
                    for i, line in enumerate(lines)]
            height = len(lines) * LH_S + 6
        elif kind == "kv":
            lines = wrap(item[2], TEXT_W - 96, F_BODY)
            rows = [("kvl", MX, 2, item[1], 0)]
            rows += [("kv", MX + 96, i * LH_B, line, 0) for i, line in enumerate(lines)]
            height = len(lines) * LH_B + 6
        else:
            continue
        blocks.append((height, rows))

    pages = []
    current = []
    y = 0
    for height, rows in blocks:
        if current and y + height - 6 > AVAIL:
            pages.append(current)
            current = []
            y = 0
        for kind, x, ry, line, extra in rows:
            current.append((kind, x, y + ry, line, extra))
        y += height
    if current:
        pages.append(current)
    accent = page.get("accent")
    return [{"rows": rows, "accent": accent} for rows in pages]


def rows_bottom(rows):
    bottom = 0
    for kind, _x, y, _line, _extra in rows:
        lh = LH_H if kind == "h" else LH_S if kind in ("note", "kvl") else LH_B
        bottom = max(bottom, y + lh)
    return bottom


def layout_quiz(qd):
    attempts = ((F_H, LH_H, F_BODY, LH_B), (F_BODY, LH_B, F_BODY, LH_B), (F_BODY, LH_B, F_SMALL, LH_S))
    for qf, qlh, of, olh in attempts:
        qlines = wrap(qd["q"], TEXT_W, qf)
        y = len(qlines) * qlh + 8
        boxes = []
        for option in qd["options"]:
            lines = wrap(option, TEXT_W - 34, of)
            h = len(lines) * olh + 10
            boxes.append((y, h, lines))
            y += h + 5
        bottom = y - 5
        if bottom <= AVAIL:
            break
    return {"qf": qf, "qlh": qlh, "qlines": qlines, "of": of, "olh": olh,
            "boxes": boxes, "bottom": bottom}


def layout_feedback(qd):
    answer = wrap(qd["options"][qd["answer"]], TEXT_W - 20, F_BODY)
    why = wrap(qd["why"], TEXT_W, F_BODY)
    answer_top = 40
    answer_h = len(answer) * LH_B + 10
    why_top = answer_top + answer_h + 10
    return {"answer": answer, "answer_h": answer_h, "why": why, "why_top": why_top,
            "bottom": why_top + len(why) * LH_B}


def layout_proposal(p, i):
    plan, gain, cost = C.PROPOSALS[p][i]
    inner = TEXT_W - 20
    plan_l = wrap(plan, inner, F_BODY)
    for f, lh in ((F_BODY, LH_B), (F_SMALL, LH_S)):
        gain_l = wrap(gain, inner - 18, f)
        cost_l = wrap(cost, inner - 18, f)
        height = 10 + len(plan_l) * LH_B + 8 + len(gain_l) * lh + 5 + len(cost_l) * lh + 8
        if height <= CARD_H:
            break
    return {"plan": plan_l, "gain": gain_l, "cost": cost_l, "f": f, "lh": lh, "height": height}


CARD_Y = 78
CARD_H = BODY_BOTTOM - CARD_Y

_level_cache = {}
_quiz_cache = {}
_feedback_cache = {}
_proposal_cache = {}


def level_steps(li):
    if li not in _level_cache:
        steps = []
        for kind, data in C.LEVELS[li]["steps"]:
            if kind == "read":
                pages = []
                for page in data:
                    pages.extend(layout_page(page))
                steps.append((kind, pages))
            else:
                steps.append((kind, data))
        _level_cache[li] = steps
    return _level_cache[li]


def quiz_layout(li, si, qi, feedback=False):
    key = (li, si, qi)
    cache = _feedback_cache if feedback else _quiz_cache
    if key not in cache:
        qd = C.LEVELS[li]["steps"][si][1][qi]
        cache[key] = layout_feedback(qd) if feedback else layout_quiz(qd)
    return cache[key]


def proposal_layout(p, i):
    key = (p, i)
    if key not in _proposal_cache:
        _proposal_cache[key] = layout_proposal(p, i)
    return _proposal_cache[key]


# ------------------------------------------------------------------ progress

progress = {"done": [False] * LEVEL_COUNT, "best": [0] * LEVEL_COUNT}


def sanitize(p):
    done = p.get("done")
    best = p.get("best")
    clean_done = []
    clean_best = []
    for i in range(LEVEL_COUNT):
        d = done[i] if isinstance(done, list) and i < len(done) else False
        b = best[i] if isinstance(best, list) and i < len(best) else 0
        clean_done.append(d is True)
        clean_best.append(b if isinstance(b, int) and 0 <= b <= 99 else 0)
    p.clear()
    p["done"] = clean_done
    p["best"] = clean_best


try:
    State.load(APP_NAME, progress)
except Exception:
    pass
sanitize(progress)


def save_progress():
    # Only level completion and knowledge scores are stored. No answers,
    # ballot choices or anything about the player's views are ever saved.
    try:
        State.save(APP_NAME, {"done": list(progress["done"]), "best": list(progress["best"])})
    except Exception:
        pass


def unlocked(li):
    return li == 0 or progress["done"][li - 1]


def all_done():
    return all(progress["done"])


def total_questions(li):
    total = 0
    for kind, data in C.LEVELS[li]["steps"]:
        if kind == "quiz":
            total += len(data)
    return total


# --------------------------------------------------------------------- game

DIRECTIONS = (BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_SELECT, BUTTON_BACK)


def read_key():
    for b in DIRECTIONS:
        if badge.pressed(b):
            return b
    return None


class Game:
    def __init__(self):
        self.mode = "title"
        self.cursor = 0
        self.t_enter = now()
        self.dir = 1
        self.flash = None
        self.flash_t = 0
        self.li = 0
        self.steps = []
        self.step_i = 0
        self.page = 0
        self.qi = 0
        self.phase = "ask"
        self.choice = 0
        self.last_correct = False
        self.correct = 0
        self.answered = 0
        self.ex_issue = 0
        self.ex_plat = 0
        self.seen = set()
        self.reveal_t = 0
        self.ballot_order = None
        self.ballot_mark = None
        self.ballot_cursor = 0
        self.ballot_phase = "mark"
        self.cast_t = 0
        self.complete_t = 0
        self.bar = 0.0
        self.hl_y = None

    # -- navigation helpers
    def bump(self, direction=1):
        self.t_enter = now()
        self.dir = direction
        self.hl_y = None

    def go(self, mode, direction=1, cursor=0):
        self.mode = mode
        self.cursor = cursor
        self.bump(direction)

    def say(self, message):
        self.flash = message
        self.flash_t = now()

    def offset(self):
        t = (now() - self.t_enter) / TRANSITION_MS
        return self.dir * 24 * (1 - ease(t))

    # -- level flow
    def enter_level(self, li):
        self.li = li
        self.steps = level_steps(li)
        self.correct = 0
        self.answered = 0
        self.bar = 0.0
        self.mode = "level"
        self.start_step(0, 1)

    def start_step(self, idx, direction, at_end=False):
        self.step_i = idx
        kind, data = self.steps[idx]
        self.page = len(data) - 1 if (at_end and kind == "read") else 0
        if kind == "quiz":
            self.qi = 0
            self.phase = "ask"
            self.choice = 0
        elif kind == "explore":
            self.ex_issue = 0
            self.ex_plat = 0
            self.seen = {(0, 0)}
        elif kind == "reveal":
            self.reveal_t = now()
        elif kind == "ballot":
            self.ballot_order = shuffled(range(len(C.CANDIDATES)))
            self.ballot_mark = None
            self.ballot_cursor = 0
            self.ballot_phase = "mark"
        self.bump(direction)

    def next_step(self):
        if self.step_i + 1 < len(self.steps):
            self.start_step(self.step_i + 1, 1)
        else:
            self.finish_level()

    def back_step(self):
        if self.step_i == 0:
            self.go("map", -1, self.li)
        elif self.steps[self.step_i - 1][0] == "read":
            self.start_step(self.step_i - 1, -1, at_end=True)

    def finish_level(self):
        li = self.li
        progress["done"][li] = True
        progress["best"][li] = max(progress["best"][li], self.correct)
        save_progress()
        self.complete_t = now()
        self.go("complete", 1)

    def step_kind(self):
        return self.steps[self.step_i][0]

    def level_fraction(self):
        kind, data = self.steps[self.step_i]
        sub = 0.0
        if kind == "read":
            sub = (self.page + 1) / len(data)
        elif kind == "quiz":
            sub = (self.qi + (1 if self.phase == "feedback" else 0)) / len(data)
        elif kind == "explore":
            sub = len(self.seen) / 12
        elif kind == "reveal":
            sub = 1.0 if self.reveal_done() else 0.5
        elif kind == "ballot":
            sub = 1.0 if self.ballot_phase == "cast" else 0.5
        return (self.step_i + sub) / len(self.steps)

    def reveal_done(self):
        return now() - self.reveal_t > 350 * 2 + 500

    # -- input
    def update(self):
        key = read_key()
        if key is not None:
            handler = getattr(self, "on_" + self.mode)
            handler(key)

    def on_title(self, key):
        items = self.title_items()
        if key in (BUTTON_UP, BUTTON_DOWN):
            self.cursor = (self.cursor + (1 if key == BUTTON_DOWN else -1)) % len(items)
        elif key == BUTTON_SELECT:
            action = items[self.cursor][1]
            if action == "play":
                nxt = next_level()
                if nxt is None:
                    self.go("certificate", 1)
                else:
                    self.enter_level(nxt)
            elif action == "map":
                self.go("map", 1, next_level() or 0)
            elif action == "reset":
                self.go("reset", 1, 0)

    def title_items(self):
        nxt = next_level()
        if nxt is None:
            first = "View certificate"
        elif nxt == 0 and not any(progress["done"]):
            first = "Start"
        else:
            first = "Continue: Level %d" % (nxt + 1)
        return ((first, "play"), ("Level map", "map"), ("Reset progress", "reset"))

    def on_reset(self, key):
        if key in (BUTTON_UP, BUTTON_DOWN):
            self.cursor = 1 - self.cursor
        elif key == BUTTON_SELECT:
            if self.cursor == 1:
                progress["done"] = [False] * LEVEL_COUNT
                progress["best"] = [0] * LEVEL_COUNT
                save_progress()
                self.say("Progress erased")
            self.go("title", -1, 0)
        elif key in (BUTTON_LEFT, BUTTON_BACK):
            self.go("title", -1, 2)

    def on_map(self, key):
        rows = LEVEL_COUNT + 1
        if key in (BUTTON_UP, BUTTON_DOWN):
            self.cursor = (self.cursor + (1 if key == BUTTON_DOWN else -1)) % rows
        elif key in (BUTTON_LEFT, BUTTON_BACK):
            self.go("title", -1, 1)
        elif key in (BUTTON_SELECT, BUTTON_RIGHT):
            if self.cursor == LEVEL_COUNT:
                if all_done():
                    self.go("certificate", 1)
                else:
                    self.say("Finish all 5 levels first")
            elif unlocked(self.cursor):
                self.enter_level(self.cursor)
            else:
                self.say("Finish Level %d first" % self.cursor)

    def on_level(self, key):
        if key == BUTTON_BACK:
            self.go("map", -1, self.li)
            return
        getattr(self, "on_" + self.step_kind())(key)

    def on_read(self, key):
        pages = self.steps[self.step_i][1]
        if key in (BUTTON_RIGHT, BUTTON_SELECT):
            if self.page < len(pages) - 1:
                self.page += 1
                self.bump(1)
            else:
                self.next_step()
        elif key == BUTTON_LEFT:
            if self.page > 0:
                self.page -= 1
                self.bump(-1)
            else:
                self.back_step()

    def on_quiz(self, key):
        questions = self.steps[self.step_i][1]
        qd = questions[self.qi]
        if self.phase == "ask":
            n = len(qd["options"])
            if key in (BUTTON_UP, BUTTON_DOWN):
                self.choice = (self.choice + (1 if key == BUTTON_DOWN else -1)) % n
            elif key == BUTTON_SELECT:
                self.last_correct = self.choice == qd["answer"]
                if self.last_correct:
                    self.correct += 1
                self.answered += 1
                self.phase = "feedback"
                self.bump(1)
        elif key in (BUTTON_SELECT, BUTTON_RIGHT):
            if self.qi + 1 < len(questions):
                self.qi += 1
                self.phase = "ask"
                self.choice = 0
                self.bump(1)
            else:
                self.next_step()

    def on_explore(self, key):
        if key in (BUTTON_UP, BUTTON_DOWN):
            self.ex_issue = (self.ex_issue + (1 if key == BUTTON_DOWN else -1)) % len(C.ISSUES)
            self.bump(1 if key == BUTTON_DOWN else -1)
        elif key in (BUTTON_LEFT, BUTTON_RIGHT):
            self.ex_plat = (self.ex_plat + (1 if key == BUTTON_RIGHT else -1)) % len(C.PLATFORMS)
            self.bump(1 if key == BUTTON_RIGHT else -1)
        elif key == BUTTON_SELECT:
            if len(self.seen) >= 12:
                self.next_step()
                return
            for i in range(len(C.ISSUES)):
                for p in range(len(C.PLATFORMS)):
                    if (i, p) not in self.seen:
                        self.ex_issue, self.ex_plat = i, p
                        self.bump(1)
                        self.seen.add((i, p))
                        return
        self.seen.add((self.ex_issue, self.ex_plat))

    def on_reveal(self, key):
        if key in (BUTTON_SELECT, BUTTON_RIGHT):
            if self.reveal_done():
                self.next_step()
            else:
                self.reveal_t = now() - 5000

    def on_ballot(self, key):
        if self.ballot_phase == "cast":
            if key in (BUTTON_SELECT, BUTTON_RIGHT) and now() - self.cast_t > 900:
                self.next_step()
            return
        rows = len(C.CANDIDATES) + 2
        if key in (BUTTON_UP, BUTTON_DOWN):
            self.ballot_cursor = (self.ballot_cursor + (1 if key == BUTTON_DOWN else -1)) % rows
        elif key == BUTTON_SELECT:
            if self.ballot_cursor == rows - 1:
                # Cast: forget the mark immediately. It is never stored or scored.
                self.ballot_mark = None
                self.ballot_order = None
                self.ballot_phase = "cast"
                self.cast_t = now()
                self.bump(1)
            else:
                self.ballot_mark = self.ballot_cursor
                self.ballot_cursor = rows - 1

    def on_complete(self, key):
        if key in (BUTTON_RIGHT, BUTTON_SELECT):
            if self.li + 1 < LEVEL_COUNT:
                self.enter_level(self.li + 1)
            else:
                self.go("certificate", 1)
        elif key in (BUTTON_LEFT, BUTTON_BACK):
            self.go("map", -1, self.li)

    def on_certificate(self, key):
        if key in (BUTTON_SELECT, BUTTON_LEFT, BUTTON_BACK, BUTTON_RIGHT):
            self.go("title", -1, 0)

    # -- drawing
    def draw(self):
        screen.pen = BG
        screen.clear()
        getattr(self, "draw_" + self.mode)()
        if self.flash and now() - self.flash_t < 1600:
            self.draw_flash()

    def draw_flash(self):
        w = measure(self.flash, F_BODY) + 24
        y = FOOTER_Y - 30
        rrect(W / 2 - w / 2, y, w, 22, 6, PANEL_2)
        rrect_line(W / 2 - w / 2, y, w, 22, 6, WARN)
        text_c(self.flash, y + 5, F_BODY, BRIGHT)

    def draw_header(self, left, right="", accent=ACCENT, frac=None):
        rect(0, 0, W, HEADER_H, PANEL)
        dot(MX + 3, HEADER_H / 2, 3, accent)
        text(left, MX + 12, 7, F_SMALL, TEXT)
        if right:
            text_r(right, W - MX, 7, F_SMALL, DIM)
        rect(0, HEADER_H, W, 2, LINE)
        if frac is not None:
            dt = min(badge.ticks_delta, 100) / 1000
            self.bar += (frac - self.bar) * min(1.0, dt * 10)
            rect(0, HEADER_H, W * self.bar, 2, accent)

    def draw_footer(self, left=None, right=None, right_pen=ACCENT):
        rect(MX, FOOTER_Y, TEXT_W, 1, LINE)
        y = FOOTER_Y + 6
        if left:
            chevron(MX + 2, y + 5, (-1, 0), DIM)
            text(left, MX + 9, y, F_SMALL, DIM)
        if right:
            w = measure(right, F_SMALL)
            text(right, W - MX - 9 - w, y, F_SMALL, right_pen)
            chevron(W - MX - 2, y + 5, (1, 0), right_pen)

    def level_header(self, right=""):
        lv = C.LEVELS[self.li]
        self.draw_header("LEVEL %d  %s" % (self.li + 1, lv["short"].upper()), right,
                         LEVEL_PENS[self.li], self.level_fraction())

    # title
    def draw_title(self):
        t = now()
        # soft vertical glow
        for i in range(6):
            rect(0, 20 + i * 14, W, 14, color.rgb(16 + i, 22 + i, 31 + i * 2))
        self.draw_ballot_box(W / 2, 76, (t % 2600) / 1400)
        text_c("CIVIC QUEST", 104, F_BIG, BRIGHT)
        text_c("A field guide to elections in " + C.COUNTRY, 136, F_SMALL, DIM)
        items = self.title_items()
        for i, (label, _a) in enumerate(items):
            y = 156 + i * 21
            if i == self.cursor:
                w = measure(label, F_BODY) + 36
                rrect(W / 2 - w / 2, y - 3, w, 19, 6, PANEL_2)
                rrect_line(W / 2 - w / 2, y - 3, w, 19, 6, ACCENT)
                chevron(W / 2 - w / 2 + 10, y + 6, (1, 0), ACCENT)
                text_c(label, y, F_BODY, BRIGHT)
            else:
                text_c(label, y, F_BODY, DIM)
        text_c("UP/DOWN move    SELECT choose", H - 14, F_SMALL, LINE)

    def draw_ballot_box(self, cx, base, phase):
        # paper drops into the slot, then pauses
        drop = ease(clamp(phase, 0, 1))
        alpha = 255 if phase < 1.2 else int(255 * clamp(1 - (phase - 1.2) * 4, 0, 1))
        py = base - 62 + drop * 34
        if alpha > 0:
            rrect(cx - 13, py, 26, 30, 2, color.rgb(238, 235, 226, alpha))
            rect(cx - 8, py + 7, 16, 2, color.rgb(110, 115, 120, alpha))
            rect(cx - 8, py + 12, 11, 2, color.rgb(110, 115, 120, alpha))
            icon_check(cx + 5, py + 21, 4, color.rgb(88, 166, 255, alpha))
        rrect(cx - 34, base - 30, 68, 30, 4, PANEL_2)
        rrect_line(cx - 34, base - 30, 68, 30, 4, LINE)
        rect(cx - 34, base - 34, 68, 6, PANEL)
        rect(cx - 16, base - 32, 32, 3, BG)
        icon_star(cx, base - 14, 7, ACCENT)

    # reset
    def draw_reset(self):
        self.draw_header("RESET PROGRESS")
        ox = self.offset()
        text("Erase level progress?", MX + ox, BODY_TOP + 6, F_H, BRIGHT)
        y = BODY_TOP + 34
        for line in wrap("This clears completed levels and knowledge scores on this badge. Nothing else is stored.", TEXT_W, F_BODY):
            text(line, MX + ox, y, F_BODY, TEXT)
            y += LH_B
        for i, label in enumerate(("Keep my progress", "Erase progress")):
            by = 132 + i * 30
            sel = i == self.cursor
            rrect(MX + ox, by, TEXT_W, 24, 6, PANEL_2 if sel else PANEL)
            if sel:
                rrect_line(MX + ox, by, TEXT_W, 24, 6, WARN if i else ACCENT)
            text(label, MX + 14 + ox, by + 6, F_BODY, BRIGHT if sel else DIM)
        self.draw_footer("Title", "SELECT confirm")

    # map
    def draw_map(self):
        done_count = sum(1 for d in progress["done"] if d)
        self.draw_header("LEVEL MAP", "%d/%d complete" % (done_count, LEVEL_COUNT))
        ox = self.offset()
        row_h = 29
        top = BODY_TOP - 4
        for i in range(LEVEL_COUNT + 1):
            y = top + i * row_h
            sel = i == self.cursor
            if sel:
                rrect(MX - 6 + ox, y, TEXT_W + 12, row_h - 3, 6, PANEL_2)
            cx = MX + 10 + ox
            cy = y + (row_h - 3) / 2
            if i < LEVEL_COUNT:
                pen = LEVEL_PENS[i]
                done = progress["done"][i]
                open_ = unlocked(i)
                if done:
                    dot(cx, cy, 9, pen)
                    icon_check(cx, cy, 4, BG)
                elif open_:
                    dot(cx, cy, 9, pen)
                    dot(cx, cy, 7, PANEL_2 if sel else BG)
                    text_c(str(i + 1), cy - 6, F_SMALL, BRIGHT, cx)
                else:
                    dot(cx, cy, 9, LINE)
                    icon_lock(cx, cy, DIM)
                title = C.LEVELS[i]["title"]
                text(title, MX + 28 + ox, y + 2, F_BODY, BRIGHT if open_ else DIM)
                if done:
                    sub = C.RANKS[i]
                elif open_:
                    sub = "Ready"
                else:
                    sub = "Locked"
                text(sub, MX + 28 + ox, y + 15, F_SMALL, pen if done else DIM)
                if done:
                    n = stars_for(progress["best"][i], total_questions(i))
                    for s in range(3):
                        icon_star(W - MX - 44 + s * 15 + ox, cy, 6, GOLD if s < n else LINE, s < n)
            else:
                ready = all_done()
                dot(cx, cy, 9, GOLD if ready else LINE)
                icon_star(cx, cy, 6, BG if ready else DIM)
                text("Civic Ready certificate", MX + 28 + ox, y + 2, F_BODY, BRIGHT if ready else DIM)
                text("Unlocked" if ready else "Complete all levels", MX + 28 + ox, y + 15, F_SMALL,
                     GOLD if ready else DIM)
            if sel:
                rect(MX - 6 + ox, y + 4, 2, row_h - 11, ACCENT)
        self.draw_footer("Title", "SELECT open")

    # level
    def draw_level(self):
        getattr(self, "draw_" + self.step_kind())()

    def draw_rows(self, rows, ox, accent_pen):
        for kind, x, y, line, extra in rows:
            yy = BODY_TOP + y
            xx = x + ox
            if kind == "h":
                text(line, xx, yy, F_H, accent_pen or BRIGHT)
            elif kind == "p":
                text(line, xx, yy, F_BODY, TEXT)
            elif kind in ("plus", "minus"):
                if extra:
                    icon_sign(MX + 6 + ox, yy + 6, kind)
                text(line, xx, yy, F_BODY, TEXT)
            elif kind == "note":
                if extra:
                    rect(MX + ox, yy - 1, 2, extra, accent_pen or ACCENT)
                text(line, xx, yy, F_SMALL, DIM)
            elif kind == "kvl":
                text(line.upper(), xx, yy, F_SMALL, DIM)
            elif kind == "kv":
                text(line, xx, yy, F_BODY, BRIGHT)

    def draw_read(self):
        pages = self.steps[self.step_i][1]
        page = pages[self.page]
        self.level_header("%d/%d" % (self.page + 1, len(pages)))
        accent = page.get("accent")
        accent_pen = PLATFORM_PENS[accent] if accent is not None else None
        ox = self.offset()
        if accent_pen:
            rect(0, BODY_TOP - 4, 4, rows_bottom(page["rows"]) + 8, accent_pen)
        self.draw_rows(page["rows"], ox, accent_pen)
        can_back = self.page > 0 or self.step_i == 0 or self.steps[self.step_i - 1][0] == "read"
        back = "Map" if (self.page == 0 and self.step_i == 0) else "Prev"
        last = self.page == len(pages) - 1
        self.draw_footer(back if can_back else None, "Continue" if last else "Next")
        if len(pages) > 1:
            n = len(pages)
            x0 = W / 2 - (n - 1) * 5
            for i in range(n):
                dot(x0 + i * 10, FOOTER_Y + 11, 2.5 if i == self.page else 1.5,
                    BRIGHT if i == self.page else LINE)

    def draw_quiz(self):
        questions = self.steps[self.step_i][1]
        self.level_header("Q %d/%d" % (self.qi + 1, len(questions)))
        if self.phase == "feedback":
            self.draw_feedback(questions[self.qi])
            return
        lay = quiz_layout(self.li, self.step_i, self.qi)
        ox = self.offset()
        y = BODY_TOP
        for line in lay["qlines"]:
            text(line, MX + ox, y, lay["qf"], BRIGHT)
            y += lay["qlh"]
        box_x = MX + ox
        target = None
        for i, (by, bh, lines) in enumerate(lay["boxes"]):
            if i == self.choice:
                target = by
        dt = min(badge.ticks_delta, 100) / 1000
        if self.hl_y is None:
            self.hl_y = target
        self.hl_y += (target - self.hl_y) * min(1.0, dt * 18)
        sel_h = lay["boxes"][self.choice][1]
        for i, (by, bh, lines) in enumerate(lay["boxes"]):
            rrect(box_x, BODY_TOP + by, TEXT_W, bh, 6, PANEL)
        rrect(box_x, BODY_TOP + self.hl_y, TEXT_W, sel_h, 6, PANEL_2)
        rrect_line(box_x, BODY_TOP + self.hl_y, TEXT_W, sel_h, 6, LEVEL_PENS[self.li], 1.5)
        for i, (by, bh, lines) in enumerate(lay["boxes"]):
            sel = i == self.choice
            cy = BODY_TOP + by + bh / 2
            dot(box_x + 13, cy, 8, LEVEL_PENS[self.li] if sel else LINE)
            text_c("ABC"[i], cy - 6, F_SMALL, BG if sel else TEXT, box_x + 13)
            ty = BODY_TOP + by + 5
            for line in lines:
                text(line, box_x + 28, ty, lay["of"], BRIGHT if sel else TEXT)
                ty += lay["olh"]
        self.draw_footer(None, "SELECT answer", DIM)
        text("UP/DOWN choose", MX, FOOTER_Y + 6, F_SMALL, DIM)

    def draw_feedback(self, qd):
        lay = quiz_layout(self.li, self.step_i, self.qi, feedback=True)
        ox = self.offset()
        ok = self.last_correct
        pen = GOOD if ok else WARN
        pop = ease((now() - self.t_enter) / 300)
        dot(MX + 12 + ox, BODY_TOP + 12, 4 + 8 * pop, pen)
        if ok:
            icon_check(MX + 12 + ox, BODY_TOP + 12, 5 * pop, BG)
        else:
            rect(MX + 11 + ox, BODY_TOP + 5, 2, 9 * pop, BG)
            rect(MX + 11 + ox, BODY_TOP + 16, 2, 2 * pop, BG)
        text("Correct" if ok else "Not quite", MX + 30 + ox, BODY_TOP + 4, F_H, pen)
        text("ANSWER", MX + ox, BODY_TOP + 28, F_SMALL, DIM)
        top = BODY_TOP + 40
        rrect(MX + ox, top, TEXT_W, lay["answer_h"], 6, PANEL)
        rect(MX + ox, top + 4, 2, lay["answer_h"] - 8, GOOD)
        y = top + 5
        for line in lay["answer"]:
            text(line, MX + 12 + ox, y, F_BODY, BRIGHT)
            y += LH_B
        y = BODY_TOP + lay["why_top"]
        for line in lay["why"]:
            text(line, MX + ox, y, F_BODY, TEXT)
            y += LH_B
        text("Score %d/%d" % (self.correct, self.answered), MX, FOOTER_Y + 6, F_SMALL, DIM)
        self.draw_footer(None, "Next")

    def draw_explore(self):
        self.level_header("Seen %d/12" % len(self.seen))
        ox = self.offset()
        tab_w = (TEXT_W - 12) / 3
        for p in range(3):
            x = MX + p * (tab_w + 6)
            pen = PLATFORM_PENS[p]
            label = "Platform " + C.PLATFORMS[p]
            if p == self.ex_plat:
                rrect(x, BODY_TOP - 2, tab_w, 20, 6, pen)
                text_c(label, BODY_TOP + 2, F_SMALL, BG, x + tab_w / 2)
            else:
                rrect_line(x, BODY_TOP - 2, tab_w, 20, 6, pen)
                text_c(label, BODY_TOP + 2, F_SMALL, pen, x + tab_w / 2)
        issue = C.ISSUES[self.ex_issue]
        iy = BODY_TOP + 24
        text(issue, MX + ox, iy, F_H, BRIGHT)
        text_r("%d/4" % (self.ex_issue + 1), W - MX - 16, iy + 3, F_SMALL, DIM)
        chevron(W - MX - 5, iy + 3, (0, -1), DIM)
        chevron(W - MX - 5, iy + 12, (0, 1), DIM)
        lay = proposal_layout(self.ex_plat, self.ex_issue)
        pen = PLATFORM_PENS[self.ex_plat]
        rrect(MX + ox, CARD_Y, TEXT_W, CARD_H, 6, PANEL)
        rect(MX + ox, CARD_Y + 6, 3, CARD_H - 12, pen)
        y = CARD_Y + 8
        x = MX + 12 + ox
        for line in lay["plan"]:
            text(line, x, y, F_BODY, BRIGHT)
            y += LH_B
        y += 7
        for kind, lines in (("plus", lay["gain"]), ("minus", lay["cost"])):
            icon_sign(x + 5, y + 6, kind)
            for line in lines:
                text(line, x + 16, y, lay["f"], TEXT)
                y += lay["lh"]
            y += 5
        # mini map of seen cards
        gx = W / 2 - 16
        for i in range(4):
            for p in range(3):
                cx = gx + p * 11
                cy = FOOTER_Y + 4 + i * 4
                cur = (i, p) == (self.ex_issue, self.ex_plat)
                rect(cx, cy, 9, 3, BRIGHT if cur else PLATFORM_PENS[p] if (i, p) in self.seen else LINE)
        if len(self.seen) >= 12:
            self.draw_footer(None, "SELECT continue")
            text("Arrows explore", MX, FOOTER_Y + 6, F_SMALL, DIM)
        else:
            self.draw_footer(None, "SELECT next unseen", DIM)
            text("Arrows explore", MX, FOOTER_Y + 6, F_SMALL, DIM)

    def draw_reveal(self):
        self.level_header("The reveal")
        t = now() - self.reveal_t
        card_w = (TEXT_W - 16) / 3
        card_h = 128
        top = BODY_TOP + 4
        for i in range(3):
            pen = PLATFORM_PENS[i]
            k = clamp((t - i * 350) / 500, 0, 1)
            scale = abs(math.cos(math.pi * k))
            cx = MX + i * (card_w + 8) + card_w / 2
            w = max(2, card_w * scale)
            x = cx - w / 2
            if k < 0.5:
                rrect(x, top, w, card_h, 8, PANEL_2)
                rrect_line(x, top, w, card_h, 8, pen, 1.5)
                if scale > 0.7:
                    text_c("?", top + 40, F_BIG, pen, cx)
                    text_c("Platform " + C.PLATFORMS[i], top + card_h - 22, F_SMALL, DIM, cx)
            else:
                cand = C.CANDIDATES[i]
                rrect(x, top, w, card_h, 8, PANEL_2)
                rrect(x, top, w, 26, 8, pen)
                rect(x, top + 18, w, 8, pen)
                if scale > 0.7:
                    text_c("Platform " + C.PLATFORMS[i], top + 7, F_SMALL, BG, cx)
                    dot(cx, top + 50, 17, PANEL)
                    dot(cx, top + 50, 15, pen)
                    text_c(cand["first"][0] + cand["last"][0], top + 43, F_H, BG, cx)
                    text_c(cand["first"], top + 76, F_BODY, BRIGHT, cx)
                    text_c(cand["last"], top + 92, F_BODY, BRIGHT, cx)
                    text_c("Fictional", top + card_h - 18, F_SMALL, DIM, cx)
        if self.reveal_done():
            text_c("Same ideas you explored.", top + card_h + 10, F_BODY, TEXT)
            text_c("Now meet the people behind them.", top + card_h + 26, F_BODY, TEXT)
            self.draw_footer(None, "Continue")
        else:
            self.draw_footer(None, "SELECT skip", DIM)

    def draw_ballot(self):
        self.level_header("Secret ballot")
        ox = self.offset()
        if self.ballot_phase == "cast":
            self.draw_cast(ox)
            return
        px, py, pw = MX + ox, BODY_TOP - 2, TEXT_W
        rows = len(C.CANDIDATES) + 1
        row_h = 23
        ph = 36 + rows * row_h + 4
        rrect(px, py, pw, ph, 4, PAPER)
        text_c("PRACTICE BALLOT", py + 5, F_SMALL, INK, W / 2 + ox)
        text_c("Leader of %s: mark one or leave blank" % C.COUNTRY, py + 19, F_SMALL, INK_DIM, W / 2 + ox)
        rect(px + 8, py + 33, pw - 16, 1, INK_DIM)
        for r in range(rows):
            y = py + 36 + r * row_h
            sel = r == self.ballot_cursor
            if sel:
                rrect(px + 4, y + 1, pw - 8, row_h - 2, 4, color.rgb(214, 226, 240))
            cx = px + 20
            cy = y + row_h / 2
            screen.pen = INK
            screen.shape(shape.circle(cx, cy, 6).stroke(1.5))
            if self.ballot_mark == r:
                dot(cx, cy, 4, INK)
            if r < len(C.CANDIDATES):
                ci = self.ballot_order[r]
                text(C.CANDIDATES[ci]["name"], px + 34, y + 5, F_BODY, INK)
                text_r("Platform " + C.PLATFORMS[ci], px + pw - 10, y + 6, F_SMALL, INK_DIM)
            else:
                text("Leave blank", px + 34, y + 5, F_BODY, INK_DIM)
        by = py + ph + 6
        sel = self.ballot_cursor == rows
        rrect(px, by, pw, 22, 6, ACCENT if sel else PANEL_2)
        text_c("Cast ballot", by + 5, F_BODY, BG if sel else TEXT, W / 2 + ox)
        text("Never saved or scored", MX, FOOTER_Y + 6, F_SMALL, DIM)
        self.draw_footer(None, "SELECT mark", DIM)

    def draw_cast(self, ox):
        t = (now() - self.cast_t) / 900
        self.draw_ballot_box(W / 2 + ox, 104, min(t, 1.0))
        if t >= 1:
            pop = ease((t - 1) * 3)
            text_c("Ballot cast", 116, F_H, color.rgb(240, 246, 252, int(255 * pop)))
            y = 142
            for line in wrap("Your choice stays private: it was not saved or scored. In real elections, officials count ballots and check the results.", TEXT_W, F_BODY):
                text_c(line, y, F_BODY, TEXT)
                y += LH_B
            self.draw_footer(None, "Continue")

    # complete
    def draw_complete(self):
        li = self.li
        pen = LEVEL_PENS[li]
        self.draw_header("LEVEL %d COMPLETE" % (li + 1), C.LEVELS[li]["title"], pen)
        t = now() - self.complete_t
        pop = ease(t / 400)
        cx = W / 2
        dot(cx, 70, 30 * pop + 1, pen)
        dot(cx, 70, 24 * pop + 1, PANEL_2)
        icon_star(cx, 70, 16 * pop + 1, pen)
        total = total_questions(li)
        n = stars_for(self.correct, total)
        for s in range(3):
            k = ease((t - 400 - s * 180) / 250)
            filled = s < n and k > 0
            icon_star(cx - 24 + s * 24, 120, 5 + 4 * (k if s < n else 1), GOLD if filled else LINE, filled)
        text_c("RANK EARNED", 138, F_SMALL, DIM)
        text_c(C.RANKS[li], 152, F_H, BRIGHT)
        text_c("Knowledge: %d of %d correct" % (self.correct, total), 176, F_BODY, TEXT)
        if li + 1 < LEVEL_COUNT:
            nxt = "Level %d" % (li + 2)
        else:
            nxt = "Graduate"
        self.draw_footer("Map", nxt)

    # certificate
    def draw_certificate(self):
        self.draw_header("CERTIFICATE", "Meridia civics", GOLD)
        ox = self.offset()
        x, y, w, h = MX + ox, BODY_TOP - 2, TEXT_W, BODY_BOTTOM - BODY_TOP + 4
        rrect(x, y, w, h, 8, PANEL)
        rrect_line(x + 3, y + 3, w - 6, h - 6, 6, GOLD, 1)
        cx = W / 2 + ox
        text_c("THIS CERTIFIES A", y + 10, F_SMALL, DIM, cx)
        text_c("Civic Ready", y + 24, F_BIG, GOLD, cx)
        ly = y + 58
        for line in wrap("You learned how elections work, weighed tradeoffs, checked claims and cast a secret practice ballot.", w - 28, F_BODY):
            text_c(line, ly, F_BODY, TEXT, cx)
            ly += LH_B
        score = sum(progress["best"])
        total = sum(total_questions(i) for i in range(LEVEL_COUNT))
        text_c("Knowledge score %d/%d" % (score, total), ly + 6, F_BODY, BRIGHT, cx)
        for i in range(LEVEL_COUNT):
            icon_star(cx - 40 + i * 20, ly + 34, 6, LEVEL_PENS[i])
        text_c("Keep learning. Respect every voter.", y + h - 18, F_SMALL, DIM, cx)
        self.draw_footer(None, "Title")


def next_level():
    for i in range(LEVEL_COUNT):
        if not progress["done"][i]:
            return i
    return None


game = Game()


def update():
    game.update()
    game.draw()


run(update)
