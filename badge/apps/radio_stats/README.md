# Radio Stats

Radio Stats shows anonymous counts of nearby Wi-Fi access points from passive scans.

## Usage

Open **Radio Stats** from the badge menu. Select takes a single passive
snapshot; Left/Right switches between channel counts and signal-strength
buckets. Home returns to the launcher. There is no automatic/background scan.
The listening card appears before scanning; the synchronous firmware scan can
pause controls for up to about ten seconds.

The header shows the observed access-point (AP) count and snapshot age.
Channel bars show counts on channels 1-14, not percentages; each snapshot
scales its bars to its largest count. Signal buckets are >= -60 dBm,
-75 through -61 dBm, and < -75 dBm. Unknown channels and invalid/unknown RSSI
values are counted separately. Empty scans show zero, not a radio error.

## Requirements and safety

Targets the Universe 2026 badge's onboard RM2 Wi-Fi radio and MicroPython
`network.WLAN` station/AP interfaces. No credentials, internet connection,
external hardware, or `secrets.py` changes are needed.

Only `station.scan(passive=True)` is used. The CYW43 implementation exposes
this keyword and selects passive scan type:
[MicroPython v1.27.0 source](https://github.com/micropython/micropython/blob/v1.27.0/extmod/network_cyw43.c).
Firmware that rejects it shows **Passive scan unsupported**; the app never
retries with a default/active scan. Missing networking APIs and radio failures
also produce explicit error cards. This source evidence is not verification
of a particular installed badge firmware.

The app refuses to scan if either the station or AP interface is already
active, leaving existing connectivity untouched. If this happens, turn off
Wi-Fi before retrying. Otherwise it enables the station only for the scan,
then disables it in a `finally` block even on failure. It never calls connect,
disconnect, packet-capture, transmit, or raw-radio APIs and does not change
country settings.

If disabling the station itself fails, **Radio shutdown failed** warns that
the radio may remain enabled; restart the badge before retrying.

The driver necessarily returns scan metadata including identifiers. The app
does not inspect those fields: it reads only channel and RSSI, consumes the
temporary result list, and retains only aggregate integers in RAM. It does
not log, display, persist, export, or track SSIDs, BSSIDs, MAC addresses,
packet payloads, or individual networks. Exiting discards the snapshot.

## Measurement limits

This is an AP-density snapshot, **not** channel airtime utilization, bandwidth,
packet rate, client count, or a measure of how much people are communicating.
The driver normally deduplicates APs within a scan; multiple AP radios can
belong to one network. Results depend on beacon timing, reception, signal
strength, firmware timeout and regulatory channel availability, and can be
partial. A zero count does not prove a channel is quiet. Overlapping 2.4 GHz
channels are shown separately, without suggesting a "best" channel.

The RM2 overview covers 2.4 GHz Wi-Fi only, not 5/6 GHz, BLE, other radio
protocols or non-Wi-Fi interference. Measuring actual band occupancy requires
hardware/firmware exposing channel-busy counters or a suitable spectrum
analyzer; the supported scan API supplies neither.

## Validation

From the repository root:

```powershell
python .github\skills\hyb26-skill\scripts\validate_app.py badge\apps\radio_stats
python .github\scripts\validate_app_readmes.py badge\apps
python -m unittest discover -s tests -p test_radio_stats.py
```

Host tests use synthetic metadata, not real network identifiers, and exercise
radio ownership, mandatory passive mode, errors, cleanup, aggregation and UI.
They do not prove radio behavior. The simulator does not implement Wi-Fi
scanning and should show the unavailable card, not fabricated measurements.

On a physical badge, verify: the custom menu icon; startup without scanning;
Select's listening card then a snapshot; both pages and empty results;
retry/error behavior; active station/AP refusal without changing that
connection; station disabled after scanning; Home/reopen; both orientations.
Confirm the installed firmware's passive behavior before relying on it in
a transmission-sensitive environment. Physical verification is outstanding.
