#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  UR5 Control Station — Remote Access via Ngrok               ║
# ║  Dominio estático: unsardonic-buckishly-mila.ngrok-free.dev  ║
# ║  La URL de Vercel es siempre la misma — no hay que cambiar   ║
# ║  nada cada vez que se arranque.                              ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Dominio estático (siempre el mismo) ──
STATIC_DOMAIN="unsardonic-buckishly-mila.ngrok-free.dev"
MQTT_WSS="wss://${STATIC_DOMAIN}"
VERCEL_LINK="https://arm-robot-pi.vercel.app?mqtt=${MQTT_WSS}"

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

# Verificar ngrok autenticado
if ! ngrok config check &>/dev/null; then
    echo -e "${RED}❌ Ngrok no autenticado.${NC}"
    echo -e "   Corre: ${YELLOW}ngrok config add-authtoken TU_TOKEN${NC}"
    exit 1
fi

echo -e "${GREEN}Iniciando túnel MQTT (dominio fijo)...${NC}"

# Iniciar ngrok con dominio estático en puerto 9001
ngrok http 9001 --domain="$STATIC_DOMAIN" --log=stdout > /tmp/ngrok_mqtt.log 2>&1 &
PIDS+=($!)

sleep 3

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  ✅ Túnel MQTT activo                                        ║${NC}"
echo -e "${CYAN}║  MQTT WSS: ${GREEN}${MQTT_WSS}${CYAN}  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🔗 Link permanente para compartir:                          ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  ${YELLOW}${VERCEL_LINK}${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}💡 Este link siempre funciona — no cambia nunca.${NC}"
echo -e "   Guárdalo o compártelo directamente."
echo ""
echo -e "Press Ctrl+C to stop"

wait
