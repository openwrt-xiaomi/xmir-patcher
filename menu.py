#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess

import xmir_base
import gateway
from gateway import die
import i18n
import lang_config


gw = gateway.Gateway(detect_device = False, detect_ssh = False)

# Check for language preference or show language menu
current_lang = lang_config.get_language()
if current_lang not in i18n.get_supported_languages():
    current_lang = lang_config.show_language_menu()

def get_header(delim, suffix = ''):
  header = delim*58 + '\n'
  header += '\n'
  title = i18n.get_translation(current_lang, 'title')
  header += '{} {} \n'.format(title, suffix)
  header += '\n'
  return header

def menu1_show():
  gw.load_config()
  print(get_header('='))
  menu_items = i18n.get_translation(current_lang, 'main_menu')
  for i, item in enumerate(menu_items, 1):
    if i == 1:  # IP address item needs formatting
      print(' {} - {}'.format(i, item.format(gw.ip_addr)))
    else:
      print(' {} - {}'.format(i if i <= 9 else 0, item))

def menu1_process(id):
  if id == 1: 
    ip_prompt = i18n.get_translation(current_lang, 'enter_ip')
    ip_addr = input(ip_prompt)
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
  extended_suffix = i18n.get_translation(current_lang, 'extended_functions')
  print(get_header('-', extended_suffix))
  menu_items = i18n.get_translation(current_lang, 'extended_menu')
  for i, item in enumerate(menu_items, 1):
    if i == 1:  # IP address item needs formatting
      print(' {} - {}'.format(i, item.format(gw.ip_addr)))
    else:
      print(' {} - {}'.format(i if i <= 9 else 0, item))

def menu2_process(id):
  if id == 1:
    ip_prompt = i18n.get_translation(current_lang, 'enter_ip')
    ip_addr = input(ip_prompt)
    return [ "gateway.py", ip_addr ]
  if id == 2: return "passw.py"
  if id == 3: return "read_dmesg.py"
  if id == 4: return [ "create_backup.py", "part" ]
  if id == 5: return [ "install_lang.py", "uninstall" ]
  if id == 6: return "activate_boot.py"
  if id == 7: 
    # Bootloader selection submenu
    bootloader_prompt = i18n.get_translation(current_lang, 'bootloader_choice')
    bootloader_choice = input(bootloader_prompt)
    if bootloader_choice == '1':
      return [ "install_bl.py", "breed" ]
    elif bootloader_choice == '2':
      return [ "install_bl.py", "uboot" ]
    else:
      return None
  if id == 8: return "test.py"
  if id == 9: return "reboot.py"
  if id == 0: return "__menu1" 
  return None

def menu_show(level):
  if level == 1:
    menu1_show()
    return i18n.get_translation(current_lang, 'select')
  else:
    menu2_show()
    return i18n.get_translation(current_lang, 'choice')

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


