#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import gateway
from gateway import die


gw = gateway.Gateway()
if not gw.device_name:
  die("Устройство Xiaomi Mi Wi-Fi не найдено! (IP: {})".format(gateway.ip_addr))

fn_dir = 'firmware/'
fn_dir2 = fn_dir + '/tmp/'
fn_kernel = fn_dir2 + 'kernel.bin'
fn_rootfs = fn_dir2 + 'rootfs.bin'

os.makedirs(fn_dir2, exist_ok = True)

fn_list = [f for f in os.listdir(fn_dir) if os.path.isfile(os.path.join(fn_dir, f))]
if not fn_list:
  die("В папке {} прошивка не найдена!".format(fn_dir))

fn_local = fn_dir + fn_list[0]
print("Считываю файл {}".format(fn_local))
with open(fn_local, "rb") as file:
  data = file.read()

fw_type = None

if data[:4] == b'HDR1' or data[:4] == b'HDR2':
  fw_type = 'stock'
  die("Стоковые прошивки Xiaomi не поддерживаются!")

if data[:4] == b"\x27\x05\x19\x56":  # uImage 
  fw_type = 'factory'

if data[:10] == b"sysupgrade":  # TAR
  fw_type = 'sysupgrade'
  die("SysUpgrade прошивки (TAR-архивы) не поддерживаются!")

if not fw_type:
  die("Неизвестный тип прошивки (header = {})".format(data[:16]))

if data[:4] == b"\x27\x05\x19\x56":
  fw_type = 'factory'

if fw_type == 'factory':
  pos = 0x0C
  kernel_size = int.from_bytes(data[pos:pos+4], byteorder='big')
  kernel_size += 0x40
  if (kernel_size > len(data) - 1024):
    die("initramfs прошивки не поддерживаются!")
  rootfs_offset = data.find(b'UBI#', kernel_size)
  if (rootfs_offset <= 0):
    die("В прошивке не найден раздел rootfs!")
  #if (rootfs_offset < 4*1024*1024):
  #  kernel_size = rootfs_offset
  kernel_data = data[:kernel_size]
  with open(fn_kernel, "wb") as file:
    file.write(kernel_data)
  with open(fn_rootfs, "wb") as file:
    file.write(data[rootfs_offset:])

sys.exit(0)      hhjhjhhjhj

print("Загружаем: " + fn_local)
gw.upload(fn_local, fn_remote)

for filename in [fn for fn in os.listdir(fn_dir) if fn.split(".")[-1] in ['lmo']]:
  print("Загружаем: " + filename)
  gw.upload(fn_dir + '/' + filename, '/tmp/' + filename)

print("Загрузка файлов завершена")

print ("Настраиваем...")
gw.run_cmd("sh " + fn_remote)

print("Готово! Языковые файлы установлены.")
