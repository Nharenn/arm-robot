#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  UR5 Control Station — Full Setup Script (macOS)             ║
# ║                                                              ║
# ║  This installs and configures:                               ║
# ║  1. Mosquitto MQTT Broker                                    ║
# ║  2. Python dependencies (paho-mqtt, zmqremoteapi)            ║
# ║  3. Node.js dependencies (mqtt.js)                           ║
# ║  4. Ngrok for remote access                                  ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

# Navigate to project root (works from any directory)
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     UR5 Control Station — Setup              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Check for Homebrew ──
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}⚠️  Homebrew not found. Installing...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# ── 1. Install Mosquitto MQTT Broker ──
echo ""
echo -e "${GREEN}[1/4] Installing Mosquitto MQTT Broker...${NC}"
if ! command -v mosquitto &> /dev/null; then
    brew install mosquitto
    echo -e "${GREEN}  ✅ Mosquitto installed${NC}"
else
    echo -e "${YELLOW}  ℹ️  Mosquitto already installed${NC}"
fi

# ── 2. Install Python dependencies ──
echo ""
echo -e "${GREEN}[2/4] Installing Python dependencies...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}  ❌ Python3 not found. Install it: brew install python${NC}"
    exit 1
fi

cd backend
python3 -m pip install -r requirements.txt --quiet
echo -e "${GREEN}  ✅ Python packages installed${NC}"
cd ..

# Create .env from example if it doesn't exist
if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo -e "${YELLOW}  ℹ️  Created backend/.env from template${NC}"
fi

# ── 3. Install Node.js dependencies ──
echo ""
echo -e "${GREEN}[3/4] Installing Node.js dependencies...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}  ❌ Node.js not found. Install it: brew install node${NC}"
    exit 1
fi

npm install --quiet
echo -e "${GREEN}  ✅ Node packages installed${NC}"

# ── 4. Install Ngrok ──
echo ""
echo -e "${GREEN}[4/4] Installing Ngrok for remote access...${NC}"
if ! command -v ngrok &> /dev/null; then
    brew install ngrok/ngrok/ngrok
    echo -e "${GREEN}  ✅ Ngrok installed${NC}"
else
    echo -e "${YELLOW}  ℹ️  Ngrok already installed${NC}"
fi

# ── Done ──
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Setup Complete!                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "To start everything, run:"
echo -e "  ${BLUE}./scripts/start.sh${NC}"
echo ""
echo -e "Or start each service manually:"
echo -e "  ${YELLOW}1.${NC} mosquitto -c backend/mosquitto.conf"
echo -e "  ${YELLOW}2.${NC} Open CoppeliaSim → load coppeliasim/ur5_mqtt_control.ttt → Play"
echo -e "  ${YELLOW}3.${NC} cd backend && python3 mqtt_bridge.py"
echo -e "  ${YELLOW}4.${NC} cd backend && python3 video_stream.py"
echo -e "  ${YELLOW}5.${NC} npm run dev"
echo ""
echo -e "For remote access:"
echo -e "  ${YELLOW}6.${NC} ./scripts/start_remote.sh"
echo ""
