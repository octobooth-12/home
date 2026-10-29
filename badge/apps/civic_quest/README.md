# Civic Quest

A five-level civics game for ages 10-15 that teaches how elections work using a fictional country and fictional candidates.

## Usage

Use Up/Down to move, Left/Right to page or switch, and Select to choose. Back
is an optional shortcut; every screen can be finished with the direction
controls and Select alone. Levels unlock in order:

1. **How Elections Work** - candidates, platforms, secret ballots and who runs
   elections.
2. **Issues & Tradeoffs** - taxes, education, immigration and climate, each
   with a benefit and a cost.
3. **Mystery Platforms** - compare three unnamed platforms (X, Y and Z) across
   all four issues. Every card must be viewed before moving on.
4. **Reveal & Fact-Check** - all three candidates are revealed together and
   shown equally, then you practice checking claims and sources.
5. **Ballot & Beyond** - cast a secret practice ballot (in shuffled order, with
   a "Leave blank" option), learn that changing your mind and disagreeing
   respectfully are normal, and graduate with a Civic Ready certificate.

Each level ends with a short quiz. Only civic knowledge is scored; there are no
right or wrong views and no candidate is ever recommended.

## Privacy

The game never tries to predict or record which candidate or idea a player
prefers. Only level completion and quiz scores are saved, using the badge
`State` store. The practice ballot is never saved or scored. Use **Reset
progress** on the title screen to clear saved progress.

## Requirements

Universe 2026 badge firmware. No Wi-Fi, touch or badge link is needed.

## Fork and run

The complete source is published at https://github.com/octobooth-12/home,
with Civic Quest on the default `civic-quest` branch. Fork that repository on
GitHub, then clone your fork. Keep the full repository so the badge runtime
references, simulator extension, deployment scripts and tests remain available.

From the repository root in PowerShell, with Python 3.10 or later:

```powershell
python -m unittest tests.test_civic_quest tests.test_system
python .github\skills\hyb26-skill\scripts\validate_app.py badge\apps\civic_quest
```

In the GitHub Copilot app, open the Badge Simulator for `civic_quest` to try
the game on your computer. The simulator extension is in
`.github/extensions/badge-simulator/`; follow its README for setup.

This app is Python source: no compilation or firmware build is required when
using compatible Universe 2026 firmware. For a physical badge, follow
`hardware/USB_SERIAL.md`. In USB Disk Mode, preview the files before deploying:

```powershell
python .github\skills\hyb26-skill\scripts\deploy_app.py badge\apps\civic_quest
```

Review the preview, then add `--write` to install. If updating an existing
installation, use `--replace` as well; the script keeps a backup.
