#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import platform
import ctypes
import binascii
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from xqimage import *
from gateway import *
from read_info import *
from envbuffer import *


def i2b(value):
  return value.to_bytes(4, byteorder='little')

def build_sign(model, ver):
  model = model.upper()
  payload = None
  if model == "R3G":        # TEST
    poffset = 0x1070
    payload = b'\x66' * 16  # TEST
  if model == "RA69":
    poffset = 0x1070
    payload = i2b(0x4152A8) + i2b(0) + i2b(0x402634) + i2b(0)
  if model == "RA70":
    poffset = 0x1078
    payload = i2b(0x4152D0) + i2b(0) + i2b(0x40265C) + i2b(0)
  if model == "RA72":
    poffset = 0x1078
    payload = i2b(0x4152E0) + i2b(0) + i2b(0x402630) + i2b(0)
  if model == "R3600":
    poffset = 0x1070
    payload = i2b(0x415290) + i2b(0) + i2b(0x402634) + i2b(0)
  if model == "RB03":
    poffset = 0x1078
    payload = i2b(0x4148B0) + i2b(0) + i2b(0x40263C) + i2b(0)
  if not payload:
    die('Payload is not defined for device "{}".'.format(model))
  # add header of sign section (16 bytes)
  sign = i2b(poffset) + (b'\x00' * 12)
  # add fake sign 
  sign += b'\xEA' * (poffset - len(payload))
  # add payload
  sign += payload
  return sign


gw = Gateway(timeout = 4)
if gw.status < 1:
  die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))

print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))
print("MAC Address = {}".format(gw.mac_address))

signature = build_sign(gw.device_name, gw.rom_version)

dinfo = DevInfo(gw, verbose = 0, infolevel = 0)
syslog = SysLog(gw, timeout = 10, verbose = 1, infolevel = 2)

syslog.verbose = 2
bdata = syslog.parse_bdata()
bdata.var['boot_wait'] = "on"
bdata.var['uart_en'] = "1"
bdata.var['telnet_en'] = "1"
bdata.var['ssh_en'] = "1"
bdata.var['CountryCode'] = "EU"
partname = 'bdata'
bdata.mtd = syslog.get_mtd_by_name(partname)
if not bdata.mtd:
  die('MTD partition "{}" not found!'.format(partname))
#bdata_env_size = 0x4000
bdata_env_size = 0x10000   # fixed size of BData environment buffer
bdata.buf = bdata.pack(bdata_env_size)
bdata.buf += b'\xFF' * (bdata.mtd.size - len(bdata.buf))
bdata.img = XQImage(gw.device_name)
bdata.img.add_version(gw.rom_version)
bdata.img.add_file(bdata.buf, 'bdata.bin', mtd = bdata.mtd.id)

partname = 'crash'
crash_mtd = syslog.get_mtd_by_name(partname)
if not crash_mtd:
  die('MTD partition "{}" not found!'.format(partname))

def create_crash_image(mtd, prefix, outfilename):
  crash = types.SimpleNamespace()
  crash.mtd = mtd
  if prefix is None:
    prefix = b''
  crash.buf = bytearray(prefix + b'\xFF' * (mtd.size - len(prefix)))
  crash.img = XQImage(gw.device_name)
  crash.img.add_version(gw.rom_version)
  crash.img.add_file(crash.buf, 'crash.bin', mtd = mtd.id)
  crash.img.save_image(signature, outfilename)
  print('Created hacked image file: "{}"'.format(outfilename))
  return crash

# image for activate "factory mode" via uboot (insert factory_mode=1 into kernel cmdline)
fn_crash1 = 'outdir/image_{device}_1_crash.bin'.format(device = gw.device_name)
crash1 = create_crash_image(crash_mtd, b'\xA5\x5A\x00\x00', fn_crash1)

# image for change BData environment
bdata.img.save_image(signature, 'outdir/image_{device}_2_bdata.bin'.format(device = gw.device_name))
print('Created hacked image file: "{}"'.format(bdata.img.outfilename))

# image for deactivate "factory mode" via uboot
fn_crash3 = 'outdir/image_{device}_3_crash.bin'.format(device = gw.device_name)
crash3 = create_crash_image(crash_mtd, None, fn_crash3)

print("OK_finish")

