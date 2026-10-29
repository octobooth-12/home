"""Passive Wi-Fi observations, retaining only anonymous aggregates."""


class ScanError(Exception):
    pass


def aggregate(results):
    stats = {
        "total": 0,
        "channels": [0] * 14,
        "unknown_channel": 0,
        "signals": [0, 0, 0],
        "unknown_signal": 0,
        "strongest": None,
    }
    # Consume the driver's list so identifying fields are released promptly.
    while results:
        row = results.pop()
        if not isinstance(row, (tuple, list)) or len(row) < 4:
            raise ScanError("Invalid scan result")
        channel, rssi = row[2], row[3]
        del row
        if type(channel) is not int or type(rssi) is not int:
            raise ScanError("Invalid scan measurement")
        stats["total"] += 1
        if 1 <= channel <= 14:
            stats["channels"][channel - 1] += 1
        else:
            stats["unknown_channel"] += 1
        if not -127 < rssi < 0:
            stats["unknown_signal"] += 1
            continue
        bucket = 0 if rssi >= -60 else 1 if rssi >= -75 else 2
        stats["signals"][bucket] += 1
        if stats["strongest"] is None or rssi > stats["strongest"]:
            stats["strongest"] = rssi
    return stats


def passive_snapshot(network):
    """Never borrow an active interface or fall back to an active scan."""
    try:
        station = network.WLAN(network.STA_IF)
        access_point = network.WLAN(network.AP_IF)
        if station.active() or access_point.active():
            raise ScanError("Wi-Fi already in use")
        try:
            station.active(True)
            try:
                results = station.scan(passive=True)
            except TypeError:
                raise ScanError("Passive scan unsupported")
            return aggregate(results)
        finally:
            try:
                station.active(False)
            except OSError:
                raise ScanError("Radio shutdown failed")
    except (AttributeError, ImportError):
        raise ScanError("Wi-Fi API unavailable")
    except OSError:
        raise ScanError("Radio operation failed")
