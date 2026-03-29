#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  UR5 Control Station — Remote Access via Ngrok               ║
# ║                                                              ║
# ║  Exposes your local services to the internet securely.       ║
# ║  You can control the robot from ANY device, anywhere.        ║
# ║                                                              ║
# ║  Prerequisites:                                              ║
# ║  1. Run ./scripts/start.sh first (services must be running)  ║
# ║  2. Sign up at https://ngrok.com and get your auth token     ║
# ║  3. Run: ngrok config add-authtoken YOUR_TOKEN               ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

# Navigate to project root (works from any directory)
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PIDS=()
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Stopping tunnels...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    echo -e "${GREEN}✅ Tunnels closed${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  UR5 Remote Access — Ngrok Tunnels           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Check ngrok auth
if ! ngrok config check &>/dev/null; then
    echo -e "${RED}❌ Ngrok not authenticated.${NC}"
    echo -e "   1. Sign up free at: ${BLUE}https://dashboard.ngrok.com/signup${NC}"
    echo -e "   2. Copy your auth token from: ${BLUE}https://dashboard.ngrok.com/get-started/your-authtoken${NC}"
    echo -e "   3. Run: ${YELLOW}ngrok config add-authtoken YOUR_TOKEN${NC}"
    exit 1
fi

# ── Create ngrok config for multiple tunnels ──
NGROK_CONFIG="/tmp/ur5_ngrok.yml"
cat > "$NGROK_CONFIG" << 'EOF'
version: "2"
tunnels:
  mqtt-ws:
    proto: http
    addr: 9001
    inspect: false
  video-stream:
    proto: http
    addr: 8081
    inspect: false
EOF

echo -e "${GREEN}Starting Ngrok tunnels...${NC}"
echo ""

# Detectar config por defecto de ngrok (donde está guardado el authtoken)
DEFAULT_NGROK_CFG=""
if [ -f "$HOME/.config/ngrok/ngrok.yml" ]; then
    DEFAULT_NGROK_CFG="$HOME/.config/ngrok/ngrok.yml"
elif [ -f "$HOME/Library/Application Support/ngrok/ngrok.yml" ]; then
    DEFAULT_NGROK_CFG="$HOME/Library/Application Support/ngrok/ngrok.yml"
fi

# Pasar ambos configs: el default (authtoken) + el custom (tunnels)
if [ -n "$DEFAULT_NGROK_CFG" ]; then
    ngrok start --config "$DEFAULT_NGROK_CFG" --config "$NGROK_CONFIG" --all &
else
    ngrok start --config "$NGROK_CONFIG" --all &
fi
PIDS+=($!)

sleep 3

# Get tunnel URLs from ngrok API
echo -e "${GREEN}Fetching tunnel URLs...${NC}"
echo ""

TUNNELS=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null || echo "")

if [ -z "$TUNNELS" ]; then
    echo -e "${YELLOW}⚠️  Could not fetch tunnel info automatically.${NC}"
    echo -e "   Check: ${BLUE}http://localhost:4040${NC} for tunnel URLs"
else
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  🌐 Remote Access URLs                                  ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"

    # Parse URLs
    FRONTEND_URL=$(echo "$TUNNELS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    if ':5173' in t.get('config', {}).get('addr', ''):
        print(t['public_url'])
        break
" 2>/dev/null || echo "check http://localhost:4040")

    MQTT_URL=$(echo "$TUNNELS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    if ':9001' in t.get('config', {}).get('addr', ''):
        print(t['public_url'])
        break
" 2>/dev/null || echo "check http://localhost:4040")

    STREAM_URL=$(echo "$TUNNELS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    if ':8081' in t.get('config', {}).get('addr', ''):
        print(t['public_url'])
        break
" 2>/dev/null || echo "check http://localhost:4040")

    # Generar link de Vercel con ?mqtt= pre-configurado
    VERCEL_APP="https://arm-robotic-iud.vercel.app"
    VERCEL_LINK="${VERCEL_APP}?mqtt=${MQTT_URL}"

    echo -e "${CYAN}║  MQTT WS (ngrok): ${GREEN}${MQTT_URL}${NC}"
    echo -e "${CYAN}║  Video Stream:    ${GREEN}${STREAM_URL}${NC}"
    echo -e "${CYAN}║  Ngrok Dashboard: ${BLUE}http://localhost:4040${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  🔗 Compartir este link (ya incluye la URL de MQTT):    ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  ${YELLOW}${VERCEL_LINK}${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
fi

echo ""
echo -e "${YELLOW}Pegar el link de arriba para que el profesor acceda con MQTT ya configurado.${NC}"
echo -e "Press Ctrl+C to stop tunnels"

wait
