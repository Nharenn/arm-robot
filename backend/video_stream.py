#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║  CoppeliaSim Live Video Stream (MJPEG)           ║
║  Captures the CoppeliaSim viewport and streams   ║
║  it to the React frontend via HTTP MJPEG.        ║
║                                                  ║
║  Frontend loads: <img src="localhost:8081/stream.mjpeg">
╚══════════════════════════════════════════════════╝
"""

import io
import time
import math
import os
import threading
import json
from typing import Optional, Dict

from flask import Flask, Response, render_template_string, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

COPPELIA_HOST = os.getenv("COPPELIASIM_HOST", "localhost")
COPPELIA_PORT = int(os.getenv("COPPELIASIM_PORT", "23000"))
STREAM_PORT = int(os.getenv("STREAM_PORT", "8081"))
STREAM_FPS = int(os.getenv("STREAM_FPS", "15"))

app = Flask(__name__)
CORS(app)

# Global frame buffer
latest_frame: Optional[bytes] = None
frame_lock = threading.Lock()
sim = None
vision_sensor_handle = None
coppelia_connected = False

# Joint angles received from MQTT (for animated fallback)
current_joints: Dict[str, float] = {"J1": 0, "J2": 0, "J3": 0, "J4": 0, "J5": 0, "J6": 0}
joints_lock = threading.Lock()

# ── Sensor name candidates ──
SENSOR_NAMES = [
    "/visionSensor",
    "/VisionSensor",
    "/ViewSensor",
    "visionSensor",
    "VisionSensor",
    "ViewSensor",
]


def connect_coppelia():
    """Connect to CoppeliaSim and find a vision sensor."""
    global sim, vision_sensor_handle, coppelia_connected
    try:
        from coppeliasim_zmqremoteapi_client import RemoteAPIClient
        print(f"🔗 Connecting to CoppeliaSim at {COPPELIA_HOST}:{COPPELIA_PORT}...")
        client = RemoteAPIClient(host=COPPELIA_HOST, port=COPPELIA_PORT)
        sim = client.require("sim")
        coppelia_connected = True
        print("✅ Connected to CoppeliaSim")

        # Try multiple sensor names
        for name in SENSOR_NAMES:
            try:
                vision_sensor_handle = sim.getObject(name)
                print(f"✅ Found vision sensor: {name}")
                return True
            except Exception:
                continue

        print("ℹ️  No vision sensor found in the scene")
        print("   Add a Vision Sensor and name it 'ViewSensor' for live streaming")
        vision_sensor_handle = None
        return True

    except Exception as e:
        print(f"⚠️  CoppeliaSim not available: {e}")
        return False


def capture_frame() -> Optional[bytes]:
    """Capture a frame from CoppeliaSim vision sensor."""
    global sim, vision_sensor_handle
    if sim is None or vision_sensor_handle is None:
        return None
    try:
        img, res = sim.getVisionSensorImg(vision_sensor_handle)
        if img and res[0] > 0 and res[1] > 0:
            from PIL import Image
            import numpy as np

            img_array = np.frombuffer(img, dtype=np.uint8).reshape(res[1], res[0], 3)
            img_array = np.flipud(img_array)

            pil_img = Image.fromarray(img_array)
            buffer = io.BytesIO()
            pil_img.save(buffer, format="JPEG", quality=92)
            return buffer.getvalue()
    except Exception:
        pass
    return None


def generate_fallback_frame(frame_num: int) -> bytes:
    """Generate a nice animated fallback frame showing robot arm with real joint angles."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 800, 500
    img = Image.new("RGB", (W, H), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    t = frame_num * 0.06

    # Background gradient
    for y in range(H):
        r = int(15 + 6 * math.sin(t * 0.3 + y * 0.008))
        g = int(23 + 4 * math.sin(t * 0.2 + y * 0.01))
        b = int(42 + 10 * math.sin(t * 0.15 + y * 0.012))
        draw.line([(0, y), (W, y)], fill=(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))

    # Grid
    grid_off = int((frame_num * 0.3) % 30)
    for x in range(grid_off, W, 30):
        draw.line([(x, 0), (x, H)], fill=(25, 35, 52), width=1)
    for y in range(grid_off, H, 30):
        draw.line([(0, y), (W, y)], fill=(25, 35, 52), width=1)

    # Get current joint angles
    with joints_lock:
        j = dict(current_joints)

    # Convert degrees to radians
    a1 = math.radians(j.get("J1", 0))
    a2 = math.radians(j.get("J2", 0))
    a3 = math.radians(j.get("J3", 0))
    a4 = math.radians(j.get("J4", 0))

    # Robot arm rendering
    base_x = W // 2
    base_y = H - 80

    # Base platform
    draw.rectangle([base_x - 50, base_y, base_x + 50, base_y + 25], fill=(51, 65, 85), outline=(71, 85, 105))
    draw.rectangle([base_x - 60, base_y + 25, base_x + 60, base_y + 35], fill=(41, 55, 75), outline=(61, 75, 95))

    # Base rotation indicator (J1)
    j1_indicator_r = 25
    j1_x = base_x + int(j1_indicator_r * math.sin(a1))
    j1_y = base_y + 30 - int(j1_indicator_r * 0.3 * math.cos(a1))
    draw.ellipse([base_x - 30, base_y + 20, base_x + 30, base_y + 40], fill=(41, 55, 75), outline=(59, 130, 246))
    draw.line([(base_x, base_y + 30), (j1_x, j1_y)], fill=(59, 130, 246), width=2)

    # Segment 1 (J2 - shoulder)
    seg1_len = 110
    s1_angle = -math.pi / 2 + a2 * 0.5  # Base angle offset
    x1 = base_x + int(seg1_len * math.cos(s1_angle))
    y1 = base_y + int(seg1_len * math.sin(s1_angle))
    
    # Draw segment 1 (thick arm)
    for w in range(-4, 5):
        draw.line([(base_x + w, base_y), (x1 + w, y1)], fill=(59, 130, 246), width=1)
    draw.ellipse([base_x - 8, base_y - 8, base_x + 8, base_y + 8], fill=(71, 85, 105), outline=(100, 116, 139))

    # Segment 2 (J3 - elbow)
    seg2_len = 90
    s2_angle = s1_angle + a3 * 0.5
    x2 = x1 + int(seg2_len * math.cos(s2_angle))
    y2 = y1 + int(seg2_len * math.sin(s2_angle))

    for w in range(-3, 4):
        draw.line([(x1 + w, y1), (x2 + w, y2)], fill=(96, 165, 250), width=1)
    draw.ellipse([x1 - 7, y1 - 7, x1 + 7, y1 + 7], fill=(71, 85, 105), outline=(100, 116, 139))

    # Segment 3 (J4 - wrist)
    seg3_len = 55
    s3_angle = s2_angle + a4 * 0.5
    x3 = x2 + int(seg3_len * math.cos(s3_angle))
    y3 = y2 + int(seg3_len * math.sin(s3_angle))

    for w in range(-2, 3):
        draw.line([(x2 + w, y2), (x3 + w, y3)], fill=(147, 197, 253), width=1)
    draw.ellipse([x2 - 6, y2 - 6, x2 + 6, y2 + 6], fill=(71, 85, 105), outline=(100, 116, 139))

    # End effector (gripper)
    draw.ellipse([x3 - 6, y3 - 6, x3 + 6, y3 + 6], fill=(16, 185, 129))
    # Pulsing glow
    glow_r = int(10 + 4 * math.sin(t * 3))
    draw.ellipse([x3 - glow_r, y3 - glow_r, x3 + glow_r, y3 + glow_r],
                 fill=None, outline=(16, 185, 129, 128), width=2)

    # ── Joint angle display ──
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 12)
        font_small = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 10)
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except Exception:
        font = ImageFont.load_default()
        font_small = font
        font_title = font

    # Title
    draw.text((20, 15), "UR5 ARM CONTROL", fill=(148, 163, 184), font=font_title)
    draw.text((20, 35), "DEMO MODE — Simulation", fill=(100, 116, 139), font=font_small)

    # Joint values panel
    panel_x = W - 180
    panel_y = 15
    draw.rounded_rectangle([panel_x - 10, panel_y - 5, W - 10, panel_y + 125], radius=8, fill=(20, 30, 50, 200), outline=(51, 65, 85))
    draw.text((panel_x, panel_y), "JOINT ANGLES", fill=(148, 163, 184), font=font_small)

    joint_names = ["J1", "J2", "J3", "J4", "J5", "J6"]
    colors = [(59, 130, 246), (16, 185, 129), (251, 146, 60), (168, 85, 247), (236, 72, 153), (148, 163, 184)]
    for i, jname in enumerate(joint_names):
        val = j.get(jname, 0)
        y_pos = panel_y + 18 + i * 17
        draw.text((panel_x, y_pos), f"{jname}:", fill=colors[i], font=font)
        draw.text((panel_x + 35, y_pos), f"{val:+7.1f}°", fill=(226, 232, 240), font=font)

    # Status
    if coppelia_connected:
        status_color = (251, 191, 36)
        status_text = "● CoppeliaSim — No ViewSensor"
    else:
        status_color = (59, 130, 246)
        dots = "·" * (1 + frame_num % 3)
        status_text = f"● Demo Mode {dots}"

    draw.text((20, H - 30), status_text, fill=status_color, font=font_small)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def start_mqtt_listener():
    """Subscribe to joint state from the bridge to animate the fallback."""
    try:
        import paho.mqtt.client as mqtt

        def on_connect(c, u, f, rc, p=None):
            c.subscribe("ur5/state/joints")

        def on_message(c, u, msg):
            global current_joints
            try:
                data = json.loads(msg.payload)
                with joints_lock:
                    for k in ["J1", "J2", "J3", "J4", "J5", "J6"]:
                        if k in data:
                            current_joints[k] = float(data[k])
            except Exception:
                pass

        client = mqtt.Client(
            client_id="video_stream_listener",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect("localhost", 1883)
        client.loop_forever()
    except Exception as e:
        print(f"⚠️  MQTT listener error: {e}")


def frame_producer():
    """Background thread that captures frames."""
    global latest_frame
    interval = 1.0 / STREAM_FPS
    fallback_num = 0

    while True:
        frame = capture_frame()
        if frame:
            with frame_lock:
                latest_frame = frame
        else:
            fallback = generate_fallback_frame(fallback_num)
            fallback_num += 1
            with frame_lock:
                latest_frame = fallback
        time.sleep(interval)


def generate_mjpeg():
    """Generator for MJPEG stream."""
    while True:
        with frame_lock:
            frame = latest_frame
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        time.sleep(1.0 / STREAM_FPS)


VIEWER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0f172a; overflow: hidden; }
        img { width: 100%; height: 100vh; object-fit: contain; display: block; }
    </style>
</head>
<body>
    <img src="/stream.mjpeg" alt="CoppeliaSim Live" />
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(VIEWER_HTML)


@app.route("/stream.mjpeg")
def stream():
    return Response(
        generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "coppelia": coppelia_connected,
        "sensor": vision_sensor_handle is not None
    })


def coppelia_reconnect_loop():
    """Background thread that periodically tries to reconnect to CoppeliaSim."""
    while True:
        if not coppelia_connected or vision_sensor_handle is None:
            connect_coppelia()
        time.sleep(10)


def main():
    print("╔══════════════════════════════════════════╗")
    print("║  CoppeliaSim Video Stream Server         ║")
    print("╚══════════════════════════════════════════╝")
    print()

    connect_coppelia()

    # Start MQTT listener for joint angles (for animated fallback)
    mqtt_thread = threading.Thread(target=start_mqtt_listener, daemon=True)
    mqtt_thread.start()

    # Start frame producer
    producer = threading.Thread(target=frame_producer, daemon=True)
    producer.start()

    # Start reconnection loop
    reconnect = threading.Thread(target=coppelia_reconnect_loop, daemon=True)
    reconnect.start()

    if coppelia_connected and vision_sensor_handle is not None:
        print(f"📹 Live streaming at http://localhost:{STREAM_PORT}")
    else:
        print(f"📹 Animated demo at http://localhost:{STREAM_PORT}")
        print(f"   Robot arm responds to slider controls via MQTT")

    print()
    app.run(host="0.0.0.0", port=STREAM_PORT, threaded=True)


if __name__ == "__main__":
    main()
