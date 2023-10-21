#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import platform

import xmir_base
import gateway
from gateway import die


gw = gateway.Gateway()

if len(sys.argv) > 1:
  new_passw = sys.argv[1]
else:
  new_passw = input("Enter new password for root user: ")

new_passw = new_passw.strip()
if len(new_passw) == 0:
  die('Typed password is not correct!')

gw.run_cmd('echo -e "{new_passw}\\n{new_passw}" | passwd root'.format(new_passw = new_passw))
time.sleep(0.5)
gw.ssh_close()
if gw.check_ssh(gw.ip_addr, gw.ssh_port, new_passw) != 0:
  die('Can\'t change password for root user via SSH')

gw.passw = new_passw
print("The root password has been changed.")
