#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time

import xmir_base
from gateway import *
import i18n
import lang_config


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

# Route BE3600 variants (RD15, RD16, RN06) to connect6
if dn in ['RD15', 'RD16', 'RN06']:
    inited_gw = create_gateway(timeout = 4, die_if_sshOk = True, die_if_ftpOk = True, web_login = True, try_telnet = True)
    import connect6
    sys.exit(0)

if True:
    # init gw and check ssh
    gw = create_gateway(timeout = 4, die_if_sshOk = True, die_if_ftpOk = True, web_login = True, try_telnet = True)
    
    hackCheck = gw.detect_hackCheck(update = True)
    if hackCheck:
        print(f'hackCheck version =', hackCheck)

    exp_modules = [
        'connect6',  # arn_switch/start_binding
        'connect5',  # smartcontroller
        'connect7',  # get_icon
    ]
    
    exploit_worked = False
    exploit_warnings = []
    
    for mod_name in exp_modules:
        try:
            import_module(mod_name, gw)
            exploit_worked = True
            break  # Ok
        except ExploitFixed as e:
            print('WARN:', str(e))
            exploit_warnings.append(str(e))
            continue  # try next module
        except ExploitNotWorked as e:
            print('WARN:', str(e))
            exploit_warnings.append(str(e))
            continue  # try next module
        except Exception:
            raise
    
    # Show general exploit failure message if all exploits failed
    if not exploit_worked:
        current_lang = lang_config.get_language() or 'en'
        
        print()
        print("=" * 60)
        print(i18n.get_translation(current_lang, 'messages', 'exploit_failed_title'))
        print()
        print(i18n.get_translation(current_lang, 'messages', 'exploit_failed_message'))
        print()
        print(i18n.get_translation(current_lang, 'messages', 'exploit_failed_suggestion'))
        print("=" * 60)
        print()
