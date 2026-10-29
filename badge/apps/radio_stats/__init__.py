"""Anonymous radio-environment overview for the Universe 2026 badge."""

import os
import sys
import time


APP_DIR = "/system/apps/radio_stats"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from radio_core import ScanError, passive_snapshot

try:
    import network
except ImportError:
    network = None

badge.mode(HIRES | VSYNC)
screen.font = font.nope
screen.fill_rule = image.EVEN_ODD

BG = color.rgb(13, 17, 23)
FG = color.rgb(235, 245, 255)
MUTED = color.rgb(160, 174, 192)
ACCENT = color.rgb(211, 250, 55)
BAR = color.rgb(65, 185, 210)

stats = None
page = 0
pending = False
error = None
age_ms = 0
completed_at = None


def label(text, x, y, pen=FG):
    screen.pen = pen
    screen.text(text, x, y)


def draw_channels():
    label("Observed APs by channel", 12, 88, MUTED)
    counts = stats["channels"]
    peak = max(1, max(counts))
    step = (screen.width - 24) // 14
    baseline = screen.height - 65
    for index, count in enumerate(counts):
        x = 12 + index * step
        height = count * 42 // peak
        screen.pen = BAR
        screen.shape(shape.rectangle(x, baseline - height, step - 3, height))
        label(str(count), x, baseline - height - 12)
        label(str(index + 1), x, baseline + 5, MUTED)
    label("Unknown channel: %d" % stats["unknown_channel"], 12, baseline + 22, MUTED)


def draw_signals():
    descriptions = (">= -60 dBm", "-75 to -61 dBm", "< -75 dBm")
    for index, description in enumerate(descriptions):
        label(description, 12, 91 + index * 24, MUTED)
        label(str(stats["signals"][index]), screen.width - 48, 91 + index * 24, ACCENT)
    label("Unknown RSSI: %d" % stats["unknown_signal"], 12, 166, MUTED)
    strongest = stats["strongest"]
    label("Strongest: " + ("--" if strongest is None else "%d dBm" % strongest),
          12, 183, MUTED)


def draw():
    screen.pen = BG
    screen.rectangle(screen.clip)
    label("RADIO STATS", 12, 12, ACCENT)
    label("2.4 GHz / passive observations", 12, 31, MUTED)
    if pending:
        label("Listening for access points...", 12, 83)
        label("Controls pause during scan (up to 10s).", 12, 108, MUTED)
    elif error:
        label(error, 12, 77, ACCENT)
        if error == "Wi-Fi already in use":
            label("Existing radio left untouched.", 12, 104, MUTED)
            label("Retry after Wi-Fi is off.", 12, 125, MUTED)
        elif error == "Radio shutdown failed":
            label("Radio may still be enabled.", 12, 104, MUTED)
            label("Restart badge before retrying.", 12, 125, MUTED)
        else:
            label("No active-scan fallback.", 12, 104, MUTED)
            label("Matching badge firmware required.", 12, 125, MUTED)
    elif stats is None:
        label("How crowded is the neighborhood?", 12, 73)
        label("Select takes one passive snapshot.", 12, 102, MUTED)
        label("No names, addresses or traffic saved.", 12, 125, MUTED)
    else:
        label("%d APs observed / %ds ago" % (stats["total"], age_ms // 1000),
              12, 59, ACCENT)
        if page == 0:
            draw_channels()
        else:
            draw_signals()
    label("AP counts are NOT airtime or traffic.", 12, screen.height - 35, MUTED)
    label("SELECT scan   L/R view   HOME exit", 12, screen.height - 17)


def update():
    global stats, page, pending, error, age_ms, completed_at
    if pending:
        pending = False
        try:
            if network is None:
                raise ScanError("Wi-Fi API unavailable")
            stats = passive_snapshot(network)
            completed_at = time.ticks_ms()
            age_ms = 0
        except ScanError as failure:
            error = str(failure)
            print("Radio Stats: " + error)
    else:
        if stats is not None:
            age_ms = max(0, time.ticks_diff(time.ticks_ms(), completed_at))
        if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
            page = 1 - page
        if badge.pressed(BUTTON_SELECT):
            stats = None
            error = None
            pending = True
    # The listening card is presented one frame before the blocking driver call.
    draw()


run(update)
