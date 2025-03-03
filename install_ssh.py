#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time

import xmir_base
from gateway import *

gw = Gateway()

FN_patch     = 'data/ssh_patch.sh'
fn_patch     = '/tmp/ssh_patch.sh'
FN_install   = 'data/ssh_install.sh'
fn_install   = '/tmp/ssh_install.sh'
FN_uninstall = 'data/ssh_uninstall.sh'
fn_uninstall = '/tmp/ssh_uninstall.sh'

action = 'install'
if len(sys.argv) > 1:
    if sys.argv[1].startswith('u') or sys.argv[1].startswith('r'):
        action = 'uninstall'

if action == 'install':
    gw.upload(FN_patch, fn_patch)
    gw.upload(FN_install, fn_install)

gw.upload(FN_uninstall, fn_uninstall)

print("All files uploaded!")

print("Run scripts...")
run_script = fn_install if action == 'install' else fn_uninstall
gw.run_cmd(f"chmod +x {run_script} ; {run_script}")

time.sleep(1.5)

gw.run_cmd(f"rm -f {fn_patch} ; rm -f {fn_install} ; rm -f {fn_uninstall}")

print("Ready! The Permanent SSH patch installed.")
