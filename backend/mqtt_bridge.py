#!/usr/bin/env python3
"""
UR5 MQTT ↔ CoppeliaSim Bridge — MODO SIMPLE
Frontend manda ángulos → Bridge los pasa a CoppeliaSim → CoppeliaSim mueve el robot.
CoppeliaSim tiene su propio PID interno, no necesitamos uno propio.
"""

import json, time, math, signal, sys, os, random, threading
from typing import Dict
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

MQTT_HOST     = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT     = int(os.getenv("MQTT_BROKER_PORT", "1883"))
COPPELIA_HOST = os.getenv("COPPELIASIM_HOST", "localhost")
COPPELIA_PORT = int(os.getenv("COPPELIASIM_PORT", "23000"))

T_CMD    = "ur5/cmd/joints"
T_STATUS = "ur5/status"
T_JOINTS = "ur5/state/joints"
T_PID    = "ur5/state/pid"
T_SENS   = "ur5/state/sensors"

KEYS = ["J1","J2","J3","J4","J5","J6"]

UR5_NAMES = [
    "/UR5/joint",
    "/UR5/link/joint",
    "/UR5/link/joint/link/joint",
    "/UR5/link/joint/link/joint/link/joint",
    "/UR5/link/joint/link/joint/link/joint/link/joint",
    "/UR5/joint/link/joint/link/joint/link/joint/link/joint/link/joint",
]
UR5_NAMES_ALT = ["/UR5_joint1","/UR5_joint2","/UR5_joint3",
                  "/UR5_joint4","/UR5_joint5","/UR5_joint6"]


class Bridge:
    def __init__(self):
        self.sim        = None
        self.handles    = []
        self._lock      = threading.Lock()
        self.targets    = {k: 0.0 for k in KEYS}
        self.running    = True
        self.cop_ok     = False
        self.mqtt_ok    = False

        self.client = mqtt.Client(
            client_id="ur5_bridge",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message
        self.client.will_set(T_STATUS,
            json.dumps({"connected":False,"coppelia":False,"mode":"offline"}),
            qos=1, retain=True)

    # ── MQTT ──────────────────────────────────────────────────────────────

    def _on_connect(self, client, *_):
        self.mqtt_ok = True
        client.subscribe(T_CMD, qos=1)
        self._pub_status()
        print("✅ MQTT conectado")

    def _on_disconnect(self, *_):
        self.mqtt_ok = False
        print("⚠️  MQTT desconectado")

    def _on_message(self, client, userdata, msg):
        try:
            p = json.loads(msg.payload.decode())
            with self._lock:
                for k in KEYS:
                    if k in p:
                        self.targets[k] = float(p[k])
            print(f"📥 Targets: { {k: round(self.targets[k],1) for k in KEYS} }")
        except Exception as e:
            print(f"⚠️  Mensaje malo: {e}")

    # ── CoppeliaSim ───────────────────────────────────────────────────────

    def connect_coppelia(self) -> bool:
        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            print(f"🔗 Conectando CoppeliaSim {COPPELIA_HOST}:{COPPELIA_PORT}...")
            self.sim = RemoteAPIClient(host=COPPELIA_HOST, port=COPPELIA_PORT).require("sim")

            # Buscar joints
            handles = []
            for names in [UR5_NAMES, UR5_NAMES_ALT]:
                try:
                    handles = [self.sim.getObject(n) for n in names]
                    if len(handles) == 6:
                        print(f"✅ Joints encontrados: {names[0]}...")
                        break
                except Exception:
                    handles = []

            # Auto-descubrimiento si no encontró por nombre
            if len(handles) != 6:
                print("🔍 Buscando joints en la escena...")
                found, idx = [], 0
                while True:
                    try:
                        h = self.sim.getObjects(idx, self.sim.sceneobject_joint)
                        if h == -1: break
                        alias = self.sim.getObjectAlias(h, 1)
                        print(f"   Joint encontrado: {alias}")
                        found.append(h); idx += 1
                    except Exception:
                        break
                if len(found) >= 6:
                    found.sort(key=lambda h: self.sim.getObjectAlias(h, 1))
                    handles = found[:6]

            if len(handles) != 6:
                print(f"❌ Solo encontré {len(handles)} joints — necesito 6. DEMO MODE.")
                return False

            self.handles = handles

            # Leer posición actual → usarla como target inicial (no saltar a 0°)
            actual = self._read_positions()
            if actual:
                with self._lock:
                    self.targets.update(actual)
                print(f"✅ Posición inicial: {actual}")

            self.cop_ok = True
            self._pub_status()
            print("✅ CoppeliaSim listo — control directo activado")
            return True

        except ImportError:
            print("❌ Instala: pip install coppeliasim-zmqremoteapi-client")
            return False
        except Exception as e:
            print(f"❌ CoppeliaSim: {e}")
            return False

    def _read_positions(self) -> Dict[str,float]:
        try:
            return {KEYS[i]: round(math.degrees(self.sim.getJointPosition(h)), 2)
                    for i,h in enumerate(self.handles)}
        except Exception as e:
            print(f"⚠️  Error leyendo posición: {e}")
            self.cop_ok = False
            self._pub_status()
            return {}

    def _write_targets(self, targets: Dict[str,float]):
        """Pasa los targets directamente a CoppeliaSim. Su PID interno hace el movimiento."""
        try:
            for i,h in enumerate(self.handles):
                self.sim.setJointTargetPosition(h, math.radians(targets[KEYS[i]]))
        except Exception as e:
            print(f"⚠️  Error escribiendo targets: {e}")
            self.cop_ok = False
            self._pub_status()

    # ── Demo (sin CoppeliaSim) ────────────────────────────────────────────

    _demo = {k: 0.0 for k in KEYS}

    def _demo_step(self, targets):
        for k in KEYS:
            self._demo[k] = round(self._demo[k] + 0.15*(targets[k]-self._demo[k]), 2)
        return dict(self._demo)

    # ── Status ────────────────────────────────────────────────────────────

    def _pub_status(self):
        self.client.publish(T_STATUS, json.dumps({
            "connected": self.mqtt_ok,
            "coppelia":  self.cop_ok,
            "mode": "live" if self.cop_ok else "demo",
        }), qos=1, retain=True)

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        print("╔══════════════════════════════════════╗")
        print("║   UR5 Bridge — Modo Simple           ║")
        print("║   Frontend → CoppeliaSim directo     ║")
        print("╚══════════════════════════════════════╝\n")

        try:
            self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ MQTT no conectó: {e}"); sys.exit(1)

        time.sleep(1)
        self.connect_coppelia()
        if not self.cop_ok:
            print("ℹ️  DEMO MODE — CoppeliaSim no conectado\n")

        dt = 0.05  # 20 Hz
        print(f"🚀 Corriendo a {int(1/dt)} Hz\n")

        try:
            while self.running:
                t0 = time.time()

                with self._lock:
                    targets = dict(self.targets)

                if self.cop_ok:
                    # 1. Mandar targets a CoppeliaSim
                    self._write_targets(targets)
                    # 2. Leer posición real
                    actual = self._read_positions()
                    if not actual:
                        actual = self._demo_step(targets)
                else:
                    actual = self._demo_step(targets)

                # Publicar posición real al frontend
                if self.mqtt_ok:
                    self.client.publish(T_JOINTS, json.dumps(actual), qos=0)

                    # PID visual simple (solo error, sin controlador propio)
                    active = "J2"
                    err = round(targets.get(active,0) - actual.get(active,0), 2)
                    self.client.publish(T_PID, json.dumps({
                        "setpoint": round(targets.get(active,0), 2),
                        "error": err, "output": 0,
                        "p": 0, "i": 0, "d": 0
                    }), qos=0)

                    self.client.publish(T_SENS, json.dumps({
                        "temp":  round(28 + random.uniform(-0.3,0.3), 1),
                        "force": round(max(0, abs(err)*0.05), 1)
                    }), qos=0)

                time.sleep(max(0, dt - (time.time()-t0)))

        except KeyboardInterrupt:
            print("\n🛑 Parando...")
        finally:
            self.client.publish(T_STATUS,
                json.dumps({"connected":False,"coppelia":False,"mode":"offline"}),
                qos=1, retain=True)
            self.client.loop_stop()
            self.client.disconnect()
            print("✅ Bridge detenido")


def main():
    b = Bridge()
    def stop(s,f): b.running = False
    signal.signal(signal.SIGINT,  stop)
    signal.signal(signal.SIGTERM, stop)
    b.run()

if __name__ == "__main__":
    main()
