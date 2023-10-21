#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import xmir_base
import gateway
from gateway import die
import read_info


if len(sys.argv) <= 1:
  die("Bootloader name not specified!")
bl_name = sys.argv[1]
bl_name = bl_name.strip().lower()


gw = gateway.Gateway()
dn = gw.device_name
if not gw.device_name:
  die("Xiaomi Mi Wi-Fi device not found! (IP: {})".format(gateway.ip_addr))

fn_dir    = 'bootloader/'
fn_remote = '/tmp/bootloader.bin'
fn_local  = None

if bl_name == 'breed':
  if dn != 'R3G' and dn != 'R3P' and dn != 'RM2100':
    die("Breed bootloader cannot be installed on this device!")
  fn_local = fn_dir + 'breed_r3g_eng.bin'

if bl_name == 'uboot':
  fn_local = fn_dir + 'uboot_{}.bin'.format(gw.device_name)

if not fn_local:
  die('Incorrect bootloader name!')

if not os.path.exists(fn_local):
  die('File "{}" not found'.format(fn_local))

dev = read_info.DevInfo(verbose = 0, infolevel = 1)
if dev.info.cpu_arch != 'mips':
  die("Currently support only MIPS arch!")

dev.get_bootloader()
if not dev.bl.img:
  die("Can't dump current bootloader!")

if dev.bl.spi_rom:
  die("Not support SPI Flash ROM! (now supported only NAND)")

addr = None
for p, part in enumerate(dev.partlist):
  if part['addr'] == 0 and part['size'] > 0x00800000:  # 8MiB
    continue  # skip "ALL" part
  if part['addr'] == 0:
    name = part['name']
    fname = ''.join(e for e in name if e.isalnum())
    addr = part['addr']
    size = part['size']

if addr is None:
  die("No matching partition found!")

gw.upload(fn_local, fn_remote)
print ('Writing data to partition "{}" (addr: {}) ...'.format(name, "0x%08X" % addr))
gw.run_cmd('mtd write {bin} "{name}"'.format(bin=fn_remote, name=name))

print('Ready! Bootloader "{}" installation is complete.'.format(bl_name))
