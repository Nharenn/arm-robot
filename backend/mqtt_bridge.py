#!/usr/bin/env python3
"""
UR5 MQTT ↔ CoppeliaSim Bridge — Direct Kinematic Control
Usa setJointPosition (cinemático) en vez de setJointTargetPosition (dinámico/PID)
para evitar oscilaciones del controlador interno de CoppeliaSim.
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


class UR5Bridge:

    def __init__(self):
        self.sim            = None
        self.handles        = []
        self._lock          = threading.Lock()
        self.targets        = {k: 0.0 for k in KEYS}   # ángulos en grados
        self.current        = {k: 0.0 for k in KEYS}   # posición actual leída
        self.active_joint   = "J2"
        self.running        = True
        self.coppelia_ok    = False
        self.mqtt_ok        = False

        self.client = mqtt.Client(
            client_id="ur5_bridge",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message
        self.client.will_set(TOPIC_STATUS,
            json.dumps({"connected": False, "coppelia": False}), qos=1, retain=True)

    # ── MQTT ──────────────────────────────────────────────────────────────

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
                        self.active_joint = p["activeJoint"]
        except Exception:
            pass

    # ── CoppeliaSim ───────────────────────────────────────────────────────

    def connect_coppelia(self) -> bool:
        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            print(f"🔗 Conectando a CoppeliaSim {COPPELIA_HOST}:{COPPELIA_PORT}...")
            self.sim = RemoteAPIClient(host=COPPELIA_HOST, port=COPPELIA_PORT).require("sim")

            # Buscar joints
            self.handles = self._find_joints()
            if len(self.handles) != 6:
                print(f"⚠️  Encontré {len(self.handles)} joints (se necesitan 6) → DEMO MODE")
                return False

            # ── CLAVE: poner joints en modo CINEMÁTICO (no dinámico) ──
            # Esto desactiva el PID interno de CoppeliaSim y permite control directo
            for h in self.handles:
                try:
                    self.sim.setObjectInt32Param(
                        h,
                        self.sim.jointintparam_dynctrlmode,
                        self.sim.jointdynctrl_free   # modo libre / cinemático
                    )
                except Exception:
                    pass

            # Leer posición actual como punto de partida
            pos = self._read()
            if pos:
                with self._lock:
                    self.targets.update(pos)
                self.current.update(pos)

            self.coppelia_ok = True
            self._pub_status()
            print("✅ CoppeliaSim conectado — modo CINEMÁTICO (sin PID interno)")
            return True

        except ImportError:
            print("❌ Instala: pip install coppeliasim-zmqremoteapi-client")
            return False
        except Exception as e:
            print(f"❌ CoppeliaSim: {e} → DEMO MODE")
            return False

    def _find_joints(self) -> list:
        naming_variants = [
            ["/UR5/joint", "/UR5/link/joint", "/UR5/link/joint/link/joint",
             "/UR5/link/joint/link/joint/link/joint",
             "/UR5/link/joint/link/joint/link/joint/link/joint",
             "/UR5/joint/link/joint/link/joint/link/joint/link/joint/link/joint"],
            [f"/UR5_joint{i}" for i in range(1, 7)],
        ]
        for names in naming_variants:
            try:
                h = [self.sim.getObject(n) for n in names]
                if len(h) == 6:
                    print(f"✅ Joints encontrados: {names[0]}...")
                    return h
            except Exception:
                pass
        # Auto-descubrimiento
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
            print(f"✅ Joints auto-descubiertos ({len(found)} encontrados)")
            return found[:6]
        return []

    def _read(self) -> Dict[str, float]:
        """Lee posición actual de CoppeliaSim en grados."""
        try:
            return {KEYS[i]: round(math.degrees(self.sim.getJointPosition(h)), 2)
                    for i, h in enumerate(self.handles)}
        except Exception:
            self.coppelia_ok = False
            self._pub_status()
            return {}

    def _write(self, targets: Dict[str, float]):
        """Escribe posición DIRECTAMENTE (cinemático) — sin PID, sin oscilación."""
        try:
            for i, h in enumerate(self.handles):
                # setJointPosition = control directo, instantáneo, sin dinámica
                self.sim.setJointPosition(h, math.radians(targets[KEYS[i]]))
        except Exception as e:
            print(f"⚠️  Write: {e}")
            self.coppelia_ok = False
            self._pub_status()

    # ── Demo mode ─────────────────────────────────────────────────────────

    def _demo_step(self, targets: Dict[str, float]) -> Dict[str, float]:
        for k in KEYS:
            self.current[k] = round(
                self.current[k] + 0.2 * (targets[k] - self.current[k]), 2)
        return dict(self.current)

    # ── Status ────────────────────────────────────────────────────────────

    def _pub_status(self):
        self.client.publish(TOPIC_STATUS, json.dumps({
            "connected": self.mqtt_ok,
            "coppelia":  self.coppelia_ok,
            "mode": "live" if self.coppelia_ok else "demo",
        }), qos=1, retain=True)

    # ── Main loop ─────────────────────────────────────────────────────────

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
        if not self.coppelia_ok:
            print("ℹ️  DEMO MODE activo")

        dt = 0.05
        print(f"🚀 Bridge corriendo a {int(1/dt)} Hz\n")

        try:
            while self.running:
                t0 = time.time()

                with self._lock:
                    targets = dict(self.targets)
                    active  = self.active_joint

                if self.coppelia_ok:
                    # ESCRIBIR target directamente (cinemático)
                    self._write(targets)
                    # LEER posición actual para el frontend
                    joints = self._read()
                    if not joints:
                        joints = self._demo_step(targets)
                else:
                    joints = self._demo_step(targets)

                # PID solo para visualización (no controla el robot)
                measured = joints.get(active, 0)
                target_a = targets.get(active, 0)
                error    = target_a - measured
                pid_data = {
                    "setpoint": round(target_a, 2),
                    "error":    round(error, 2),
                    "output":   round(error * 1.0, 2),
                    "p": round(error * 1.0, 2),
                    "i": 0.0,
                    "d": 0.0,
                }

                sensors = {
                    "temp":  round(28 + random.uniform(-0.1, 0.1), 1),
                    "force": round(max(0, abs(error) * 0.1), 1),
                }

                if self.mqtt_ok:
                    self.client.publish(TOPIC_STATE_JOINTS,  json.dumps(joints),   qos=0)
                    self.client.publish(TOPIC_STATE_PID,     json.dumps(pid_data), qos=0)
                    self.client.publish(TOPIC_STATE_SENSORS, json.dumps(sensors),  qos=0)

                time.sleep(max(0, dt - (time.time() - t0)))

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
