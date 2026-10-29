"""Full-screen hydration reminder scene for the Hydrate Yourself app.

Usage from the app (Mona is loaded once by the caller):

    from hydration_scene import draw_hydration_scene
    draw_hydration_scene(mona, badge.ticks, area_text)

The function only draws one frame and never blocks or reads input.
"""

import math

SKY_TOP = color.rgb(14, 40, 78)
SKY_GLOW = color.rgb(30, 86, 140, 90)
WAVE_BACK = color.rgb(40, 120, 200)
WAVE_MID = color.rgb(28, 163, 236, 210)
WAVE_FRONT = color.rgb(116, 204, 244, 170)
FOAM = color.rgb(220, 244, 255, 200)
WHITE = color.rgb(255, 255, 255)
SHADOW = color.rgb(0, 0, 0, 120)
HINT_BG = color.rgb(8, 30, 60, 170)
DROP = color.rgb(150, 220, 255)

# (base height as a fraction of the screen, amplitude, wavelength, speed px/s, colour)
_LAYERS = (
    (0.62, 0.035, 0.55, 18, WAVE_BACK),
    (0.72, 0.030, 0.40, -28, WAVE_MID),
    (0.84, 0.025, 0.30, 40, WAVE_FRONT),
)

_STEPS = 24


def _wave(ticks, base, amp, wavelength, speed, pen, w, h):
    seconds = ticks / 1000
    y0 = h * base
    a = h * amp
    k = (2 * math.pi) / (w * wavelength)
    offset = seconds * speed
    phase2 = seconds * 1.3
    points = []
    for i in range(_STEPS + 1):
        x = w * i / _STEPS
        y = y0 + math.sin((x + offset) * k) * a + math.sin(x * k * 0.5 + phase2) * a * 0.4
        points.append(vec2(x, y))
    crest = points[:]
    points.append(vec2(w, h))
    points.append(vec2(0, h))
    screen.pen = pen
    screen.shape(shape.custom(points))
    return crest


def _foam(crest, ticks):
    screen.pen = FOAM
    stroke = max(1, screen.height / 120)
    screen.shape(shape.custom(crest).stroke(stroke, shape.ALIGN_CENTER | shape.PATH_OPEN))
    for i in range(0, len(crest), 4):
        p = crest[i]
        if math.sin(ticks / 260 + i) > 0.2:
            screen.shape(shape.circle(p.x, p.y - 2, stroke * 1.2))


def _centred_text(text, y, pen):
    w, _ = screen.measure_text(text)
    x = (screen.width - w) / 2
    screen.pen = SHADOW
    screen.text(text, x + 1, y + 1)
    screen.pen = pen
    screen.text(text, x, y)


def _droplets(ticks, w, h):
    screen.pen = DROP
    r = max(1.5, h / 80)
    for i in range(5):
        t = ((ticks / 1600) + i * 0.2) % 1
        x = w * (0.12 + 0.19 * i)
        y = h * (0.2 + t * 0.4)
        screen.shape(shape.circle(x, y, r))
        screen.shape(shape.regular_polygon(x, y - r * 1.2, r * 0.75, 3))


def draw_hydration_scene(
    mona, ticks, area_text=None,
    hint="SELECT: I drank water | BACK: skip", skip_level=0,
):
    """Draw one full-screen frame of the hydration reminder.

    mona: image loaded by the caller (e.g. image.load("assets/mona.png")).
    ticks: frame time in milliseconds (badge.ticks).
    area_text: optional short line shown under the title.
    hint: control hint drawn in the bottom bar; pass None to hide it.
    skip_level: consecutive skips (0 to 3); fractional values animate the rise.
    """
    w = screen.width
    h = screen.height
    ticks = ticks or 0
    water_rise = min(3, max(0, skip_level)) * 0.21

    screen.antialias = image.X4
    screen.fill_rule = image.EVEN_ODD

    screen.pen = SKY_TOP
    screen.clear()
    screen.pen = SKY_GLOW
    screen.shape(shape.circle(w / 2, h * 0.45, h * 0.42))
    _droplets(ticks, w, h)

    base, amp, wavelength, speed, pen = _LAYERS[0]
    _wave(ticks, base - water_rise, amp, wavelength, speed, pen, w, h)

    # Mona fills most of the height and bobs with the water
    if mona is not None:
        mw = max(1, mona.width)
        mh = max(1, mona.height)
        scale = min((h * 0.62) / mh, (w * 0.6) / mw)
        dw = mw * scale
        dh = mh * scale
        bob = math.sin(ticks / 450) * h * 0.02
        sway = math.sin(ticks / 900) * w * 0.01
        dx = (w - dw) / 2 + sway
        dy = h * 0.86 - dh + bob
        screen.blit(mona, rect(int(dx), int(dy), int(dw), int(dh)))

    base, amp, wavelength, speed, pen = _LAYERS[1]
    _wave(ticks, base - water_rise, amp, wavelength, speed, pen, w, h)
    base, amp, wavelength, speed, pen = _LAYERS[2]
    crest = _wave(ticks, base - water_rise, amp, wavelength, speed, pen, w, h)
    _foam(crest, ticks)
    if skip_level >= 3:
        screen.pen = FOAM
        for i in range(4):
            phase = (ticks / 1900 + i / 4) % 1
            screen.shape(shape.circle(
                w * (0.43 + 0.05 * math.sin(i + ticks / 700)),
                h * (0.65 - phase * 0.36),
                max(2, h / 65),
            ).stroke(1))

    screen.font = font.smart
    pulse = (math.sin(ticks / 300) + 1) / 2
    title = "Mona is underwater!" if skip_level >= 3 else "Time to hydrate!"
    _centred_text(title, h * 0.04, color.rgb(255, 255, int(200 + 55 * pulse)))
    screen.font = font.nope
    if area_text:
        _, th = screen.measure_text("Ag")
        _centred_text(str(area_text), h * 0.04 + th + 1, WHITE)

    if hint:
        _, hh = screen.measure_text(hint)
        bar_h = hh + 4
        screen.pen = HINT_BG
        screen.shape(shape.rectangle(0, h - bar_h, w, bar_h))
        _centred_text(hint, h - bar_h + 2, WHITE)
