# Hydrate Yourself testing and deployment

## What the simulator proves

The simulator exercises setup, drawing, animation, controls, milestone logic,
saved state within the runtime, and hydration logging. It does not prove
accelerometer accuracy, IR reception, battery consumption, or physical input
and display performance. Screenshots in this directory are simulator captures.

Open the Badge Simulator canvas with `app: "hydrate_yourself"`. Its `check_app`
action checks app structure. From the repository root on Windows, run:

```powershell
python .github\skills\hyb26-skill\scripts\validate_app.py badge\apps\hydrate_yourself
python .github\scripts\validate_app_readmes.py badge/apps
```

## Simulator acceptance checks

Use a fresh simulator runtime for synthetic tests. Do not mix test records with
real walking history. `exec` and `run_script` are canvas actions, not physical
badge commands. Reload normally to check saved data; restarting the entire
simulator runtime may clear its virtual filesystem.

| Check | Expected result |
| --- | --- |
| First launch | Height setup appears, followed by reminder interval setup |
| One UP, then DOWN in height setup | Height changes by +1 cm, then -1 cm |
| One UP, then DOWN in reminder setup | Interval changes by +10 steps, then -10 steps |
| UP/DOWN at limits | Height stays within 100-220 cm; interval within 100-5,000 |
| SELECT and BACK in setup | Values can be edited, saved, and reopened |
| Normal reload after save | Settings, steps, skips, and history are restored |
| Motion at rest | Repeated identical samples do not add steps |
| Synthetic motion across a milestone | One reminder, with the next milestone advanced |
| SELECT during reminder | One hydration record; skip level resets to zero |
| BACK during reminder | No hydration record; water rises, then counter returns |
| Three consecutive skips | Mona appears underwater with bubbles |
| Fourth consecutive skip | Water stays capped at level three |
| Drink after skips | Water resets; next reminder starts at normal level |
| Known beacon callback | Hydration records the matching Quest area |
| Beacon older than 60 seconds | Hydration records `Unknown area` |
| No beacon library | Step counter still opens; area is unknown |

To preview a reminder without walking, use the canvas `exec` action:

```python
setup_page = 0
reminder_active = True
```

Then press SELECT to log a simulated drink or BACK to skip. Trigger the reminder
again to exercise another skip. These button actions save test data.

For a deterministic threshold check in a disposable simulator runtime, use:

```python
setup_page = 0
step_count = 499
next_hydration = 500
hydration_interval = 500
last_saved_steps = 499
gravity_baseline = 16384
in_step_swing = False
last_step_tick = -1000
sample_motion(0, 0, 19000, badge.ticks, 8)
sample_motion(0, 0, 16384, badge.ticks, 8)
assert step_count == 500
assert reminder_active
assert next_hydration == 1000
```

This tests the detector's state transitions with chosen values, not the
firmware's accelerometer scale or real gait accuracy.

## Physical deployment

Read `hardware/USB_SERIAL.md` before connecting. Close other serial tools;
never run serial commands concurrently. Do not copy any filled `secrets.py`.

From the repository root:

```powershell
python .github\skills\hyb26-skill\scripts\badge_serial.py port
python .github\skills\hyb26-skill\scripts\badge_serial.py disk-mode
python .github\skills\hyb26-skill\scripts\deploy_app.py badge\apps\hydrate_yourself
python .github\skills\hyb26-skill\scripts\deploy_app.py badge\apps\hydrate_yourself --write
python .github\skills\hyb26-skill\scripts\patch_menu_icons.py
```

Review the deployment dry run before writing. If an app already exists, add
`--replace` to both deployment commands to preserve a backup. The icon patch
also previews first; apply with `--write` only if the installed menu needs it.
Verify installed file hashes, especially the new 48x48 water-cup `icon.png`.

Eject and let the badge restart:

```powershell
python .github\skills\hyb26-skill\scripts\badge_serial.py eject
```

Rediscover the port, then finish with `mpremote connect <port> reset`.
Open the menu and visually confirm the water-cup tile. File hashes alone
do not establish that the launcher displays the icon.

## Physical acceptance checklist

- Open the app, complete setup, return HOME, and reopen to check saved settings.
- Check both orientations, physical buttons, and capacitive controls.
- Count 100 actual steps manually and compare with the app. Repeat with the
  badge worn normally. Record the count and wearing position; tune the motion
  detector only from measured results.
- Stand still and handle the badge to look for false steps.
- Choose a 100-step interval, walk across a milestone, and check animation and
  responsiveness on hardware.
- Skip three reminders, verify rising water, then confirm a drink and verify
  reset and the saved log.
- Try a recognized venue IR beacon, then move away for more than a minute and
  verify the area becomes unknown. Beacon availability and coverage are not
  guaranteed; the last detected beacon is only a proximity hint.
- Check battery life over normal use. This app must remain open to count steps.

Physical deployment, successful app launch, and measured walking accuracy are
separate results. Do not label the pedometer hardware-verified merely because
the app was copied or the simulator passed.
