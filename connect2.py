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
# R2100   FW v2.0.722   Router AC2100
# R2350   FW v1.3.8     AIoT Router AC2350
# R3600   FW v1.0.17    AIoT Router AX3600
# RM2100  FW v2.0.23    Router Redmi AC2100
# RM1800  FW v1.0.336   AX1800 Wi-Fi 6 Mesh Router
# RA67    FW v1.0.33    AX5 Router


gw = Gateway(timeout = 4)
if gw.status < 1:
  die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))

print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))
print("mac address = {}".format(gw.mac_address))

dn = gw.device_name
gw.ssh_port = 22
if gw.ping(verbose = 0) is True:
  die(0, "Stock SSH server already installed and running")

stok = gw.web_login()
ext_name = 'misystem/set_config_iotdev'
user_id = '_username_'

def exec_cmd(cmd):
  params = { 'bssid': 'Xiaomi', 'user_id': user_id, 'ssid': ('-h' + '\n' + cmd + '\n') }
  res = requests.get(gw.apiurl + ext_name, params = params)
  return res.text

res = exec_cmd('nvram set bootdelay=5; nvram set ssh_en=1; nvram commit;')
if res != '{"code":0}':
  die('Extension "/api/{}" not working!'.format(ext_name))

cmd = ''
cmd += 'echo -e "root\\nroot" | passwd root' + '\n'
#cmd += 'sed -i \'s/channel=.*/channel="debug"/g\' /etc/init.d/dropbear' + '\n'
cmd += 'sed -i \'s/"$flg_ssh" != "1" -o "$channel" = "release"/-n ""/g\' /etc/init.d/dropbear' + '\n'
cmd += "/etc/init.d/dropbear enable" + '\n'
cmd += "/etc/init.d/dropbear restart" + '\n'
cmd += 'logger -p err -t XMiR "completed!"' + '\n'
res = exec_cmd(cmd)
#if res != '{"code":0}':
#  die('Extension "/api/misystem/set_config_iotdev" not working!!!')

time.sleep(0.5)
gw.ping(contimeout = 32)   # RSA host key generate very slow!

print("")
print("#### Connection to device {} is OK ####".format(gw.device_name))

