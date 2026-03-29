#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  UR5 MQTT ↔ CoppeliaSim Bridge                              ║
║  Connects the React frontend to CoppeliaSim via MQTT         ║
║                                                              ║
║  Architecture:                                               ║
║  [React] ──WS:9001──▸ [Mosquitto] ──TCP:1883──▸ [Bridge]    ║
║                                        │                     ║
║                                  [CoppeliaSim ZMQ:23000]     ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import time
import math
import threading
import signal
import sys
import os
from typing import Dict, Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ── Load environment ──
load_dotenv()

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
COPPELIA_HOST = os.getenv("COPPELIASIM_HOST", "localhost")
COPPELIA_PORT = int(os.getenv("COPPELIASIM_PORT", "23000"))
STREAM_PORT = int(os.getenv("STREAM_PORT", "8081"))
STREAM_FPS = int(os.getenv("STREAM_FPS", "15"))

# ── MQTT Topics ──
TOPIC_CMD_JOINTS   = "ur5/cmd/joints"      # Frontend → Bridge: target joint angles
TOPIC_CMD_GRIPPER  = "ur5/cmd/gripper"      # Frontend → Bridge: gripper open/close
TOPIC_CMD_PID      = "ur5/cmd/pid"          # Frontend → Bridge: PID params
TOPIC_STATE_JOINTS = "ur5/state/joints"     # Bridge → Frontend: actual joint angles
TOPIC_STATE_PID    = "ur5/state/pid"        # Bridge → Frontend: PID state
TOPIC_STATE_SENSORS= "ur5/state/sensors"    # Bridge → Frontend: sensor data
TOPIC_STATUS       = "ur5/status"           # Bridge → Frontend: connection status

# ── UR5 Joint names in CoppeliaSim ──
UR5_JOINT_NAMES = [
    "/UR5/joint",                                                              # J1 - Base
    "/UR5/link/joint",                                                         # J2 - Shoulder
    "/UR5/link/joint/link/joint",                                              # J3 - Elbow
    "/UR5/link/joint/link/joint/link/joint",                                   # J4 - Wrist 1
    "/UR5/link/joint/link/joint/link/joint/link/joint",                        # J5 - Wrist 2
    "/UR5/joint/link/joint/link/joint/link/joint/link/joint/link/joint",       # J6 - Wrist 3
]

# Alternative joint naming (some CoppeliaSim scenes use this)
UR5_JOINT_NAMES_ALT = [
    "/UR5_joint1",
    "/UR5_joint2",
    "/UR5_joint3",
    "/UR5_joint4",
    "/UR5_joint5",
    "/UR5_joint6",
]


class PIDController:
    """Simple PID controller for each joint."""
    def __init__(self, kp=1.0, ki=0.1, kd=0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_error = 0.0
        self.integral_limit = 20.0  # límite más bajo para evitar wind-up

    def update(self, setpoint: float, measured: float, dt: float) -> dict:
        error = setpoint - measured
        # Resetear integral si el setpoint cambió mucho (evita wind-up)
        if abs(error - self.prev_error) > 30:
            self.integral = 0.0
        self.integral = max(-self.integral_limit,
                           min(self.integral_limit,
                               self.integral + error * dt))
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        self.prev_error = error

        p_term = self.kp * error
        i_term = self.ki * self.integral
        d_term = self.kd * derivative
        output = p_term + i_term + d_term

        return {
            "setpoint": round(setpoint, 2),
            "error": round(error, 2),
            "output": round(output, 2),
            "p": round(p_term, 2),
            "i": round(i_term, 2),
            "d": round(d_term, 2),
        }

    def set_params(self, kp=None, ki=None, kd=None):
        if kp is not None: self.kp = kp
        if ki is not None: self.ki = ki
        if kd is not None: self.kd = kd


class UR5Bridge:
    """Main bridge between MQTT and CoppeliaSim."""

    def __init__(self):
        self.sim = None
        self.joint_handles = []
        self.target_angles: Dict[str, float] = {
            "J1": 0, "J2": 0, "J3": 0, "J4": 0, "J5": 0, "J6": 0
        }
        self.gripper_closed = False
        self.pid = PIDController()
        self.active_joint = "J2"
        self.running = True
        self.coppelia_connected = False
        self.mqtt_connected = False

        # ── MQTT Client ──
        self.mqtt_client = mqtt.Client(
            client_id="ur5_bridge",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_message = self._on_mqtt_message

        # Will message: if bridge disconnects, notify frontend
        self.mqtt_client.will_set(
            TOPIC_STATUS,
            json.dumps({"connected": False, "coppelia": False}),
            qos=1,
            retain=True
        )

    # ── MQTT Callbacks ──

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("✅ MQTT: Connected to broker")
            self.mqtt_connected = True
            # Subscribe to command topics
            client.subscribe(TOPIC_CMD_JOINTS, qos=1)
            client.subscribe(TOPIC_CMD_GRIPPER, qos=1)
            client.subscribe(TOPIC_CMD_PID, qos=1)
            # Publish online status
            self._publish_status()
        else:
            print(f"❌ MQTT: Connection failed (rc={rc})")

    def _on_mqtt_disconnect(self, client, userdata, flags, rc, properties=None):
        print(f"⚠️  MQTT: Disconnected (rc={rc})")
        self.mqtt_connected = False

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())

            if msg.topic == TOPIC_CMD_JOINTS:
                # Update target angles from frontend
                for key in ["J1", "J2", "J3", "J4", "J5", "J6"]:
                    if key in payload:
                        self.target_angles[key] = float(payload[key])
                if "activeJoint" in payload:
                    self.active_joint = payload["activeJoint"]

            elif msg.topic == TOPIC_CMD_GRIPPER:
                self.gripper_closed = payload.get("closed", False)

            elif msg.topic == TOPIC_CMD_PID:
                self.pid.set_params(
                    kp=payload.get("kp"),
                    ki=payload.get("ki"),
                    kd=payload.get("kd")
                )

        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️  MQTT: Bad message on {msg.topic}: {e}")

    # ── CoppeliaSim Connection ──

    def connect_coppelia(self) -> bool:
        """Connect to CoppeliaSim via ZMQ Remote API."""
        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            print(f"🔗 CoppeliaSim: Connecting to {COPPELIA_HOST}:{COPPELIA_PORT}...")
            client = RemoteAPIClient(host=COPPELIA_HOST, port=COPPELIA_PORT)
            self.sim = client.require("sim")

            # Try to get joint handles
            self.joint_handles = []
            joint_names_to_try = UR5_JOINT_NAMES

            # First try default naming
            try:
                for name in UR5_JOINT_NAMES:
                    handle = self.sim.getObject(name)
                    self.joint_handles.append(handle)
                print(f"✅ CoppeliaSim: Found UR5 joints (standard naming)")
            except Exception:
                # Try alternative naming
                self.joint_handles = []
                try:
                    for name in UR5_JOINT_NAMES_ALT:
                        handle = self.sim.getObject(name)
                        self.joint_handles.append(handle)
                    print(f"✅ CoppeliaSim: Found UR5 joints (alternative naming)")
                except Exception:
                    # Auto-discover: search for joints
                    print("🔍 CoppeliaSim: Auto-discovering UR5 joints...")
                    self.joint_handles = self._auto_discover_joints()

            if len(self.joint_handles) == 6:
                self.coppelia_connected = True
                print(f"✅ CoppeliaSim: Connected! Found 6 joints")
                # Leer posición actual y usarla como target e interp inicial — evita snap a 0°
                initial = self.read_joint_positions()
                if initial:
                    self.target_angles.update(initial)
                    print(f"✅ CoppeliaSim: Initial targets synced to current position")
                self._publish_status()
                return True
            else:
                print(f"⚠️  CoppeliaSim: Found {len(self.joint_handles)} joints (expected 6)")
                print("   Make sure you have a UR5 robot in your scene.")
                print("   The bridge will run in DEMO MODE.")
                return False

        except ImportError:
            print("❌ CoppeliaSim: coppeliasim_zmqremoteapi_client not installed")
            print("   Run: pip install coppeliasim-zmqremoteapi-client")
            return False
        except Exception as e:
            print(f"❌ CoppeliaSim: Connection failed — {e}")
            print("   Make sure CoppeliaSim is running with ZMQ Remote API enabled.")
            print("   The bridge will run in DEMO MODE.")
            return False

    def _auto_discover_joints(self) -> list:
        """Try to auto-discover UR5 joint handles using multiple strategies."""
        handles = []
        
        # Strategy 1: Named patterns
        search_patterns = [
            [f"/UR5/joint{i}" for i in range(1, 7)],
            [f"/UR5_joint{i}" for i in range(1, 7)],
            [f"UR5_joint{i}" for i in range(1, 7)],
            [f"/joint{i}" for i in range(1, 7)],
            [f"joint{i}" for i in range(1, 7)],
        ]
        for pattern in search_patterns:
            try:
                handles = [self.sim.getObject(name) for name in pattern]
                if len(handles) == 6:
                    print(f"   Found joints with pattern: {pattern[0]}...")
                    return handles
            except Exception:
                handles = []
                continue

        # Strategy 2: Scan all scene objects for joints
        print("   Scanning entire scene for joint objects...")
        try:
            all_joints = []
            idx = 0
            while True:
                try:
                    handle = self.sim.getObjects(idx, self.sim.sceneobject_joint)
                    if handle == -1:
                        break
                    alias = self.sim.getObjectAlias(handle, 1)
                    all_joints.append((handle, alias))
                    print(f"   Found joint: {alias} (handle={handle})")
                    idx += 1
                except Exception:
                    break
            
            if len(all_joints) >= 6:
                # Sort by name for consistent ordering
                all_joints.sort(key=lambda x: x[1])
                handles = [j[0] for j in all_joints[:6]]
                print(f"   Using first 6 of {len(all_joints)} joints found by scene scan")
                return handles
        except Exception as e:
            print(f"   Scene scan failed: {e}")

        return handles

    # ── Publishing ──

    def _publish_status(self):
        status = {
            "connected": self.mqtt_connected,
            "coppelia": self.coppelia_connected,
            "mode": "live" if self.coppelia_connected else "demo",
            "timestamp": time.time()
        }
        self.mqtt_client.publish(TOPIC_STATUS, json.dumps(status), qos=1, retain=True)

    def _publish_joints(self, joints: dict):
        self.mqtt_client.publish(TOPIC_STATE_JOINTS, json.dumps(joints), qos=0)

    def _publish_pid(self, pid_data: dict):
        self.mqtt_client.publish(TOPIC_STATE_PID, json.dumps(pid_data), qos=0)

    def _publish_sensors(self, sensor_data: dict):
        self.mqtt_client.publish(TOPIC_STATE_SENSORS, json.dumps(sensor_data), qos=0)

    # ── Read from CoppeliaSim ──

    def read_joint_positions(self) -> Dict[str, float]:
        """Read current joint positions from CoppeliaSim (in degrees)."""
        if not self.coppelia_connected or not self.joint_handles:
            return {}
        try:
            positions = {}
            keys = ["J1", "J2", "J3", "J4", "J5", "J6"]
            for i, handle in enumerate(self.joint_handles):
                rad = self.sim.getJointPosition(handle)
                positions[keys[i]] = round(math.degrees(rad), 2)
            return positions
        except Exception as e:
            print(f"⚠️  CoppeliaSim: Error reading joints — {e}")
            self.coppelia_connected = False
            self._publish_status()
            return {}

    def write_joint_targets(self):
        """Envía los targets directamente a CoppeliaSim — su controlador interno maneja el movimiento."""
        if not self.coppelia_connected or not self.joint_handles:
            return
        try:
            keys = ["J1", "J2", "J3", "J4", "J5", "J6"]
            for i, handle in enumerate(self.joint_handles):
                self.sim.setJointTargetPosition(handle, math.radians(self.target_angles[keys[i]]))
        except Exception as e:
            print(f"⚠️  CoppeliaSim: Error writing joints — {e}")
            self.coppelia_connected = False
            self._publish_status()

    # ── Demo Mode (simulated data) ──

    def _demo_joints(self) -> Dict[str, float]:
        """Generate simulated joint positions for demo mode."""
        if not hasattr(self, '_demo_positions'):
            self._demo_positions = {"J1": 0, "J2": 0, "J3": 0, "J4": 0, "J5": 0, "J6": 0}

        import random
        for key in self._demo_positions:
            target = self.target_angles[key]
            current = self._demo_positions[key]
            # Fast response (0.3) so controls feel responsive in demo mode
            self._demo_positions[key] = round(
                current + 0.3 * (target - current) + (random.random() - 0.5) * 0.1, 2
            )
        return dict(self._demo_positions)

    def _demo_sensors(self) -> Dict[str, float]:
        """Generate simulated sensor data for demo mode."""
        import random
        if not hasattr(self, '_demo_temp'):
            self._demo_temp = 28.0
            self._demo_force = 0.0

        self._demo_temp = round(max(20, min(80, self._demo_temp + (random.random() - 0.48) * 0.15)), 1)
        self._demo_force = round(max(0, min(20, self._demo_force + (random.random() - 0.5) * 0.3)), 1)
        return {"temp": self._demo_temp, "force": self._demo_force}

    # ── Main Loop ──

    def run(self):
        """Start the bridge."""
        print("╔══════════════════════════════════════════╗")
        print("║     UR5 MQTT ↔ CoppeliaSim Bridge       ║")
        print("╚══════════════════════════════════════════╝")
        print()

        # Connect MQTT
        try:
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"❌ MQTT: Cannot connect to {MQTT_HOST}:{MQTT_PORT} — {e}")
            print("   Make sure Mosquitto is running:")
            print("   mosquitto -c backend/mosquitto.conf")
            sys.exit(1)

        # Wait for MQTT connection
        time.sleep(1)

        # Connect CoppeliaSim
        self.connect_coppelia()

        if not self.coppelia_connected:
            print()
            print("ℹ️  Running in DEMO MODE (simulated data)")
            print("   Start CoppeliaSim and restart this bridge for live mode.")
            print()

        # Main control loop at 20Hz — debe coincidir con el timestep de CoppeliaSim (50ms)
        dt = 0.05  # 50ms
        print(f"🚀 Bridge running at {int(1/dt)} Hz — Press Ctrl+C to stop")
        print()

        try:
            while self.running:
                loop_start = time.time()

                # ── Read joint positions ──
                if self.coppelia_connected:
                    joints = self.read_joint_positions()
                    if not joints:  # CoppeliaSim disconnected
                        joints = self._demo_joints()
                else:
                    joints = self._demo_joints()

                # ── Write targets a CoppeliaSim cada ciclo para mantener posición ──
                # CoppeliaSim en modo POSITION necesita el target continuamente
                if self.coppelia_connected:
                    self.write_joint_targets()

                # ── Compute PID for active joint ──
                active_key = self.active_joint
                if active_key in joints:
                    pid_data = self.pid.update(
                        self.target_angles[active_key],
                        joints[active_key],
                        dt
                    )
                else:
                    pid_data = {"setpoint": 0, "error": 0, "output": 0, "p": 0, "i": 0, "d": 0}

                # ── Read sensors ──
                if self.coppelia_connected:
                    # Read force sensor from CoppeliaSim if available
                    try:
                        # Try to read proximity/force sensor
                        sensors = self._demo_sensors()  # Fallback to simulated
                    except Exception:
                        sensors = self._demo_sensors()
                else:
                    sensors = self._demo_sensors()

                # ── Publish state via MQTT ──
                if self.mqtt_connected:
                    self._publish_joints(joints)
                    self._publish_pid(pid_data)
                    self._publish_sensors(sensors)

                # ── Maintain loop rate ──
                elapsed = time.time() - loop_start
                sleep_time = max(0, dt - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n🛑 Stopping bridge...")

        finally:
            self.running = False
            # Publish offline status
            status = {"connected": False, "coppelia": False, "mode": "offline"}
            self.mqtt_client.publish(TOPIC_STATUS, json.dumps(status), qos=1, retain=True)
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("✅ Bridge stopped cleanly")


def main():
    bridge = UR5Bridge()

    # Handle SIGTERM gracefully
    def signal_handler(sig, frame):
        bridge.running = False
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    bridge.run()


if __name__ == "__main__":
    main()
