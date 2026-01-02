#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess

import xmir_base
import gateway
from gateway import die


gw = gateway.Gateway(detect_device = False, detect_ssh = False)

def get_header(delim, suffix = ''):
  header = delim*58 + '\n'
  header += '\n'
  header += 'Xiaomi MiR Patcher {} \n'.format(suffix)
  header += '\n'
  return header

def menu1_show():
  gw.load_config()
  print(get_header('='))
  print(' 1 - Set IP-address (current value: {})'.format(gw.ip_addr))
  print(' 2 - Connect to device (install exploit)')
  print(' 3 - Read full device info')
  print(' 4 - Create full backup')
  print(' 5 - Install EN/RU languages')
  print(' 6 - Install permanent SSH')
  print(' 7 - Install firmware (from directory "firmware")')
  print(' 8 - {{{ Other functions }}}')
  print(' 9 - [[ Reboot device ]]')
  print(' 0 - Exit')

def menu1_process(id):
  if id == 1: 
    ip_addr = input("Enter device IP-address: ")
    return [ "gateway.py", ip_addr ]
  if id == 2: return "connect.py"
  if id == 3: return "read_info.py"
  if id == 4: return "create_backup.py"
  if id == 5: return "install_lang.py"
  if id == 6: return "install_ssh.py"
  if id == 7: return "install_fw.py"
  if id == 8: return "__menu2"
  if id == 9: return "reboot.py"
  if id == 0: sys.exit(0)
  return None

def menu2_show():
  print(get_header('-', '(extended functions)'))
  print(' 1 - Set IP-address (current value: {})'.format(gw.ip_addr))
  print(' 2 - Change root password')
  print(' 3 - Read dmesg and syslog')
  print(' 4 - Create a backup of the specified partition')
  print(' 5 - Uninstall EN/RU languages')
  print(' 6 - Set kernel boot address')
  print(' 7 - Install Breed bootloader')
  print(' 8 - __test__')
  print(' 9 - [[ Reboot device ]]')
  print(' 0 - Return to main menu')

def menu2_process(id):
  if id == 1:
    ip_addr = input("Enter device IP-address: ")
    return [ "gateway.py", ip_addr ]
  if id == 2: return "passw.py"
  if id == 3: return "read_dmesg.py"
  if id == 4: return [ "create_backup.py", "part" ]
  if id == 5: return [ "install_lang.py", "uninstall" ]
  if id == 6: return "activate_boot.py"
  if id == 7: return [ "install_bl.py", "breed" ]
  if id == 8: return "test.py"
  if id == 9: return "reboot.py"
  if id == 0: return "__menu1" 
  return None

def menu_show(level):
  if level == 1:
    menu1_show()
    return 'Select: '
  else:
    menu2_show()
    return 'Choice: '

def menu_process(level, id):
  if level == 1:
    return menu1_process(id)
  else:
    return menu2_process(id)

def menu():
  level = 1
  while True:
    print('')
    prompt = menu_show(level)
    print('')
    select = input(prompt)
    print('')
    if not select:
      continue
    try:
      id = int(select)
    except Exception:
      id = -1
    if id < 0:
      continue
    cmd = menu_process(level, id)
    if not cmd:
      continue
    if cmd == '__menu1':
      level = 1
      continue
    if cmd == '__menu2':
      level = 2
      continue
    #print("cmd2 =", cmd)
    if isinstance(cmd, str):
      result = subprocess.run([sys.executable, cmd])
    else:  
      result = subprocess.run([sys.executable] + cmd)


menu()


