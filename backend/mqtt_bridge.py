#!/usr/bin/env python3
"""
UR5 MQTT ↔ CoppeliaSim Bridge
[React] ──WS:9001──▸ [Mosquitto] ──TCP:1883──▸ [Bridge] ──ZMQ:23000──▸ [CoppeliaSim]
"""

import json, time, math, threading, signal, sys, os, random
from typing import Dict
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

MQTT_HOST     = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT     = int(os.getenv("MQTT_BROKER_PORT", "1883"))
COPPELIA_HOST = os.getenv("COPPELIASIM_HOST", "localhost")
COPPELIA_PORT = int(os.getenv("COPPELIASIM_PORT", "23000"))

TOPIC_CMD_JOINTS    = "ur5/cmd/joints"
TOPIC_CMD_GRIPPER   = "ur5/cmd/gripper"
TOPIC_CMD_PID       = "ur5/cmd/pid"
TOPIC_STATE_JOINTS  = "ur5/state/joints"
TOPIC_STATE_PID     = "ur5/state/pid"
TOPIC_STATE_SENSORS = "ur5/state/sensors"
TOPIC_STATUS        = "ur5/status"

KEYS = ["J1", "J2", "J3", "J4", "J5", "J6"]

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


class UR5Bridge:

    def __init__(self):
        self.sim         = None
        self.handles     = []
        self._lock       = threading.Lock()
        self.targets     = {k: 0.0 for k in KEYS}
        self.active      = "J2"
        self.running     = True
        self.cop_ok      = False
        self.mqtt_ok     = False

        self.client = mqtt.Client(
            client_id="ur5_bridge",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message
        self.client.will_set(TOPIC_STATUS,
            json.dumps({"connected": False, "coppelia": False}), qos=1, retain=True)

    # ── MQTT ──────────────────────────────────────────────────────────

    def _on_connect(self, client, *_):
        self.mqtt_ok = True
        client.subscribe([(TOPIC_CMD_JOINTS, 1), (TOPIC_CMD_GRIPPER, 1), (TOPIC_CMD_PID, 1)])
        self._pub_status()
        print("✅ MQTT conectado")

    def _on_disconnect(self, *_):
        self.mqtt_ok = False

    def _on_message(self, client, userdata, msg):
        try:
            p = json.loads(msg.payload.decode())
            if msg.topic == TOPIC_CMD_JOINTS:
                with self._lock:
                    for k in KEYS:
                        if k in p:
                            self.targets[k] = float(p[k])
                    if "activeJoint" in p:
                        self.active = p["activeJoint"]
        except Exception:
            pass

    # ── CoppeliaSim ───────────────────────────────────────────────────

    def connect_coppelia(self) -> bool:
        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            print(f"🔗 Conectando a CoppeliaSim {COPPELIA_HOST}:{COPPELIA_PORT}...")
            self.sim = RemoteAPIClient(host=COPPELIA_HOST, port=COPPELIA_PORT).require("sim")
            self.handles = self._find_joints()

            if len(self.handles) != 6:
                print(f"⚠️  {len(self.handles)} joints encontrados (se necesitan 6) → DEMO")
                return False

            # Leer posición actual y usarla como targets iniciales
            # Esto evita que el robot snapee a 0° al arrancar
            pos = self._read()
            if pos:
                with self._lock:
                    self.targets.update(pos)
                print(f"✅ Posición inicial sincronizada: {pos}")

            self.cop_ok = True
            self._pub_status()
            print("✅ CoppeliaSim conectado")
            return True

        except ImportError:
            print("❌ pip install coppeliasim-zmqremoteapi-client")
            return False
        except Exception as e:
            print(f"❌ CoppeliaSim error: {e} → DEMO")
            return False

    def _find_joints(self) -> list:
        for names in [UR5_JOINT_NAMES, UR5_JOINT_NAMES_ALT]:
            try:
                h = [self.sim.getObject(n) for n in names]
                if len(h) == 6:
                    print(f"✅ Joints: {names[0]}...")
                    return h
            except Exception:
                pass
        # Auto-discover
        found, idx = [], 0
        while True:
            try:
                h = self.sim.getObjects(idx, self.sim.sceneobject_joint)
                if h == -1: break
                found.append(h); idx += 1
            except Exception:
                break
        if len(found) >= 6:
            found.sort(key=lambda h: self.sim.getObjectAlias(h, 1))
            print(f"✅ Joints auto-descubiertos ({len(found)} total)")
            return found[:6]
        return []

    def _read(self) -> Dict[str, float]:
        try:
            return {KEYS[i]: round(math.degrees(self.sim.getJointPosition(h)), 2)
                    for i, h in enumerate(self.handles)}
        except Exception:
            self.cop_ok = False
            self._pub_status()
            return {}

    def _write(self, targets: Dict[str, float]):
        """setJointTargetPosition — método correcto para control dinámico en CoppeliaSim."""
        try:
            for i, h in enumerate(self.handles):
                self.sim.setJointTargetPosition(h, math.radians(targets[KEYS[i]]))
        except Exception as e:
            print(f"⚠️  Write error: {e}")
            self.cop_ok = False
            self._pub_status()

    # ── Demo ──────────────────────────────────────────────────────────

    _demo_pos = {k: 0.0 for k in KEYS}

    def _demo_step(self, targets):
        for k in KEYS:
            self._demo_pos[k] = round(
                self._demo_pos[k] + 0.2 * (targets[k] - self._demo_pos[k]), 2)
        return dict(self._demo_pos)

    # ── Status ────────────────────────────────────────────────────────

    def _pub_status(self):
        self.client.publish(TOPIC_STATUS, json.dumps({
            "connected": self.mqtt_ok,
            "coppelia":  self.cop_ok,
            "mode": "live" if self.cop_ok else "demo",
            "timestamp": time.time(),
        }), qos=1, retain=True)

    # ── Main loop ─────────────────────────────────────────────────────

    def run(self):
        print("╔══════════════════════════════════════╗")
        print("║   UR5 MQTT ↔ CoppeliaSim Bridge      ║")
        print("╚══════════════════════════════════════╝")

        try:
            self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ MQTT: {e}"); sys.exit(1)

        time.sleep(1)
        self.connect_coppelia()
        if not self.cop_ok:
            print("ℹ️  DEMO MODE — conecta CoppeliaSim y reinicia el bridge")

        dt = 0.05  # 20 Hz — coincide con timestep de CoppeliaSim (50ms)
        print(f"🚀 Bridge a {int(1/dt)} Hz\n")

        try:
            while self.running:
                t0 = time.time()

                # Snapshot thread-safe de targets
                with self._lock:
                    targets = dict(self.targets)
                    active  = self.active

                if self.cop_ok:
                    # 1. Escribir targets a CoppeliaSim
                    self._write(targets)
                    # 2. Leer posición actual
                    joints = self._read()
                    if not joints:
                        joints = self._demo_step(targets)
                else:
                    joints = self._demo_step(targets)

                # PID (solo visual — CoppeliaSim tiene su propio controlador)
                measured = joints.get(active, 0.0)
                target_v = targets.get(active, 0.0)
                error    = round(target_v - measured, 2)
                pid_out  = {
                    "setpoint": round(target_v, 2),
                    "error":    error,
                    "output":   round(error * 1.0, 2),
                    "p": round(error * 1.0, 2),
                    "i": 0.0, "d": 0.0,
                }

                sensors = {
                    "temp":  round(28.0 + random.uniform(-0.5, 0.5), 1),
                    "force": round(max(0.0, abs(error) * 0.05), 1),
                }

                if self.mqtt_ok:
                    self.client.publish(TOPIC_STATE_JOINTS,  json.dumps(joints),  qos=0)
                    self.client.publish(TOPIC_STATE_PID,     json.dumps(pid_out), qos=0)
                    self.client.publish(TOPIC_STATE_SENSORS, json.dumps(sensors), qos=0)

                time.sleep(max(0.0, dt - (time.time() - t0)))

        except KeyboardInterrupt:
            print("\n🛑 Parando...")
        finally:
            self.client.publish(TOPIC_STATUS,
                json.dumps({"connected": False, "coppelia": False, "mode": "offline"}),
                qos=1, retain=True)
            self.client.loop_stop()
            self.client.disconnect()
            print("✅ Bridge detenido")


def main():
    b = UR5Bridge()
    def _stop(s, f): b.running = False
    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)
    b.run()

if __name__ == "__main__":
    main()
