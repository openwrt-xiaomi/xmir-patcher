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
  supported_devices = ['R3G', 'R3P', 'RM2100', 'RA71', 'CR6606', 'CR6608', 'CR6609', 'TR609', 'TR608']
  if dn not in supported_devices:
    die("Breed bootloader cannot be installed on this device!")
  if dn in ['CR6606', 'CR6608', 'CR6609', 'TR609', 'TR608']:
    fn_local = fn_dir + 'pb-boot-cr660x.img'
  else:
    fn_local = fn_dir + 'breed_r3g_eng.bin'

if bl_name == 'uboot':
  # Check if device has a specific uboot file available
  supported_uboot_devices = ['R3G', 'R3P', 'RM2100']
  if dn not in supported_uboot_devices:
    die("U-Boot bootloader is not available for this device! Supported devices: {}".format(', '.join(supported_uboot_devices)))
  fn_local = fn_dir + 'uboot_{}.bin'.format(dn.lower())

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
name = None
size = None

# Find bootloader partition (typically at address 0, but skip large "ALL" partitions)
for p, part in enumerate(dev.partlist):
  if part['addr'] == 0 and part['size'] > 0x00800000:  # 8MiB
    continue  # skip "ALL" part
  if part['addr'] == 0:
    name = part['name']
    fname = ''.join(e for e in name if e.isalnum())
    addr = part['addr']
    size = part['size']
    break  # Take the first valid partition found

if addr is None:
  die("No matching partition found!")

# Validate that we have a proper partition name before proceeding
if not name:
  die("Invalid partition name found!")

print('Selected partition: "{}" at address 0x{:08X} (size: 0x{:08X})'.format(name, addr, size))

# Upload bootloader file to device
try:
  gw.upload(fn_local, fn_remote)
except Exception as e:
  die('Failed to upload bootloader file: {}'.format(str(e)))

print('Writing data to partition "{}" (addr: {}) ...'.format(name, "0x%08X" % addr))

# Write bootloader to partition with error handling
try:
  gw.run_cmd('mtd write {bin} "{name}"'.format(bin=fn_remote, name=name))
except Exception as e:
  die('Failed to write bootloader to partition: {}'.format(str(e)))

print('Ready! Bootloader "{}" installation is complete.'.format(bl_name))
