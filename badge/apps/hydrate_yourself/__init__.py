"""Estimate steps and log hydration breaks at GHU infrared beacons."""
import os
import sys

APP_DIR = "/system/apps/hydrate_yourself"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from math import sqrt

from badgeware import State
from hydration_scene import draw_hydration_scene

try:
    from aye_arr.nec import NECReceiver
    from aye_arr.nec.remotes.descriptor import RemoteDescriptor
except ImportError:
    IR_AVAILABLE = False
else:
    IR_AVAILABLE = True

    class GithubUniverseBeacon(RemoteDescriptor):
        NAME = "GithubUniverseBeacon"
        ADDRESS = 0x45
        BUTTON_CODES = {
            1: 0x11,
            2: 0x22,
            3: 0x33,
            4: 0x44,
            5: 0x55,
            6: 0x66,
            7: 0x77,
            8: 0x88,
            9: 0x99,
        }

        def __init__(self):
            super().__init__()

DEFAULT_HEIGHT_CM = 165
DEFAULT_HYDRATION_INTERVAL = 500
SAVE_INTERVAL = 25
BEACON_FRESH_MS = 60000
MIN_HEIGHT_CM = 100
MAX_HEIGHT_CM = 220
MIN_HYDRATION_INTERVAL = 100
MAX_HYDRATION_INTERVAL = 5000

LOCATIONS = (
    "Hack Your Badge",
    "Whats up Docs",
    "Stars Lounge",
    "GitHub Next",
    "Open Source Zone",
    "Demos & Donuts",
    "GitHub Learn",
    "Octocat Generator",
    "Makerspace",
)

BG = color.rgb(13, 17, 23)
PANEL = color.rgb(22, 27, 34)
TEXT = color.rgb(240, 246, 252)
MUTED = color.rgb(139, 148, 158)
ACCENT = color.rgb(63, 185, 80)
WATER = color.rgb(88, 166, 255)

badge.mode(HIRES | VSYNC)
screen.font = font.nope
mona = image.load("assets/mona.png")

state = {
    "steps": 0,
    "next_hydration": DEFAULT_HYDRATION_INTERVAL,
    "hydrations": [],
    "height_cm": DEFAULT_HEIGHT_CM,
    "hydration_interval": DEFAULT_HYDRATION_INTERVAL,
    "configured": False,
    "skipped_reminders": 0,
    "reminder_active": False,
}
State.load("step_tracker", state)

step_count = state.get("steps", 0)
if type(step_count) is not int or step_count < 0:
    step_count = 0

height_cm = state.get("height_cm", DEFAULT_HEIGHT_CM)
if type(height_cm) is not int or not MIN_HEIGHT_CM <= height_cm <= MAX_HEIGHT_CM:
    height_cm = DEFAULT_HEIGHT_CM

hydration_interval = state.get(
    "hydration_interval", DEFAULT_HYDRATION_INTERVAL
)
if (
    type(hydration_interval) is not int
    or not MIN_HYDRATION_INTERVAL <= hydration_interval <= MAX_HYDRATION_INTERVAL
):
    hydration_interval = DEFAULT_HYDRATION_INTERVAL

next_hydration = state.get("next_hydration", hydration_interval)
if type(next_hydration) is not int or next_hydration <= step_count:
    next_hydration = (step_count // hydration_interval + 1) * hydration_interval

hydrations = []
saved_hydrations = state.get("hydrations", [])
if type(saved_hydrations) is list:
    for item in saved_hydrations[-5:]:
        if (
            type(item) is dict
            and type(item.get("steps")) is int
            and type(item.get("location")) is str
        ):
            hydrations.append(item)

skipped_reminders = state.get("skipped_reminders", 0)
if type(skipped_reminders) is not int or not 0 <= skipped_reminders <= 3:
    skipped_reminders = 0

state = {
    "steps": step_count,
    "next_hydration": next_hydration,
    "hydrations": hydrations,
    "height_cm": height_cm,
    "hydration_interval": hydration_interval,
    "configured": state.get("configured", False) is True,
    "skipped_reminders": skipped_reminders,
    "reminder_active": state.get("reminder_active", False) is True,
}
setup_page = 0 if state["configured"] else 1
setup_height_cm = height_cm
setup_hydration_interval = hydration_interval
reminder_active = state["reminder_active"]
feedback_until = 0
skip_animation_start = None
skip_animation_from = skipped_reminders
last_beacon_location = None
last_beacon_ticks = -BEACON_FRESH_MS
last_saved_steps = step_count

gravity_baseline = None
in_step_swing = False
last_step_tick = -1000


def save_state():
    global last_saved_steps
    state["steps"] = step_count
    state["next_hydration"] = next_hydration
    state["hydrations"] = hydrations
    state["height_cm"] = height_cm
    state["hydration_interval"] = hydration_interval
    state["configured"] = True
    state["skipped_reminders"] = skipped_reminders
    state["reminder_active"] = reminder_active
    State.save("step_tracker", state)
    last_saved_steps = step_count


def sample_motion(ax, ay, az, ticks, delta_ms):
    global gravity_baseline, in_step_swing, last_step_tick
    global step_count, next_hydration, reminder_active

    magnitude = sqrt(ax * ax + ay * ay + az * az)
    if gravity_baseline is None:
        gravity_baseline = magnitude
        return

    threshold = max(0.03, gravity_baseline * 0.10)
    deviation = abs(magnitude - gravity_baseline)

    if not in_step_swing:
        alpha = min(0.05, max(0.001, delta_ms / 5000.0))
        gravity_baseline += (magnitude - gravity_baseline) * alpha
        if deviation > threshold:
            in_step_swing = True
        return

    if deviation <= threshold * 0.4:
        in_step_swing = False
        if ticks - last_step_tick >= 280:
            step_count += 1
            last_step_tick = ticks
            if step_count >= next_hydration:
                reminder_active = True
                next_hydration += hydration_interval
                save_state()
            elif step_count - last_saved_steps >= SAVE_INTERVAL:
                save_state()


def current_location(ticks):
    if (
        last_beacon_location is not None
        and ticks - last_beacon_ticks <= BEACON_FRESH_MS
    ):
        return last_beacon_location
    return "Unknown area"


def receive_beacon(location_id):
    global last_beacon_location, last_beacon_ticks
    if 1 <= location_id <= len(LOCATIONS):
        last_beacon_location = LOCATIONS[location_id - 1]
        last_beacon_ticks = badge.ticks


receiver = None
if IR_AVAILABLE:
    beacon = GithubUniverseBeacon()
    beacon.on_known = receive_beacon
    receiver = NECReceiver(17, 0, 0)
    receiver.bind(beacon)
    receiver.start()


def record_hydration():
    global skipped_reminders, reminder_active
    location = current_location(badge.ticks)
    hydrations.append({"steps": step_count, "location": location})
    hydrations[:] = hydrations[-5:]
    skipped_reminders = 0
    reminder_active = False
    save_state()


def skip_reminder():
    global skipped_reminders, reminder_active, feedback_until
    global skip_animation_start, skip_animation_from
    skip_animation_from = skipped_reminders
    skipped_reminders = min(3, skipped_reminders + 1)
    reminder_active = False
    skip_animation_start = badge.ticks
    feedback_until = badge.ticks + 2200
    save_state()


def draw_text(text, x, y, pen):
    screen.pen = pen
    screen.text(text, x, y)


def draw_mona(size=64, right_margin=16, bottom_margin=8):
    x = screen.width - right_margin - size
    y = screen.height - bottom_margin - size
    screen.blit(
        mona,
        rect(x, y, -size, size),
    )


def draw_main(ticks):
    screen.pen = BG
    screen.rectangle(0, 0, screen.width, screen.height)
    draw_text("HYDRATE YOURSELF", 18, 12, TEXT)
    draw_mona(size=96, right_margin=4)
    screen.font = font.nope
    tagline = "LET'S GO"
    tagline_width = screen.measure_text(tagline)[0]
    pill_width = tagline_width + 20
    pill_x = screen.width - 66 - pill_width
    screen.pen = WATER
    screen.shape(
        shape.rounded_rectangle(pill_x, 16, pill_width, 22, 6)
    )
    draw_text(tagline, pill_x + 10, 22, BG)
    draw_text("AREA: " + current_location(ticks), 18, 32, WATER)
    draw_text("STEPS", 18, 56, MUTED)

    screen.font = font.smart
    draw_text("%d" % step_count, 18, 70, ACCENT)
    screen.font = font.nope

    if skipped_reminders:
        draw_text("Skipped in a row: %d / 3" % skipped_reminders, 18, 110, WATER)
    distance_km = step_count * height_cm * 0.415 / 100000.0
    draw_text("~%.2f km | height %d cm" % (distance_km, height_cm), 18, 132, TEXT)
    draw_text("Next hydration: %d steps" % next_hydration, 18, 154, MUTED)

    progress = step_count % hydration_interval
    bar_width = screen.width - 130
    screen.pen = PANEL
    screen.shape(shape.rounded_rectangle(18, 174, bar_width, 8, 4))
    screen.pen = ACCENT
    screen.shape(
        shape.rounded_rectangle(
            18, 174, max(4, int(bar_width * progress / hydration_interval)), 8, 4
        )
    )

    draw_text("RECENT HYDRATION", 18, 190, MUTED)
    for item in hydrations[-1:]:
        line = "%d steps - %s" % (item["steps"], item["location"])
        if screen.measure_text(line)[0] > screen.width - 130:
            while screen.measure_text(line + "...")[0] > screen.width - 130:
                line = line[:-1]
            line += "..."
        draw_text(line, 18, 207, TEXT)
    draw_text("BACK: settings", 18, 224, MUTED)


def draw_setup(height_screen):
    screen.pen = BG
    screen.rectangle(0, 0, screen.width, screen.height)
    screen.pen = PANEL
    screen.shape(shape.rounded_rectangle(22, 30, screen.width - 44, 178, 12))

    screen.font = font.smart
    title = "YOUR SETTINGS" if height_screen else "HYDRATION REMINDER"
    width = screen.measure_text(title)[0]
    draw_text(title, (screen.width - width) // 2, 43, WATER)
    draw_mona()
    screen.font = font.nope

    if height_screen:
        draw_text("How tall are you?", 84, 88, TEXT)
        value = "%d cm" % setup_height_cm
    else:
        draw_text("Remind me every how many steps?", 54, 80, TEXT)
        value = "%d steps" % setup_hydration_interval

    screen.font = font.smart
    width = screen.measure_text(value)[0]
    draw_text(value, (screen.width - width) // 2, 112, ACCENT)
    screen.font = font.nope

    draw_text("UP / DOWN to change", 92, 161, MUTED)
    if height_screen:
        draw_text("SELECT: next", 119, 181, TEXT)
    else:
        draw_text("SELECT: save | BACK: height", 76, 181, TEXT)
    draw_text("SETUP %d / 2" % (1 if height_screen else 2), 22, 218, MUTED)


def draw_reminder():
    draw_hydration_scene(
        mona, badge.ticks, current_location(badge.ticks),
        skip_level=skipped_reminders,
    )
    screen.font = font.nope


def draw_confirmation():
    screen.pen = BG
    screen.rectangle(0, 0, screen.width, screen.height)
    draw_mona()
    screen.font = font.smart
    title = "HYDRATION LOGGED"
    width = screen.measure_text(title)[0]
    draw_text(title, (screen.width - width) // 2, 60, ACCENT)
    screen.font = font.nope

    if hydrations:
        item = hydrations[-1]
        detail = "%d steps - %s" % (item["steps"], item["location"])
        width = screen.measure_text(detail)[0]
        draw_text(detail, (screen.width - width) // 2, 116, TEXT)
    draw_text("Next reminder at %d steps" % next_hydration, 80, 148, MUTED)


def update():
    global reminder_active, feedback_until, setup_page, skip_animation_start
    global setup_height_cm, setup_hydration_interval
    global height_cm, hydration_interval, next_hydration

    if receiver is not None:
        receiver.decode()

    if setup_page:
        if setup_page == 1:
            if badge.pressed(BUTTON_UP):
                setup_height_cm = min(MAX_HEIGHT_CM, setup_height_cm + 1)
            elif badge.pressed(BUTTON_DOWN):
                setup_height_cm = max(MIN_HEIGHT_CM, setup_height_cm - 1)
            if badge.pressed(BUTTON_SELECT):
                setup_page = 2
            draw_setup(True)
        else:
            if badge.pressed(BUTTON_UP):
                setup_hydration_interval = min(
                    MAX_HYDRATION_INTERVAL, setup_hydration_interval + 100
                )
            elif badge.pressed(BUTTON_DOWN):
                setup_hydration_interval = max(
                    MIN_HYDRATION_INTERVAL, setup_hydration_interval - 100
                )
            if badge.pressed(BUTTON_BACK):
                setup_page = 1
            elif badge.pressed(BUTTON_SELECT):
                height_cm = setup_height_cm
                hydration_interval = setup_hydration_interval
                next_hydration = (
                    step_count // hydration_interval + 1
                ) * hydration_interval
                reminder_active = False
                save_state()
                setup_page = 0
            draw_setup(False)
        return

    ax, ay, az, _gx, _gy, _gz = badge.imu()
    sample_motion(ax, ay, az, badge.ticks, badge.ticks_delta)

    if skip_animation_start is not None and badge.ticks < feedback_until:
        progress = min(1.0, (badge.ticks - skip_animation_start) / 1000.0)
        level = skip_animation_from + (skipped_reminders - skip_animation_from) * progress
        draw_hydration_scene(
            mona, badge.ticks,
            "Skipped %d / 3 - next at %d steps" % (skipped_reminders, next_hydration),
            hint="Returning to your walk...",
            skip_level=level,
        )
        screen.font = font.nope
        return
    skip_animation_start = None

    if not reminder_active and badge.pressed(BUTTON_BACK):
        setup_height_cm = height_cm
        setup_hydration_interval = hydration_interval
        setup_page = 1
        draw_setup(True)
        return

    if reminder_active and badge.pressed(BUTTON_SELECT):
        record_hydration()
        feedback_until = badge.ticks + 1600
    elif reminder_active and badge.pressed(BUTTON_BACK):
        skip_reminder()
        draw_reminder()
        return

    if reminder_active:
        draw_reminder()
    elif badge.ticks < feedback_until:
        draw_confirmation()
    else:
        draw_main(badge.ticks)


def on_exit():
    if receiver is not None:
        receiver.stop()


badge.default_clear = BG
run(update)
