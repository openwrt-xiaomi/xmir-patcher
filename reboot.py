#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform

import xmir_base
import gateway
from gateway import die


gw = gateway.Gateway(detect_ssh = False)

ssh = gw.detect_ssh(verbose = 1, interactive = True)
if ssh > 0:
  print('Send command "reboot" via SSH ...')
  gw.run_cmd("reboot")
else:
  if not gw.stok:
    gw.web_login()
  print('Send command "reboot" via WEB API ...')
  if not gw.reboot_device():
    die('Can\'t run reboot command.')

if not gw.wait_shutdown(10):
  die('The "reboot" command did not shutdown the device.')

print("Reboot activated!")
