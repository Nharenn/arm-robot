#!/usr/bin/env python3
"""
UR5 MQTT ↔ CoppeliaSim Bridge
[React] ──WS:9001──▸ [Mosquitto] ──TCP:1883──▸ [Bridge] ──ZMQ:23000──▸ [CoppeliaSim]
"""

import json
import time
import math
import threading
import signal
import sys
import os
from typing import Dict

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

MQTT_HOST    = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT    = int(os.getenv("MQTT_BROKER_PORT", "1883"))
COPPELIA_HOST = os.getenv("COPPELIASIM_HOST", "localhost")
COPPELIA_PORT = int(os.getenv("COPPELIASIM_PORT", "23000"))

TOPIC_CMD_JOINTS    = "ur5/cmd/joints"
TOPIC_CMD_GRIPPER   = "ur5/cmd/gripper"
TOPIC_CMD_PID       = "ur5/cmd/pid"
TOPIC_STATE_JOINTS  = "ur5/state/joints"
TOPIC_STATE_PID     = "ur5/state/pid"
TOPIC_STATE_SENSORS = "ur5/state/sensors"
TOPIC_STATUS        = "ur5/status"

JOINT_KEYS = ["J1", "J2", "J3", "J4", "J5", "J6"]

UR5_JOINT_NAMES = [
    "/UR5/joint",
    "/UR5/link/joint",
    "/UR5/link/joint/link/joint",
    "/UR5/link/joint/link/joint/link/joint",
    "/UR5/link/joint/link/joint/link/joint/link/joint",
    "/UR5/joint/link/joint/link/joint/link/joint/link/joint/link/joint",
]
UR5_JOINT_NAMES_ALT = [
    "/UR5_joint1", "/UR5_joint2", "/UR5_joint3",
    "/UR5_joint4", "/UR5_joint5", "/UR5_joint6",
]


class PIDController:
    def __init__(self, kp=1.0, ki=0.1, kd=0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_error = 0.0

    def update(self, setpoint: float, measured: float, dt: float) -> dict:
        error = setpoint - measured
        if abs(error) < 0.1:          # zona muerta — evita ruido en cero
            self.integral = 0.0
            self.prev_error = 0.0
            return {"setpoint": round(setpoint, 2), "error": round(error, 2),
                    "output": 0.0, "p": 0.0, "i": 0.0, "d": 0.0}
        self.integral = max(-20.0, min(20.0, self.integral + error * dt))
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        self.prev_error = error
        p = self.kp * error
        i = self.ki * self.integral
        d = self.kd * derivative
        return {"setpoint": round(setpoint, 2), "error": round(error, 2),
                "output": round(p + i + d, 2), "p": round(p, 2),
                "i": round(i, 2), "d": round(d, 2)}

    def set_params(self, kp=None, ki=None, kd=None):
        if kp is not None: self.kp = kp
        if ki is not None: self.ki = ki
        if kd is not None: self.kd = kd
        self.integral = 0.0
        self.prev_error = 0.0


class UR5Bridge:

    def __init__(self):
        self.sim = None
        self.joint_handles = []
        self._lock = threading.Lock()           # protege target_angles de race conditions
        self.target_angles: Dict[str, float] = {k: 0.0 for k in JOINT_KEYS}
        self.active_joint = "J2"
        self.pid = PIDController()
        self.running = True
        self.coppelia_connected = False
        self.mqtt_connected = False

        self.mqtt_client = mqtt.Client(
            client_id="ur5_bridge",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.mqtt_client.on_connect    = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_message    = self._on_mqtt_message
        self.mqtt_client.will_set(TOPIC_STATUS,
            json.dumps({"connected": False, "coppelia": False}), qos=1, retain=True)

    # ── MQTT ──

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.mqtt_connected = True
            client.subscribe(TOPIC_CMD_JOINTS,  qos=1)
            client.subscribe(TOPIC_CMD_GRIPPER, qos=1)
            client.subscribe(TOPIC_CMD_PID,     qos=1)
            self._publish_status()
            print("✅ MQTT: Connected")
        else:
            print(f"❌ MQTT: rc={rc}")

    def _on_mqtt_disconnect(self, client, userdata, flags, rc, properties=None):
        self.mqtt_connected = False
        print(f"⚠️  MQTT: Disconnected rc={rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if msg.topic == TOPIC_CMD_JOINTS:
                with self._lock:
                    for k in JOINT_KEYS:
                        if k in payload:
                            self.target_angles[k] = float(payload[k])
                    if "activeJoint" in payload:
                        self.active_joint = payload["activeJoint"]
                        self.pid.integral   = 0.0   # reset integral on joint change
                        self.pid.prev_error = 0.0
            elif msg.topic == TOPIC_CMD_PID:
                self.pid.set_params(
                    kp=payload.get("kp"),
                    ki=payload.get("ki"),
                    kd=payload.get("kd"),
                )
        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️  Bad message: {e}")

    # ── CoppeliaSim ──

    def connect_coppelia(self) -> bool:
        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            print(f"🔗 Connecting to CoppeliaSim {COPPELIA_HOST}:{COPPELIA_PORT}...")
            self.sim = RemoteAPIClient(host=COPPELIA_HOST, port=COPPELIA_PORT).require("sim")
            self.joint_handles = self._find_joints()

            if len(self.joint_handles) == 6:
                self.coppelia_connected = True
                # Sincronizar targets con posición real — evita snap al arrancar
                initial = self._read_positions()
                if initial:
                    with self._lock:
                        self.target_angles.update(initial)
                    print(f"✅ CoppeliaSim: 6 joints found, synced to {initial}")
                self._publish_status()
                return True
            else:
                print(f"⚠️  Found {len(self.joint_handles)} joints (need 6) — DEMO MODE")
                return False
        except ImportError:
            print("❌ coppeliasim_zmqremoteapi_client not installed")
            return False
        except Exception as e:
            print(f"❌ CoppeliaSim: {e} — DEMO MODE")
            return False

    def _find_joints(self) -> list:
        for names in [UR5_JOINT_NAMES, UR5_JOINT_NAMES_ALT]:
            try:
                handles = [self.sim.getObject(n) for n in names]
                if len(handles) == 6:
                    return handles
            except Exception:
                pass
        # Auto-discover
        try:
            all_j, idx = [], 0
            while True:
                try:
                    h = self.sim.getObjects(idx, self.sim.sceneobject_joint)
                    if h == -1: break
                    all_j.append(h); idx += 1
                except Exception:
                    break
            if len(all_j) >= 6:
                return sorted(all_j, key=lambda h: self.sim.getObjectAlias(h, 1))[:6]
        except Exception:
            pass
        return []

    def _read_positions(self) -> Dict[str, float]:
        try:
            return {JOINT_KEYS[i]: round(math.degrees(self.sim.getJointPosition(h)), 2)
                    for i, h in enumerate(self.joint_handles)}
        except Exception:
            self.coppelia_connected = False
            return {}

    def _write_targets(self, targets: Dict[str, float]):
        """Escribe targets directamente — CoppeliaSim maneja el movimiento internamente."""
        try:
            for i, h in enumerate(self.joint_handles):
                self.sim.setJointTargetPosition(h, math.radians(targets[JOINT_KEYS[i]]))
        except Exception as e:
            print(f"⚠️  Write error: {e}")
            self.coppelia_connected = False
            self._publish_status()

    # ── Demo mode ──

    def _demo_joints(self) -> Dict[str, float]:
        if not hasattr(self, '_demo_pos'):
            self._demo_pos = {k: 0.0 for k in JOINT_KEYS}
        with self._lock:
            targets = dict(self.target_angles)
        import random
        for k in JOINT_KEYS:
            self._demo_pos[k] = round(
                self._demo_pos[k] + 0.15 * (targets[k] - self._demo_pos[k])
                + (random.random() - 0.5) * 0.05, 2)
        return dict(self._demo_pos)

    def _demo_sensors(self) -> Dict[str, float]:
        import random
        if not hasattr(self, '_demo_temp'):
            self._demo_temp, self._demo_force = 28.0, 0.0
        self._demo_temp  = round(max(20, min(80, self._demo_temp  + (random.random()-0.48)*0.15)), 1)
        self._demo_force = round(max(0,  min(20, self._demo_force + (random.random()-0.5 )*0.3 )), 1)
        return {"temp": self._demo_temp, "force": self._demo_force}

    # ── Status ──

    def _publish_status(self):
        self.mqtt_client.publish(TOPIC_STATUS, json.dumps({
            "connected": self.mqtt_connected,
            "coppelia":  self.coppelia_connected,
            "mode": "live" if self.coppelia_connected else "demo",
            "timestamp": time.time(),
        }), qos=1, retain=True)

    # ── Main loop ──

    def run(self):
        print("╔══════════════════════════════════════╗")
        print("║   UR5 MQTT ↔ CoppeliaSim Bridge      ║")
        print("╚══════════════════════════════════════╝")

        try:
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"❌ MQTT connect failed: {e}")
            sys.exit(1)

        time.sleep(1)
        self.connect_coppelia()

        if not self.coppelia_connected:
            print("ℹ️  DEMO MODE — start CoppeliaSim and restart bridge for live control")

        dt = 0.05   # 20 Hz — coincide con timestep de CoppeliaSim
        print(f"🚀 Running at {int(1/dt)} Hz")

        try:
            while self.running:
                t0 = time.time()

                # Snapshot thread-safe de targets
                with self._lock:
                    targets = dict(self.target_angles)
                    active  = self.active_joint

                # Leer posición actual
                if self.coppelia_connected:
                    joints = self._read_positions()
                    if not joints:
                        joints = self._demo_joints()
                else:
                    joints = self._demo_joints()

                # Enviar target a CoppeliaSim
                if self.coppelia_connected:
                    self._write_targets(targets)

                # PID solo para visualización en el frontend
                if active in joints:
                    pid_data = self.pid.update(targets[active], joints[active], dt)
                else:
                    pid_data = {"setpoint": 0, "error": 0, "output": 0, "p": 0, "i": 0, "d": 0}

                sensors = self._demo_sensors()

                if self.mqtt_connected:
                    self.mqtt_client.publish(TOPIC_STATE_JOINTS,  json.dumps(joints),   qos=0)
                    self.mqtt_client.publish(TOPIC_STATE_PID,     json.dumps(pid_data), qos=0)
                    self.mqtt_client.publish(TOPIC_STATE_SENSORS, json.dumps(sensors),  qos=0)

                elapsed = time.time() - t0
                time.sleep(max(0, dt - elapsed))

        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
        finally:
            self.running = False
            self.mqtt_client.publish(TOPIC_STATUS,
                json.dumps({"connected": False, "coppelia": False, "mode": "offline"}), qos=1, retain=True)
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("✅ Bridge stopped")


def main():
    bridge = UR5Bridge()
    def _stop(sig, frame):
        bridge.running = False
    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)
    bridge.run()

if __name__ == "__main__":
    main()
