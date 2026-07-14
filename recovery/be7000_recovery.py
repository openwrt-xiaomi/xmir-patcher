#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BE7000 (RC06) recovery — DHCP + TFTP + прогресс как в MIWIFIRepairTool.

Usage:
    sudo python3 be7000_recovery.py <firmware.bin>
    sudo python3 be7000_recovery.py --iface en5 miwifi_rc06.bin

Что делает:
 1. Слушает UDP :67 (DHCP) и UDP :69 (TFTP RRQ) на указанном iface.
 2. На DHCP DISCOVER отвечает OFFER + на REQUEST → ACK. Раздаёт роутеру IP
    192.168.31.1, объявляет себя (192.168.31.100) TFTP-сервером и указывает
    имя бутфайла (option 66 + 67 + BOOTP file field).
 3. На TFTP RRQ (независимо от имени файла) отдаёт указанную прошивку
    блоками с честной поддержкой blksize/tsize/timeout OACK.
 4. Печатает статус на месте: state, MAC, IP, прогресс, скорость,
    прогрессбар — как в MIWIFIRepairTool.

Безопасно к соседям: отвечает ТОЛЬКО на MAC начинающиеся с 58:ea:1f (Xiaomi
OUI), другие устройства игнорирует. Bind — только на один iface с
192.168.31.100/24 (параметр --iface).

Требует sudo для bind на 67/69.
"""

import argparse
import ipaddress
import os
import socket
import struct
import sys
import time
import threading

# ── defaults ────────────────────────────────────────────────────────────────

DEFAULT_IFACE       = "en5"
SERVER_IP           = "192.168.31.100"          # this Mac
CLIENT_IP           = "192.168.31.1"            # what we hand to the router
NETMASK             = "255.255.255.0"
XIAOMI_OUI_PREFIXES = (b"\x58\xea\x1f",)        # only respond to Xiaomi MACs

DHCP_MAGIC          = b"\x63\x82\x53\x63"
TFTP_BLOCK_DEFAULT  = 512
TFTP_TIMEOUT_S      = 5.0


# ── shared status object (printed periodically) ─────────────────────────────

class Status:
    """Central state for the pretty status line — updated by DHCP/TFTP threads."""
    STATES = ("WAITING", "DHCP_OFFER", "DHCP_ACK", "TFTP_XFER", "COMPLETE", "ERROR")

    def __init__(self, fw_path, bootfile):
        self.lock         = threading.Lock()
        self.state        = "WAITING"
        self.mac          = "-"
        self.ip           = "-"
        self.fw_path      = fw_path
        self.fw_size      = os.path.getsize(fw_path)
        self.bootfile     = bootfile
        self.sent_bytes   = 0
        self.total_bytes  = self.fw_size
        self.speed_bps    = 0
        self.xfer_started = None
        self.xfer_done    = None
        self.error_msg    = None
        self.event_log    = []          # tuples (time, tag, msg) — for scroll-back

    def event(self, tag, msg):
        with self.lock:
            self.event_log.append((time.time(), tag, msg))
            # trim so unbounded runs don't eat memory
            if len(self.event_log) > 200:
                self.event_log = self.event_log[-100:]

    def set(self, **kw):
        with self.lock:
            for k, v in kw.items():
                setattr(self, k, v)


def _fmt_bytes(n):
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} TB"


def _fmt_speed(bps):
    if bps <= 0:
        return "-"
    return f"{_fmt_bytes(bps)}/s"


def _progress_bar(cur, total, width=32):
    if total <= 0:
        return "-" * width
    pct = min(1.0, cur / total)
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


def status_printer(st, stop_flag):
    """Print in-place status line every 250ms + scroll-back of recent events."""
    ansi_up   = "\033[F"
    ansi_clr  = "\033[2K"
    lines_out = 0
    printed_events = 0

    print("\n" * 5, end="")  # reserve 5 lines for the status block
    lines_out = 5

    while not stop_flag.is_set():
        with st.lock:
            state       = st.state
            mac         = st.mac
            ip          = st.ip
            sent        = st.sent_bytes
            total       = st.total_bytes
            speed       = st.speed_bps
            fw          = os.path.basename(st.fw_path)
            bootfile    = st.bootfile
            new_events  = st.event_log[printed_events:]
            printed_events = len(st.event_log)

        # First: print any new events ABOVE the status block (scroll-back).
        # Move cursor up over the status block, print events (they push status
        # block down naturally when they scroll), then re-draw block.
        sys.stdout.write(ansi_up * lines_out)
        for ts, tag, msg in new_events:
            ts_str = time.strftime("%H:%M:%S", time.localtime(ts))
            sys.stdout.write(ansi_clr + f"[{ts_str}] {tag:5s} {msg}\n")

        # Now the status block (5 lines):
        pct = 100.0 * sent / total if total else 0
        bar = _progress_bar(sent, total)
        state_col = {
            "WAITING":    "\033[90m",  # dim
            "DHCP_OFFER": "\033[33m",  # yellow
            "DHCP_ACK":   "\033[36m",  # cyan
            "TFTP_XFER":  "\033[32m",  # green
            "COMPLETE":   "\033[1;32m",  # bold green
            "ERROR":      "\033[1;31m",  # bold red
        }.get(state, "")
        reset = "\033[0m"

        sys.stdout.write(ansi_clr + f"┌─ BE7000 recovery ──────────────────────────────────────────────┐\n")
        sys.stdout.write(ansi_clr + f"│ state: {state_col}{state:<12}{reset}    peer: {mac}   ip: {ip}\n")
        sys.stdout.write(ansi_clr + f"│ file:  {fw}  ({_fmt_bytes(total)})     bootfile-name: {bootfile}\n")
        sys.stdout.write(ansi_clr + f"│ {bar}  {pct:5.1f}%  {_fmt_bytes(sent)}/{_fmt_bytes(total)}  {_fmt_speed(speed)}\n")
        sys.stdout.write(ansi_clr + f"└────────────────────────────────────────────────────────────────┘\n")

        lines_out = 5
        sys.stdout.flush()
        time.sleep(0.25)


# ── helpers ─────────────────────────────────────────────────────────────────

def ip4(s):
    return socket.inet_aton(s)


def mac_str(b):
    return ":".join(f"{x:02x}" for x in b)


# ── DHCP (minimal — DISCOVER→OFFER + REQUEST→ACK) ───────────────────────────

def parse_dhcp_options(payload):
    i = 0
    while i < len(payload):
        code = payload[i]
        if code == 0xff:
            return
        if code == 0x00:
            i += 1
            continue
        length = payload[i + 1]
        yield code, payload[i + 2 : i + 2 + length]
        i += 2 + length


def build_dhcp_reply(req, msg_type, bootfile):
    xid    = req[4:8]
    chaddr = req[28:44]
    file_field = bootfile.encode()[:127].ljust(128, b"\x00")
    sname_field = SERVER_IP.encode()[:63].ljust(64, b"\x00")

    pkt = bytearray(240)
    pkt[0]     = 0x02
    pkt[1]     = 0x01
    pkt[2]     = 0x06
    pkt[3]     = 0x00
    pkt[4:8]   = xid
    pkt[8:10]  = b"\x00\x00"
    # Echo client's flags — Xiaomi U-Boot sends DISCOVER with flags=0x0000
    # and drops OFFERs whose flag bits don't match its request.  Setting
    # 0x8000 (broadcast) here silently breaks the handshake even though
    # RFC 2131 says server is free to broadcast the reply.
    pkt[10:12] = req[10:12]                 # mirror flags from request
    pkt[12:16] = b"\x00\x00\x00\x00"
    pkt[16:20] = ip4(CLIENT_IP)
    pkt[20:24] = ip4(SERVER_IP)
    pkt[24:28] = b"\x00\x00\x00\x00"
    pkt[28:44] = chaddr
    pkt += sname_field
    pkt += file_field
    pkt += DHCP_MAGIC

    def opt(code, value):
        pkt.extend(bytes([code, len(value)]) + value)

    # Options that match what dnsmasq (which the router accepts) sends.
    # Verified against a working recovery of a real BE7000: the router's
    # U-Boot DHCP client wants EXACTLY this set — option 28 (broadcast
    # addr) and options 58/59 (renewal timers) are what it looks for to
    # know the ACK is complete.  Missing 28 makes it silently retry.
    subnet_bcast = str(
        ipaddress.ip_network(f"{SERVER_IP}/{NETMASK}", strict=False).broadcast_address
    )
    opt(53, bytes([msg_type]))              # DHCP msg type
    opt(54, ip4(SERVER_IP))                 # server identifier
    opt(51, struct.pack("!I", 3600))        # lease time (1h)
    opt(58, struct.pack("!I", 1800))        # T1 renewal
    opt(59, struct.pack("!I", 3150))        # T2 rebinding
    opt(1,  ip4(NETMASK))                   # subnet mask
    opt(28, ip4(subnet_bcast))              # broadcast address
    opt(3,  ip4(SERVER_IP))                 # router
    opt(66, SERVER_IP.encode())             # TFTP server (as string)
    pkt.append(0xff)
    return bytes(pkt)


def dhcp_worker(iface_ip, bootfile, status):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_DONTROUTE, 1)
    except OSError:
        pass
    s.bind(("0.0.0.0", 67))
    status.event("DHCP", f"listening on :67, server={iface_ip}")

    while True:
        try:
            data, src = s.recvfrom(2048)
        except Exception as e:
            status.event("DHCP", f"recv err: {e}")
            continue
        try:
            _dhcp_handle(data, s, iface_ip, bootfile, status)
        except Exception as e:
            status.event("DHCP", f"handler err: {e}")


def _dhcp_handle(data, sock, iface_ip, bootfile, status):
    if len(data) < 240 or data[236:240] != DHCP_MAGIC:
        return
    chaddr = data[28:34]
    if not any(chaddr.startswith(p) for p in XIAOMI_OUI_PREFIXES):
        return

    msg_type = None
    for code, val in parse_dhcp_options(data[240:]):
        if code == 53 and len(val) == 1:
            msg_type = val[0]
            break

    if msg_type == 1:
        status.event("DHCP", f"DISCOVER from {mac_str(chaddr)} → OFFER {CLIENT_IP}")
        status.set(state="DHCP_OFFER", mac=mac_str(chaddr))
        reply = build_dhcp_reply(data, msg_type=2, bootfile=bootfile)
    elif msg_type == 3:
        status.event("DHCP", f"REQUEST from {mac_str(chaddr)} → ACK {CLIENT_IP}")
        status.set(state="DHCP_ACK", mac=mac_str(chaddr), ip=CLIENT_IP)
        reply = build_dhcp_reply(data, msg_type=5, bootfile=bootfile)
    else:
        return

    subnet_bcast = str(
        ipaddress.ip_network(f"{iface_ip}/{NETMASK}", strict=False).broadcast_address
    )
    for dst in (subnet_bcast, "255.255.255.255"):
        try:
            sock.sendto(reply, (dst, 68))
            break
        except OSError as e:
            status.event("DHCP", f"sendto {dst}:68 failed: {e}")


# ── TFTP server ─────────────────────────────────────────────────────────────

def tftp_serve(client, firmware_path, options, status):
    block_size = int(options.get("blksize", TFTP_BLOCK_DEFAULT))
    fw_size    = os.path.getsize(firmware_path)

    conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    conn.settimeout(TFTP_TIMEOUT_S)

    if options:
        ack_opts = {}
        if "blksize" in options: ack_opts["blksize"] = str(block_size)
        if "tsize"   in options: ack_opts["tsize"]   = str(fw_size)
        if "timeout" in options: ack_opts["timeout"] = options["timeout"]
        oack = b"\x00\x06"
        for k, v in ack_opts.items():
            oack += k.encode() + b"\x00" + v.encode() + b"\x00"
        status.event("TFTP", f"OACK {ack_opts} → {client}")
        conn.sendto(oack, client)
        try:
            reply, _ = conn.recvfrom(1024)
        except socket.timeout:
            status.event("TFTP", "no OACK-ACK, continuing with default blocksize")
            block_size = TFTP_BLOCK_DEFAULT

    status.set(state="TFTP_XFER", ip=client[0],
               sent_bytes=0, total_bytes=fw_size,
               xfer_started=time.time())
    t0 = time.time()
    last_speed_calc = t0
    last_speed_sent = 0

    with open(firmware_path, "rb") as f:
        block_num = 1
        while True:
            chunk = f.read(block_size)
            pkt = b"\x00\x03" + struct.pack("!H", block_num & 0xFFFF) + chunk
            got_ack = False
            for retry in range(5):
                conn.sendto(pkt, client)
                try:
                    reply, _ = conn.recvfrom(1024)
                except socket.timeout:
                    if retry == 4:
                        break
                    continue
                if reply[:2] == b"\x00\x04":
                    ack_blk = struct.unpack("!H", reply[2:4])[0]
                    if ack_blk == (block_num & 0xFFFF):
                        got_ack = True
                        break
                elif reply[:2] == b"\x00\x05":
                    err = reply[4:].split(b"\x00")[0].decode(errors="replace")
                    status.event("TFTP", f"client ERROR: {err}")
                    status.set(state="ERROR", error_msg=err)
                    conn.close()
                    return
            if not got_ack:
                status.event("TFTP", f"block {block_num} timeout after 5 retries")
                status.set(state="ERROR", error_msg=f"block {block_num} lost")
                conn.close()
                return

            sent = min(block_num * block_size, fw_size)
            now  = time.time()
            if now - last_speed_calc >= 0.3:
                speed = int((sent - last_speed_sent) / (now - last_speed_calc))
                status.set(sent_bytes=sent, speed_bps=speed)
                last_speed_calc = now
                last_speed_sent = sent

            if len(chunk) < block_size:
                status.set(state="COMPLETE",
                           sent_bytes=fw_size,
                           speed_bps=int(fw_size / max(time.time() - t0, 0.001)),
                           xfer_done=time.time())
                elapsed = time.time() - t0
                status.event(
                    "TFTP",
                    f"COMPLETE — {block_num} blocks, {fw_size} bytes, "
                    f"{elapsed:.1f}s, avg {_fmt_speed(int(fw_size / max(elapsed, 0.001)))}",
                )
                conn.close()
                return
            block_num += 1


def tftp_worker(firmware_path, status):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 69))
    status.event("TFTP", "listening on :69 for RRQ")

    while True:
        data, src = s.recvfrom(2048)
        if len(data) < 4:
            continue
        opcode = struct.unpack("!H", data[:2])[0]
        if opcode != 1:
            continue
        parts = data[2:].split(b"\x00")
        parts = [p for p in parts if p]
        if len(parts) < 2:
            continue
        filename = parts[0].decode(errors="replace")
        mode     = parts[1].decode(errors="replace").lower()
        options  = {}
        i = 2
        while i + 1 < len(parts):
            options[parts[i].decode().lower()] = parts[i + 1].decode()
            i += 2
        status.event("TFTP", f"RRQ from {src[0]} name='{filename}' opts={options}")
        threading.Thread(
            target=tftp_serve,
            args=(src, firmware_path, options, status),
            daemon=True,
        ).start()


# ── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("firmware", help="Path to .bin firmware image to serve")
    ap.add_argument("--iface", default=DEFAULT_IFACE,
                    help=f"Interface with {SERVER_IP} assigned (default {DEFAULT_IFACE})")
    ap.add_argument("--bootfile", default=None,
                    help="Filename to advertise in BOOTP file field "
                         "(default: basename of the firmware file — this is "
                         "what BE7000 U-Boot wants, e.g. "
                         "miwifi_rc06_firmware_65d1d_1.1.38.bin)")
    args = ap.parse_args()
    if args.bootfile is None:
        args.bootfile = os.path.basename(args.firmware)

    if os.geteuid() != 0:
        print("Run with sudo — need :67 and :69.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.firmware):
        print(f"Firmware not found: {args.firmware}", file=sys.stderr)
        sys.exit(1)

    st = Status(args.firmware, args.bootfile)
    stop = threading.Event()

    threading.Thread(target=dhcp_worker,
                     args=(SERVER_IP, args.bootfile, st),
                     daemon=True).start()
    threading.Thread(target=tftp_worker,
                     args=(args.firmware, st),
                     daemon=True).start()
    threading.Thread(target=status_printer,
                     args=(st, stop),
                     daemon=True).start()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        stop.set()
        time.sleep(0.3)
        print("\nstopped")


if __name__ == "__main__":
    main()
