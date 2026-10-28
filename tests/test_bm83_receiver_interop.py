"""Cross-check the badge BMW1 client with the companion receiver when present."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "badge" / "apps" / "bm83_remote"
sys.path.insert(0, str(APP))

import protocol as badge_protocol
import models
from transport import Remote

RECEIVER_LIB = Path(os.environ.get(
    "BM83_RECEIVER_LIB",
    str(ROOT.parents[1] / "BM83-ESP32-S3-Nextion"
        / "firmware" / "circuitpython" / "lib")))
if RECEIVER_LIB.is_dir():
    sys.path.insert(0, str(RECEIVER_LIB))

try:
    from remote.wifi_remote import Authenticator, WifiRemote
except ImportError as import_error:
    Authenticator = WifiRemote = None
    RECEIVER_IMPORT_ERROR = str(import_error)
else:
    RECEIVER_IMPORT_ERROR = ""

KEY = bytes(range(32))
KEY_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"


class Socket:
    def __init__(self):
        self.incoming = []
        self.outgoing = []

    def settimeout(self, value):
        self.timeout = value

    def bind(self, address):
        self.address = address

    def recvfrom_into(self, buffer):
        if not self.incoming:
            raise OSError(11)
        raw, address = self.incoming.pop(0)
        buffer[:len(raw)] = raw
        return len(raw), address

    def recvfrom(self, size):
        if not self.incoming:
            raise OSError(11)
        raw, address = self.incoming.pop(0)
        return raw[:size], address

    def setblocking(self, value):
        pass

    def sendto(self, raw, address):
        self.outgoing.append((raw, address))
        return len(raw)

    def close(self):
        pass


class State:
    def __init__(self):
        self.title = "Title"

    def snapshot(self):
        return {
            "power_on": True, "connected": True, "aux": False,
            "play_status": 1, "eq_index": 1, "duration_ms": 180000,
            "position_ms": 5000, "position_age_ms": 100,
            "clock_advancing": True, "title": self.title, "artist": "Artist",
            "album": "Album",
        }


class Ble:
    def __init__(self):
        self.value = {
            "session": 91, "sequence": 12, "mode": 0, "flags": 15,
            "error": 0, "req_client": None, "req_seq": None,
        }

    def snapshot(self):
        return dict(self.value)


@unittest.skipIf(WifiRemote is None, "BMW3 receiver unavailable: " + RECEIVER_IMPORT_ERROR)
class ReceiverInteropTests(unittest.TestCase):
    def setUp(self):
        self.socket = Socket()
        self.unit = WifiRemote(
            profile={"v": 1, "key": KEY_HEX, "port": 8767},
            socket=self.socket, unit="a1b2c3d4", clock=lambda: 0.0,
            log=lambda *args: None,
        )
        self.assertTrue(self.unit.setup())
        self.auth = Authenticator(KEY_HEX)
        self.peer = ("192.168.1.20", 49152)

    def from_unit(self):
        raw, peer = self.socket.outgoing.pop(0)
        self.assertEqual(peer, self.peer)
        return badge_protocol.decode(KEY, raw)

    def send(self, value):
        self.socket.incoming.append((badge_protocol.encode(KEY, value), self.peer))

    def test_shared_vectors_and_authenticated_welcome(self):
        hello = {"v": 1, "type": "hello", "nonce": "0011223344556677"}
        self.assertEqual(self.auth.encode(hello), badge_protocol.encode(KEY, hello))
        self.send(hello)
        self.assertEqual(self.unit.poll(0.0), [])
        welcome = self.from_unit()
        self.assertEqual(welcome, {
            "v": 1, "type": "welcome", "nonce": hello["nonce"],
            "unit": "a1b2c3d4", "client": 1,
        })

    def test_command_state_duplicate_rehello_and_ble_correlation(self):
        self.send({"v": 1, "type": "hello", "nonce": "0011223344556677"})
        self.unit.poll(0.0)
        welcome = self.from_unit()
        client = welcome["client"]

        command = {"v": 1, "type": "cmd", "unit": welcome["unit"],
                   "client": client, "seq": 1, "token": "BT_PLAY"}
        self.send(command)
        self.assertEqual(self.unit.poll(0.3), [(b"BT_PLAY", client, 1)])
        state, ble = State(), Ble()
        state.title = "é" * 50
        self.unit.reply(state, ble, {1: "ROCK"})
        reply = self.from_unit()
        self.assertEqual((reply["type"], reply["client"], reply["seq"], reply["dup"]),
                         ("state", client, 1, False))
        self.assertEqual(reply["np"]["eq"], "ROCK")
        self.assertTrue(models.valid_np(reply["np"]))
        self.assertEqual(reply["ble"]["session"], 91)

        # A lost-response retry is acknowledged as duplicate without dispatch.
        self.send(command)
        self.assertEqual(self.unit.poll(0.33), [])
        self.unit.reply(state, ble, {1: "ROCK"})
        duplicate = self.from_unit()
        self.assertTrue(duplicate["dup"])

        # A new BLE intent echoes the active client/sequence pair in its state.
        ble.value.update(sequence=13, req_client=client, req_seq=2)
        self.send(dict(command, seq=2, token="BLE_PAUSE"))
        self.assertEqual(self.unit.poll(0.36), [(b"BLE_PAUSE", client, 2)])
        self.unit.reply(state, ble, {1: "ROCK"})
        correlated = self.from_unit()
        self.assertEqual((correlated["ble"]["req_client"], correlated["ble"]["req_seq"]),
                         (client, 2))
        ble.value.update(sequence=14, session=92, req_client=None, req_seq=None)
        self.send(dict(command, seq=3, token="STATUS"))
        self.assertEqual(self.unit.poll(0.39), [])
        self.unit.reply(state, ble, {1: "ROCK"})
        superseded = self.from_unit()
        self.assertIsNone(superseded["ble"]["req_client"])
        self.assertIsNone(superseded["ble"]["req_seq"])
        self.assertEqual(superseded["ble"]["session"], 92)

        self.send(dict(command, unit="ffffffff", seq=4))
        self.assertEqual(self.unit.poll(0.42), [])
        rehello = self.from_unit()
        self.assertEqual((rehello["type"], rehello["client"], rehello["seq"]),
                         ("rehello", client, 4))

    def test_lost_release_ack_retries_same_seq_and_blocks_next_action(self):
        client = Remote(self.peer[0], self.peer[1], KEY)
        client.socket.close()
        client_socket = Socket()
        client.socket = client_socket

        client.step(0)
        hello, _ = client_socket.outgoing.pop()
        self.socket.incoming.append((hello, self.peer))
        self.unit.poll(0.0)
        welcome, _ = self.socket.outgoing.pop()
        client_socket.incoming.append((welcome, client.peer))
        client.step(1)

        client.queue_command("BT_VOLUP_R")
        client.queue_command("BT_PLAY")
        client.step(2)
        release, _ = client_socket.outgoing.pop()
        self.socket.incoming.append((release, self.peer))
        self.assertEqual(self.unit.poll(0.3), [(b"BT_VOLUP_R", 1, 1)])
        self.unit.reply(State(), Ble(), {1: "ROCK"})
        lost_ack, _ = self.socket.outgoing.pop()
        self.assertFalse(badge_protocol.decode(KEY, lost_ack)["dup"])

        client.step(152)
        retry, _ = client_socket.outgoing.pop()
        self.assertEqual(retry, release)
        self.socket.incoming.append((retry, self.peer))
        self.assertEqual(self.unit.poll(0.55), [])
        self.unit.reply(State(), Ble(), {1: "ROCK"})
        duplicate_ack, _ = self.socket.outgoing.pop()
        self.assertTrue(badge_protocol.decode(KEY, duplicate_ack)["dup"])
        client_socket.incoming.append((duplicate_ack, client.peer))
        client.step(153)

        next_action, _ = client_socket.outgoing.pop()
        decoded = badge_protocol.decode(KEY, next_action)
        self.assertEqual((decoded["token"], decoded["seq"]), ("BT_PLAY", 2))

    def test_restart_after_net_retry_dispatch_does_not_repeat_action(self):
        old_socket = Socket()
        old_unit = WifiRemote(
            profile={"v": 1, "key": KEY_HEX, "port": 8767},
            socket=old_socket, unit="a1b2c3d4", clock=lambda: 0.0,
            log=lambda *args: None,
        )
        self.assertTrue(old_unit.setup())
        client = Remote("192.168.1.30", 8767, KEY)
        client.socket.close()
        client_socket = Socket()
        client.socket = client_socket

        # Authenticate the badge to the current boot.
        client.step(0)
        old_socket.incoming.append((client_socket.outgoing.pop()[0], self.peer))
        old_unit.poll(0.0)
        welcome, _ = old_socket.outgoing.pop()
        client_socket.incoming.append((welcome, ("192.168.1.30", 8767)))
        client.queue_command("NET_RETRY")
        client.step(1)
        original_command = client_socket.outgoing[-1][0]
        original = badge_protocol.decode(KEY, original_command)
        self.assertEqual(original["token"], "NET_RETRY")

        # The old receiver dispatches NET_RETRY, then reboots before its ACK.
        old_socket.incoming.append((original_command, self.peer))
        self.assertEqual(old_unit.poll(0.3), [(b"NET_RETRY", 1, 1)])

        new_socket = Socket()
        new_unit = WifiRemote(
            profile={"v": 1, "key": KEY_HEX, "port": 8767},
            socket=new_socket, unit="b2c3d4e5", clock=lambda: 0.0,
            log=lambda *args: None,
        )
        self.assertTrue(new_unit.setup())
        new_socket.incoming.append((original_command, self.peer))
        self.assertEqual(new_unit.poll(0.0), [])
        rehello, _ = new_socket.outgoing.pop()
        client_socket.incoming.append((rehello, ("192.168.1.30", 8767)))

        # Rehello reconnects the client; the only next command is status.
        client.step(152)
        hello = badge_protocol.decode(KEY, client_socket.outgoing[-1][0])
        self.assertEqual(hello["type"], "hello")
        new_socket.incoming.append((client_socket.outgoing.pop()[0], self.peer))
        new_unit.poll(0.31)
        welcome, _ = new_socket.outgoing.pop()
        client_socket.incoming.append((welcome, ("192.168.1.30", 8767)))
        client.step(1152)
        requests = [badge_protocol.decode(KEY, packet)
                    for packet, _address in client_socket.outgoing]
        tokens = [message["token"] for message in requests if message.get("type") == "cmd"]
        self.assertEqual(tokens, ["NET_RETRY", "STATUS"])
        self.assertIn("delivery unconfirmed", client.feedback)

        # The restarted receiver accepts STATUS but dispatches no action.
        status_packet, _ = client_socket.outgoing.pop()
        new_socket.incoming.append((status_packet, self.peer))
        self.assertEqual(new_unit.poll(0.34), [])
        self.assertEqual(new_unit._replies[-1][3], False)


if __name__ == "__main__":
    unittest.main()
