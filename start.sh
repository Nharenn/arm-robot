#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  UR5 Control Station — Start All Services                    ║
# ║                                                              ║
# ║  Starts: MQTT Broker, Python Bridge, Video Stream, Frontend  ║
# ║                                                              ║
# ║  Usage: ./start.sh                                           ║
# ║  Stop:  Press Ctrl+C (stops all services)                    ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Track PIDs for cleanup
PIDS=()

cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Stopping all services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo -e "${GREEN}✅ All services stopped${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     UR5 Control Station — Starting...        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Start MQTT Broker ──
echo -e "${GREEN}[1/4] Starting MQTT Broker...${NC}"
if command -v mosquitto &> /dev/null; then
    echo -e "${YELLOW}  ℹ️  Using Mosquitto${NC}"
    mosquitto -c backend/mosquitto.conf &
    PIDS+=($!)
else
    echo -e "${YELLOW}  ℹ️  Mosquitto not found, using Python MQTT Broker${NC}"
    cd backend
    python3 mqtt_broker.py &
    PIDS+=($!)
    cd ..
fi
sleep 1
echo -e "${GREEN}  ✅ MQTT Broker running on ports 1883 (MQTT) and 9001 (WebSocket)${NC}"

# ── 2. Start Python MQTT Bridge ──
echo -e "${GREEN}[2/4] Starting MQTT ↔ CoppeliaSim Bridge...${NC}"
cd backend
python3 mqtt_bridge.py &
PIDS+=($!)
cd ..
sleep 2
echo -e "${GREEN}  ✅ Bridge running${NC}"

# ── 3. Start Video Stream Server ──
echo -e "${GREEN}[3/4] Starting Video Stream Server...${NC}"
cd backend
python3 video_stream.py &
PIDS+=($!)
cd ..
sleep 1
echo -e "${GREEN}  ✅ Video stream on http://localhost:8081${NC}"

# ── 4. Start Frontend Dev Server ──
echo -e "${GREEN}[4/4] Starting React Frontend...${NC}"
npm run dev &
PIDS+=($!)
sleep 2

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  🚀 All services running!                               ║${NC}"
echo -e "${CYAN}║                                                          ║${NC}"
echo -e "${CYAN}║  Frontend:     http://localhost:5173                     ║${NC}"
echo -e "${CYAN}║  MQTT Broker:  localhost:1883 (TCP) / :9001 (WebSocket)  ║${NC}"
echo -e "${CYAN}║  Video Stream: http://localhost:8081                     ║${NC}"
echo -e "${CYAN}║  CoppeliaSim:  localhost:23000 (ZMQ)                     ║${NC}"
echo -e "${CYAN}║                                                          ║${NC}"
echo -e "${CYAN}║  Press Ctrl+C to stop all services                       ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Wait for all processes
wait
