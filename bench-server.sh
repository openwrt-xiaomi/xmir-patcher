#!/usr/bin/env bash
# Прогон нового server-кандидата (VPN endpoint).
# Usage: ./bench-server.sh <server_ip> [ssh-user] [ssh-port]
#
# Даёт три вещи в связке:
#   1. Reverse-path MTR с сервера на роутер — ловит asymmetric-routing грязный transit
#      (это уже раз убивало single-TCP до 5 Mbit — см. AS35807 SkyNet SPB кейс).
#   2. Forward-path MTR с srv/роутера — обычно чистый, но всё равно надо иметь.
#   3. iperf3 UDP направленный тест — показывает реальный ceiling пути без TCP CC-шума.

set -e

SRV="${1:?server_ip required}"
SUSER="${2:-root}"
SPORT="${3:-22}"

# фиксированные для этой инфры
ROUTER_WAN="88.201.133.115"     # твой публичный WAN, для reverse-mtr с сервера
ROUTER_LAN="192.168.31.1"       # sshpass root:root
LAN_CLIENT="srv"                # ssh alias — WSL Ubuntu за роутером

echo "═══ Инспекция сервера $SRV ═══"
ssh -p "$SPORT" "$SUSER@$SRV" 'hostname; uname -r; nproc; free -m | head -2; ip -4 addr | grep inet' || {
  echo "! SSH не пускает — нужен пароль. Задай sshpass -p '...' вручную."
  exit 1
}

echo ""
echo "═══ 1. Reverse-path MTR: server → router WAN ($ROUTER_WAN) ═══"
echo "    (высокий StDev/loss на конкретном hop = грязный transit — плохо для CUBIC single-flow)"
ssh -p "$SPORT" "$SUSER@$SRV" "which mtr || (apt-get install -qq -y mtr-tiny 2>/dev/null); mtr -c 10 -rn $ROUTER_WAN"

echo ""
echo "═══ 2. Forward-path MTR: srv → server ═══"
ssh srv "which mtr || sudo apt-get install -qq -y mtr-tiny; mtr -c 10 -rn $SRV"

echo ""
echo "═══ 3. Forward MTR: srv → 8.8.8.8 (baseline через текущий main tunnel) ═══"
ssh srv "mtr -c 10 -rn 8.8.8.8"

echo ""
echo "═══ 4. iperf3 UDP 300 Mbit с роутера → сервер (сырой path без TCP CC) ═══"
echo "    Устанавливаю iperf3 на сервере и запускаю в фоне..."
ssh -p "$SPORT" "$SUSER@$SRV" 'which iperf3 || apt-get install -qq -y iperf3 2>/dev/null; pkill -f "iperf3 -s" 2>/dev/null; iperf3 -s -D -p 5201'
sleep 2
echo "    UDP 300M UP (router → server):"
sshpass -p 'root' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$ROUTER_LAN \
  "/opt/bin/iperf3 -c $SRV -p 5201 -u -b 300M -t 10 -f m 2>&1 | grep receiver | tail -1"
echo "    UDP 300M DL (server → router):"
sshpass -p 'root' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$ROUTER_LAN \
  "/opt/bin/iperf3 -c $SRV -p 5201 -u -b 300M -R -t 10 -f m 2>&1 | grep receiver | tail -1"

echo ""
echo "═══ 5. iperf3 TCP (BBR both sides) ═══"
sshpass -p 'root' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$ROUTER_LAN \
  "echo '   TCP UP:  ' && /opt/bin/iperf3 -c $SRV -p 5201 -t 10 -f m 2>&1 | grep receiver | tail -1
   echo '   TCP DL:  ' && /opt/bin/iperf3 -c $SRV -p 5201 -R -t 10 -f m 2>&1 | grep receiver | tail -1"

echo ""
echo "═══ Как читать ═══"
echo "  • MTR reverse: любой hop с Avg > 100ms или StDev > 50ms или loss > 5% → путь с сервера уебан."
echo "    Такой сервер уебёт single-TCP CUBIC до ~5 Mbit несмотря на любой раmax UDP."
echo "  • UDP iperf: показывает physical-cap без TCP-CC-шума."
echo "  • Delta UDP↔TCP: если UDP 400M а TCP 30M — потери / jitter (CUBIC не тянет), нужен BBR/Brutal."
echo "  • Если reverse-mtr чистый (Avg <60ms, StDev<10ms, 0%loss) — сервер годится."
