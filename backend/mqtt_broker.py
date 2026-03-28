#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  Lightweight MQTT Broker (Python)                            ║
║  Replaces Mosquitto when it's not available.                 ║
║                                                              ║
║  Ports:                                                      ║
║   - 1883: MQTT TCP (for Python bridge)                       ║
║   - 9001: MQTT over WebSocket (for browser/React frontend)   ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import struct
import signal
import sys
from collections import defaultdict

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# ── MQTT Packet Types ──
CONNECT = 1
CONNACK = 2
PUBLISH = 3
PUBACK = 4
SUBSCRIBE = 8
SUBACK = 9
UNSUBSCRIBE = 10
UNSUBACK = 11
PINGREQ = 12
PINGRESP = 13
DISCONNECT = 14


def encode_remaining_length(length):
    encoded = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        encoded.append(byte)
        if length == 0:
            break
    return bytes(encoded)


def decode_remaining_length(data, offset=1):
    multiplier = 1
    value = 0
    idx = offset
    while idx < len(data):
        encoded_byte = data[idx]
        value += (encoded_byte & 0x7F) * multiplier
        multiplier *= 128
        idx += 1
        if (encoded_byte & 0x80) == 0:
            break
    return value, idx


def decode_utf8(data, offset):
    str_len = struct.unpack("!H", data[offset:offset+2])[0]
    s = data[offset+2:offset+2+str_len].decode("utf-8", errors="replace")
    return s, offset + 2 + str_len


def encode_utf8(s):
    b = s.encode("utf-8")
    return struct.pack("!H", len(b)) + b


class MQTTBroker:
    def __init__(self):
        self.subscribers = defaultdict(set)   # topic -> set of client_id
        self.clients = {}                      # client_id -> send_func(bytes)
        self.retained = {}                     # topic -> raw publish bytes
        self.msg_count = 0

    def topic_matches(self, subscription, topic):
        sub_parts = subscription.split("/")
        top_parts = topic.split("/")
        for i, sp in enumerate(sub_parts):
            if sp == "#":
                return True
            if i >= len(top_parts):
                return False
            if sp != "+" and sp != top_parts[i]:
                return False
        return len(sub_parts) == len(top_parts)

    async def process_packet(self, raw, client_id, send_func):
        """Process a single MQTT packet from raw bytes. Returns client_id (may be updated on CONNECT)."""
        if len(raw) < 2:
            return client_id

        pkt_type = (raw[0] >> 4) & 0x0F
        flags = raw[0] & 0x0F

        # Decode remaining length to find where variable header starts
        remaining_len, var_start = decode_remaining_length(raw, 1)
        var_header = raw[var_start:var_start + remaining_len]

        if pkt_type == CONNECT:
            # Parse CONNECT
            off = 0
            proto_name, off = decode_utf8(var_header, off)
            proto_ver = var_header[off]; off += 1
            connect_flags = var_header[off]; off += 1
            keep_alive = struct.unpack("!H", var_header[off:off+2])[0]; off += 2
            cid, off = decode_utf8(var_header, off)
            if cid:
                client_id = cid

            # Register client
            self.clients[client_id] = send_func

            # Send CONNACK (session present=0, return code=0)
            connack = bytes([CONNACK << 4, 2, 0, 0])
            await send_func(connack)
            print(f"  [BROKER] Client connected: {client_id}")

        elif pkt_type == PUBLISH:
            qos = (flags >> 1) & 0x03
            retain = flags & 0x01
            off = 0
            topic, off = decode_utf8(var_header, off)
            pkt_id = None
            if qos > 0 and off + 2 <= len(var_header):
                pkt_id = struct.unpack("!H", var_header[off:off+2])[0]
                off += 2
            payload = var_header[off:]
            self.msg_count += 1

            if retain:
                if payload:
                    self.retained[topic] = raw
                else:
                    self.retained.pop(topic, None)

            # Forward to matching subscribers
            await self._forward(topic, raw, client_id)

            # PUBACK for QoS 1
            if qos == 1 and pkt_id is not None:
                puback = bytes([PUBACK << 4, 2]) + struct.pack("!H", pkt_id)
                await send_func(puback)

        elif pkt_type == SUBSCRIBE:
            off = 0
            pkt_id = struct.unpack("!H", var_header[off:off+2])[0]; off += 2
            granted = []
            while off < len(var_header):
                topic, off = decode_utf8(var_header, off)
                qos = var_header[off]; off += 1
                self.subscribers[topic].add(client_id)
                granted.append(min(qos, 1))
                # Send retained for this topic
                for rt, rd in list(self.retained.items()):
                    if self.topic_matches(topic, rt):
                        try:
                            await send_func(rd)
                        except Exception:
                            pass

            # SUBACK
            payload_bytes = bytes(granted)
            suback = bytes([SUBACK << 4])
            suback += encode_remaining_length(2 + len(payload_bytes))
            suback += struct.pack("!H", pkt_id)
            suback += payload_bytes
            await send_func(suback)

        elif pkt_type == UNSUBSCRIBE:
            off = 0
            pkt_id = struct.unpack("!H", var_header[off:off+2])[0]; off += 2
            while off < len(var_header):
                topic, off = decode_utf8(var_header, off)
                self.subscribers[topic].discard(client_id)
            unsuback = bytes([UNSUBACK << 4, 2]) + struct.pack("!H", pkt_id)
            await send_func(unsuback)

        elif pkt_type == PINGREQ:
            await send_func(bytes([PINGRESP << 4, 0]))

        elif pkt_type == DISCONNECT:
            pass  # handled by caller

        return client_id

    async def _forward(self, topic, raw, sender_id):
        dead = []
        for sub_topic, client_ids in list(self.subscribers.items()):
            if self.topic_matches(sub_topic, topic):
                for cid in list(client_ids):
                    if cid != sender_id and cid in self.clients:
                        try:
                            await self.clients[cid](raw)
                        except Exception:
                            dead.append((sub_topic, cid))
        for st, cid in dead:
            self.subscribers[st].discard(cid)

    def remove_client(self, client_id):
        self.clients.pop(client_id, None)
        for topic in list(self.subscribers.keys()):
            self.subscribers[topic].discard(client_id)
            if not self.subscribers[topic]:
                del self.subscribers[topic]
        print(f"  [BROKER] Client disconnected: {client_id}")


# ─────────────────────────────────
# TCP MQTT handler
# ─────────────────────────────────

async def read_mqtt_packet(reader):
    """Read one complete MQTT packet from a TCP stream."""
    header = await reader.read(1)
    if not header:
        return None

    # Read remaining length
    remaining = 0
    multiplier = 1
    while True:
        b = await reader.read(1)
        if not b:
            return None
        remaining += (b[0] & 0x7F) * multiplier
        multiplier *= 128
        if (b[0] & 0x80) == 0:
            break

    body = b""
    if remaining > 0:
        body = await reader.readexactly(remaining)

    return header + encode_remaining_length(remaining) + body


async def handle_tcp_client(reader, writer, broker):
    client_id = f"tcp_{id(writer)}"

    async def send(data):
        writer.write(data)
        await writer.drain()

    try:
        while True:
            raw = await read_mqtt_packet(reader)
            if raw is None:
                break
            pkt_type = (raw[0] >> 4) & 0x0F
            client_id = await broker.process_packet(raw, client_id, send)
            if pkt_type == DISCONNECT:
                break
    except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
        pass
    except Exception as e:
        print(f"  [BROKER-TCP] Error: {e}")
    finally:
        broker.remove_client(client_id)
        writer.close()


# ─────────────────────────────────
# WebSocket MQTT handler
# ─────────────────────────────────

async def handle_ws_client(ws, broker):
    client_id = f"ws_{id(ws)}"

    async def send(data):
        await ws.send(data)

    try:
        async for message in ws:
            if isinstance(message, str):
                message = message.encode("utf-8")
            pkt_type = (message[0] >> 4) & 0x0F
            client_id = await broker.process_packet(message, client_id, send)
            if pkt_type == DISCONNECT:
                break
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"  [BROKER-WS] Error: {e}")
    finally:
        broker.remove_client(client_id)


# ─────────────────────────────────
# Main
# ─────────────────────────────────

async def main():
    broker = MQTTBroker()

    # TCP server on port 1883
    tcp_server = await asyncio.start_server(
        lambda r, w: handle_tcp_client(r, w, broker),
        "0.0.0.0", 1883
    )

    print("═" * 50)
    print("  MQTT Broker (Python) running")
    print(f"  TCP:        0.0.0.0:1883")

    ws_server = None
    if HAS_WEBSOCKETS:
        # WebSocket server on port 9001 with 'mqtt' subprotocol
        ws_server = await websockets.serve(
            lambda ws: handle_ws_client(ws, broker),
            "0.0.0.0", 9001,
            subprotocols=["mqtt"],
            ping_interval=None,
            compression=None,
        )
        print(f"  WebSocket:  0.0.0.0:9001")
    else:
        print("  ⚠️  websockets not installed — WS server disabled")
        print("     Install: pip install websockets")

    print("═" * 50)

    # Wait forever
    stop = asyncio.get_event_loop().create_future()

    def _stop():
        if not stop.done():
            stop.set_result(True)

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, _stop)

    try:
        await stop
    finally:
        tcp_server.close()
        if ws_server:
            ws_server.close()
        print("\n  [BROKER] Shutting down...")


if __name__ == "__main__":
    print("\n🔌 Starting Python MQTT Broker...")
    asyncio.run(main())
