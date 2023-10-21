#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import platform
import ctypes
import binascii

import xmir_base
from envbuffer import *


class XQImgHdr(ctypes.Structure):
  _fields_ = [("magic",   ctypes.c_uint),      # HDR1
              ("sign",    ctypes.c_uint),      # offset of sign block
              ("crc32",   ctypes.c_uint),      # crc32 check sum
              ("type",    ctypes.c_ushort),    # ROM type (12 = miwifi_ssh.bin)
              ("model",   ctypes.c_short),     # device number
              ("files",   ctypes.c_uint * 8)]  # array of section-offset

class XQImgFile(ctypes.Structure):
  _fields_ = [("magic",   ctypes.c_ushort),    # BE BA
              ("rsvd0",   ctypes.c_ushort), 
              ("addr",    ctypes.c_uint),      # Flash Address
              ("size",    ctypes.c_uint),      # size of file
              ("mtd",     ctypes.c_short),     # mtd number for flashing
              ("dummy",   ctypes.c_short),
              ("name",    ctypes.c_char * 32)] # Filename

from xqmodel import xqModelList
from xqmodel import get_modelid_by_name

def DIE(msg):
  print('ERROR:', msg)
  sys.exit(1)

def buf_align(buf, align, padfill = b'\x00'):
  mod = len(buf) & (align - 1)
  if mod > 0:
    buf += padfill * (align - mod)
  return buf


class XQImage():
  testmode = False
  model = None
  type = 0
  version = None
  align = 128*1024
  padfill = b'\xFF'
  files = []  # list of files
  
  def __init__(self, model, type = 0, testmode = False):
    self.testmode = testmode
    self.model = model.upper()
    self.type = type
    self.header = XQImgHdr()
    self.version = None
    self.files = []
    self.data = None

  def add_version(self, version, channel = 'release'):
    self.version = None
    if version is None:
      return
    data = "config core 'version'\n"
    data += "\t" + "option ROM '{}'\n".format(version)
    if channel:
      data += "\t" + "option CHANNEL '{}'\n".format(channel.lower())
    data += "\t" + "option HARDWARE '{}'\n".format(self.model)
    self.version = data.encode('latin_1')
    self.version = buf_align(self.version, 16)
    self.add_file(self.version, 'xiaoqiang_version', align = 16)

  def add_file(self, data, name, mtd = None, align = 0, padfill = b'\xFF'):
    file = types.SimpleNamespace()
    file.data = data
    if align is not None:
      if align == 0: # use default
        file.data = buf_align(data, self.align, self.padfill)
      if align >= 2:
        file.data = buf_align(data, align, padfill)
    file.header = XQImgFile()
    file.header.magic = int.from_bytes(b'\xBE\xBA', byteorder='little')
    file.header.rsvd0 = 0 
    file.header.addr = 0xFFFFFFFF
    file.header.size = len(file.data)
    file.header.mtd = 0xFFFF if mtd is None else mtd
    file.header.dummy = 0
    file.header.name = name.encode('latin_1')
    self.files.append(file)
  
  def build_image(self, sign = None):
    self.data = None
    buf = bytearray()
    self.header = XQImgHdr()
    self.header.magic = int.from_bytes(b'HDR1', byteorder='little')
    self.header.sign = 0
    self.header.crc32 = 0
    self.header.type = self.type
    self.header.model = get_modelid_by_name(self.model)
    buf += bytes(self.header)
    for i, f in enumerate(self.files):
      self.header.files[i] = len(buf)
      buf += bytes(f.header)
      buf += f.data
    self.header.sign = len(buf)
    if sign:    
      buf += sign
    else:
      buf += self.build_sign()
    self.header.crc32 = 0
    buf[:ctypes.sizeof(self.header)] = bytes(self.header)
    self.header.crc32 = 0xFFFFFFFF - binascii.crc32(buf[12:])  # JAMCRC
    buf[:ctypes.sizeof(self.header)] = bytes(self.header)
    self.data = buf
    return buf
  
  def save_image(self, filename, sign = None):
    self.outfilename = filename
    data = self.build_image(sign)
    with open(filename, 'wb') as file:
      file.write(data)

  def build_sign(self):
    def i2b(value):
      return value.to_bytes(4, byteorder='little')
    payload = None
    if self.model == "R3G":
      poffset = 0x1058
      payload = i2b(0x416078) + i2b(0) + i2b(0) + i2b(0x402810)   # 2.25.124, 2.28.44
    if self.model == "R3P":
      poffset = 0x1058
      payload = i2b(0x416078) + i2b(0) + i2b(0) + i2b(0x402810)   # 2.16.29
    if self.model == "R3600":  # AX3600
      poffset = 0x1070
      payload = i2b(0x415290) + i2b(0) + i2b(0x402634) + i2b(0)   # 1.0.17 ... 1.1.19
    if self.model == "RA69":   # AX6
      poffset = 0x1070
      payload = i2b(0x4152A8) + i2b(0) + i2b(0x402634) + i2b(0)   #        ... 1.1.10
    if self.model == "RA70":   # AX9000
      poffset = 0x1078
      payload = i2b(0x4152D0) + i2b(0) + i2b(0x40265C) + i2b(0)   # 1.0.82 ... 1.0.140
    if self.model == "RA72":   # AX6000
      poffset = 0x1078
      payload = i2b(0x4152E0) + i2b(0) + i2b(0x402630) + i2b(0)   # 1.0.41 ... 1.0.55
    if not payload:
      DIE('HDR1 Payload is not defined for device "{}".'.format(self.model))
    # add header of sign section (16 bytes)
    sign = i2b(poffset) + (b'\x00' * 12)
    # add fake sign 
    size = poffset - len(payload)
    if self.testmode:
      for i in range(0, size, 4):
        sign += (0xEAA00000 + i).to_bytes(4, byteorder='little')
    else:
      sign += b'\xFF' * size
    # add payload
    sign += payload
    return sign


def create_xqimage(model, name, mtd, size, data, outfilename = None):
  testmode = True if os.getenv('XQTEST', default = '0') == '1' else False
  img = XQImage(model, testmode = testmode)
  if data is None:
    data = b''
  if len(data) > size:
    data = data[:size]
  filedata = data
  if len(data) < size:
    filedata += b'\xFF' * (size - len(data))
  #img.add_version("1.1.1")
  img.add_file(filedata, name, mtd)
  if outfilename:
    img.save_image(outfilename)
  else:
    img.build_image()
  return img


def build_xq_openwrt(fwdir, model, outfilename):
  model = model.upper()
  MAX_KERNEL_SIZE = 0x400000  # 4MiB
  ERASE_SIZE=128*1024
  kernel = None
  rootfs = None
  fit = None
  bl = None
  fn_list = [f for f in os.listdir(fwdir) if os.path.isfile(os.path.join(fwdir, f))]  
  for i, fname in enumerate(fn_list):
    fname = fwdir + fname
    fsize = os.path.getsize(fname)
    if fsize < 80*1024:
      continue    
    with open(fname, "rb") as file:
      fdata = file.read()    
    if fdata[:4] == b"\x27\x05\x19\x56":  # uImage 
      print('Parse image file "{}" ...'.format(fname))
      pos = 0x0C
      kernel_size = int.from_bytes(fdata[pos:pos+4], byteorder='big')
      kernel_size += 0x40
      kernel_name = fdata[0x20:0x40]
      if kernel_name.find(b'Breed') == 0 or kernel_name.find(b'NAND Flash') == 0:
        if bl:
          DIE('Second bootloader founded')
        bl = types.SimpleNamespace()
        bl.data = fdata
        bl.type = 'breed' if kernel_name.find(b'Breed') == 0 else ''
        if len(fdata) > 2*ERASE_SIZE or kernel_size > 2*ERASE_SIZE:
          DIE('Bootloader size is too large! (size: {} KB)'.format(len(fdata) // 1024))
        continue
      if kernel:
        DIE('Second kernel founded')
      if kernel_size < 0x100000:
        DIE('Kernel size is too small! (size: {} KB)'.format(kernel_size // 1024))
      kernel = types.SimpleNamespace()
      kernel.ostype = ''
      kernel.data = fdata[:kernel_size]      
      if kernel_name[0:1] == b'\x03' or kernel_name[0:1] == b'\x04':    # padavan kernel version
        if kernel_name[2:3] == b'\x03':  # padavan fw version
          kernel.ostype = 'padavan'
          kernel_size = int.from_bytes(kernel_name[0x1C:0x20], byteorder='big')
          if kernel_size > MAX_KERNEL_SIZE:
            DIE('Kernel size is too large! (size: {} KB)'.format(kernel_size // 1024))
          #kernel.data = fdata[:kernel_size]
          x = fdata.find(b'hsqs', kernel_size)
          if x < 0:
            DIE('Rootfs not found in padavan firmware')
          if fdata[x+28:x+32] != b'\x04\x00\x00\x00':
            DIE('Rootfs not found in padavan firmware')
          if rootfs:
            DIE('Second rootfs founded')
          kernel.data = fdata[:x]
          if x > MAX_KERNEL_SIZE:
            DIE('Padavan kernel size is too large! (size: {} KB)'.format(x // 1024))
          rootfs = types.SimpleNamespace()
          rootfs.data = fdata[x:]
          continue
      if kernel_size > MAX_KERNEL_SIZE:
        DIE('Kernel size is too large! (size: {} KB)'.format(kernel_size // 1024))
      if kernel_size + 0x100000 < len(fdata):
        data = fdata[kernel_size:]
        x = data.find(b'UBI#\x01\x00\x00\x00')
        if x >= 0:
          if rootfs:
            DIE('Second rootfs founded')
          rootfs = types.SimpleNamespace()
          rootfs.data = data[x:]
    if fdata[:8] == b'UBI#\x01\x00\x00\x00':
      print('Parse image file "{}" ...'.format(fname))
      if rootfs:
        DIE('Second rootfs founded')
      rootfs = types.SimpleNamespace()
      rootfs.data = fdata
  if bl and not kernel:
    kernel = types.SimpleNamespace()
    kernel.ostype = 'BL'
    if not kernel and not rootfs:
      DIE('The firmware was not found in the "{}" folder!'.format(fwdir))
    if not rootfs:
      DIE('Cannot found rootfs image')
    x = rootfs.data.find(b'\x01\x00\x00\x06' + b'kernel' + b'\x00')
    if x > 0x800 and x <= 0x4000:
      if kernel:
        DIE('Second kernel founded into FIT image')
      fit = rootfs
      rootfs = None
    if not kernel and not fit:
      DIE('Cannot found kernel image')
    if kernel.ostype == 'padavan':
      if not bl or (bl and bl.type != 'breed'):
        DIE('Padavan firmware supported only with Breed bootloader')      
  if bl:
    BREED_ENV_ADDR = 0x60000
    BREED_ENV_OFFSET = BREED_ENV_ADDR
    BREED_ENV_SIZE = 0x20000
    if bl.type == 'breed':
      if len(bl.data) > BREED_ENV_OFFSET:
        data = bl.data[:BREED_ENV_OFFSET]
      else:
        data = buf_align(bl.data, BREED_ENV_OFFSET, b'\xFF')
      bl.data = data      
      env_file = fwdir + 'breed_env.txt'
      if os.path.exists(env_file): 
        with open(env_file, 'r', encoding = 'latin_1') as file:
          env_data = file.read()
        print('Parse ENV file: "{}"'.format(env_file))
        env = EnvBuffer(env_data, '\n', encoding = 'latin_1')
        env_data = env.pack(BREED_ENV_SIZE)
        bl.data += b'ENV\x00' + env_data[4:]
      if model == 'R3P' and len(bl.data) > 2*ERASE_SIZE:
        DIE('Router R3P have small bootloader partition')
  img = XQImage(model)
  #img.add_version("1.1.1")
  mtd = None
  if fit:
    if model == 'R3600':
      mtd = { 'rootfs': 12, 'rootfs_1': 13 }
    if not mtd:
      DIE('Device "{}" currently not supported.'.format(model))
    img.add_file(fit.data, 'firmware_squashfs.bin', mtd['rootfs'])
    img.add_file(fit.data, 'firmware_squashfs.bin', mtd['rootfs_1'])
  else:
    mtd = { 'bootloader': 1, 'kernel0': 8, 'kernel1': 9, 'rootfs0': 10, 'rootfs1': 11, 'overlay': 12 }
    if bl:
      img.add_file(bl.data, 'bootloader.bin', mtd['bootloader'])
    if kernel.ostype != 'BL':
      img.add_file(kernel.data, 'kernel0.bin', mtd['kernel0'])
      img.add_file(kernel.data, 'kernel1.bin', mtd['kernel1'])
      img.add_file(rootfs.data, 'rootfs.bin', mtd['rootfs0'])
  img.save_image(outfilename)


# python xqimage.py R3600 crash.bin 10 0x80000 "\x12\x34\xAB\xCD" r3600_crash_1234.bin
# hexdump -v -s 6 -n 4 -e '2/1 "%02x "' /dev/mtd10 | echo ""
# python xqimage.py R3G crash.bin 5 0x40000 "\xA5\x5A\x00\x00" r3g_crash_A55A.bin
# python xqimage.py R3G crash.bin 5 0x40000 "" r3g_crash.bin
# python xqimage.py R3G miwifi_r3g_openwrt_21.02.bin

if __name__ == "__main__":
  fn = ''

  if len(sys.argv) > 6:
    model = sys.argv[1]
    name = sys.argv[2]
    mtd = int(sys.argv[3])
    size = sys.argv[4]
    size = int(size, 16) if size.lower().startswith('0x') else int(size, 10)
    if size <= 0:
      size = 128*1024
    data = None
    if len(sys.argv[5]) > 0:
      data = sys.argv[5]      
      data = data.encode('latin_1').decode('unicode-escape').encode('latin_1')
    outfilename = sys.argv[6]
    create_xqimage(model, name, mtd, size, data, outfilename)
    fn = outfilename

  if len(sys.argv) == 3:
    model = sys.argv[1]
    fn = sys.argv[2]
    build_xq_openwrt('firmware/', model, fn)    

  if fn:
    print("#### File '{}' created ####".format(fn))
  else:
    print("ERROR: Incorrect arguments!")
