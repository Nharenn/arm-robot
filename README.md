# UR5 Control Station

Remote control dashboard for a UR5 6-DOF robotic arm simulated in CoppeliaSim, connected via MQTT protocol.

## Project Structure

```
.
├── src/                    # React frontend (Vite + TypeScript + Tailwind)
│   ├── components/         # UI components (Charts, ConnectionSettings, UIBlocks)
│   ├── hooks/              # Custom hooks (useMQTT, useRobotData)
│   ├── App.tsx             # Main application
│   ├── main.tsx            # Entry point
│   ├── types.ts            # TypeScript interfaces
│   └── index.css           # Global styles
├── backend/                # Python backend services
│   ├── mqtt_bridge.py      # MQTT <-> CoppeliaSim bridge (PID controller)
│   ├── video_stream.py     # MJPEG video streaming server (Flask)
│   ├── mqtt_broker.py      # Fallback Python MQTT broker
│   ├── mosquitto.conf      # Mosquitto broker configuration
│   └── requirements.txt    # Python dependencies
├── coppeliasim/            # CoppeliaSim scene and scripts
│   ├── ur5_scene_setup.lua # Lua script for joint configuration
│   ├── ur5_mqtt_control.ttt# Scene file (binary)
│   └── README_SETUP.md     # Scene setup instructions
├── scripts/                # Shell scripts for running services
│   ├── setup.sh            # Install all dependencies (macOS)
│   ├── start.sh            # Start all services locally
│   └── start_remote.sh     # Open Ngrok tunnels for remote access
├── docs/                   # Documentation
│   ├── DEPLOY.md           # Deployment guide (Vercel + Ngrok)
│   └── Informe_IEEE_UR5_MQTT.docx  # IEEE technical report
├── public/                 # Static assets
├── index.html              # HTML entry point
├── vite.config.ts          # Vite build configuration
├── tsconfig.json           # TypeScript configuration
├── tailwind.config.js      # Tailwind CSS configuration
├── vercel.json             # Vercel deployment config
└── package.json            # Node.js dependencies
```

## Architecture

```
Browser (React)  <-- WebSocket -->  Mosquitto MQTT Broker  <-- TCP -->  Python Bridge  <-- ZMQ -->  CoppeliaSim
                                         (port 9001)                   (PID Controller)            (UR5 Simulation)
```

## Quick Start

```bash
# 1. Install dependencies
./scripts/setup.sh

# 2. Open CoppeliaSim and load coppeliasim/ur5_mqtt_control.ttt, then press Play

# 3. Start all services
./scripts/start.sh

# 4. Open http://localhost:5173
```

## Remote Access

```bash
# After start.sh is running:
./scripts/start_remote.sh

# Share the generated URL with your professor
```

See [docs/DEPLOY.md](docs/DEPLOY.md) for full deployment instructions with Vercel + Ngrok.

## Tech Stack

Frontend: React 18, TypeScript, Tailwind CSS, Recharts, MQTT.js, Vite
Backend: Python 3, paho-mqtt, Flask, CoppeliaSim ZMQ Remote API
Protocol: MQTT over WebSocket (Mosquitto broker)
Deployment: Vercel (frontend) + Ngrok (backend tunnels)
