# BM83 Remote

BM83 Remote brings the CrowPanel audio controls and Now Playing information to the GitHub Universe badge.

Open **BM83 Remote** from the badge menu while the badge and BM83 audio unit are on the same Wi-Fi network. The unit must run the matching BMW1 UDP receiver on port 8767 and have the same 32-byte key. The badge requests album artwork over HTTPS from MusicBrainz and Cover Art Archive, with Deezer as a fallback; a small cache is stored under `/state/bm83_art/`.

## Controls

- **Left / Right**: previous / next track.
- **Select**: play / pause.
- **Back**: mute on the Now Playing page; cancel/return on Settings.
- **Hold Up / Down**: volume up / down; release the button to stop the unit's repeat.
- **Menu**: open Settings. Use **Up / Down**, **Select**, and **Back** to navigate.
- Settings provide Power, Pair, EQ, confirmed bond erasure, Wi-Fi/artwork retry, and BLE volume-remote pause/enable when a fresh BLE status permits the request.

The status line reports whether a command was sent and whether a reply arrived. A reply is delivery feedback, not proof that playback or volume changed. BLE Pause/Enable is reported as Waiting, Confirmed, Failed, or Unconfirmed and only confirms when a newer BLE status echoes the matching request client/sequence; null correlation means there is no current Wi-Fi-owned BLE request.

## Configuration and network

Add these values to the badge's existing `secrets.py`; never put real credentials in this app or commit them:

```python
WIFI_SSID = "your network"
WIFI_PASSWORD = "your password"
BM83_HOST = "192.168.1.50"  # the audio unit's IPv4 address
BM83_PORT = 8767             # optional; defaults to 8767
BM83_KEY = "64 lowercase hex characters shared with the audio unit"
```

The BM83 unit and badge need LAN connectivity. Automatic cover downloads also need internet access. Missing settings, Wi-Fi failures, unavailable units, missing artwork and unsupported/progressive JPEGs are shown in the app rather than treated as success. The simulator cannot use sockets or HTTPS; `inject_sample_state()` can be called from its REPL to preview Now Playing layout.

## BMW1 details

Datagrams use the `BMW1.` prefix, a 16-byte HMAC-SHA256 tag, and UTF-8 JSON. The app verifies the tag before decoding JSON, accepts only replies from the configured IPv4/port, serializes one command at a time, retries the same sequence, and preserves a pending volume release ahead of other commands. Timed-out non-idempotent commands are not replayed under a new client. Status snapshots expire after six seconds; elapsed time advances only for a fresh playing snapshot whose source clock is advancing and remains within the source-age limit.

Artwork uses exact artist/album identity, a MusicBrainz score threshold of 95, unique release-group matches, a minimum 1.1-second MusicBrainz request interval and bounded response/cache sizes. Requests are HTTPS-only and limited to MusicBrainz, Cover Art Archive, Archive.org and Deezer hosts. The badge's `fetch` does not follow redirects, so the app follows at most three itself within that same allow-list. A busy MusicBrainz (HTTP 429, 502, 503 or 504) is retried up to three times at the same request interval before the app reports that artwork is unavailable; Settings then offers a retry. Artwork data is untrusted; only matching artist/album data and baseline JPEGs with bounded dimensions are used.

## Host tests

Run the app tests from the repository root. Receiver interoperability tests use a sibling `BM83-ESP32-S3-Nextion/firmware/circuitpython/lib` checkout when available; set `BM83_RECEIVER_LIB` to the receiver library directory for any other checkout location:

```powershell
$env:BM83_RECEIVER_LIB = "C:\path\to\BM83-ESP32-S3-Nextion\firmware\circuitpython\lib"
python -m unittest discover -s tests -p "test_bm83*.py"
```
