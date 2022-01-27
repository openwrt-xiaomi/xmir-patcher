#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import platform
import ctypes
import binascii


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

xqModelList = [
  "<unk0>",
  "<unk1>",
  "<unk2>",
  "R1CM",    # 3
  "R2D",     # 4
  "R1CL",
  "R2CM",
  "R3",
  "R3D",     # 8
  "R3L",
  "R3P",     # 10
  "P01",
  "R3A",
  "R3G",     # 13
  "R4",
  "R4C",
  "D01",
  "R4A",
  "R4CM",
  "R4AC",
  "R3GV2",   # 20
  "R2600",
  "R2100",   # 22
  "RM2100",  # 23
  "R3600",   # 24
  "R1350",
  "R2200",
  "R2350",   # 27
  "IR1200G",
  "RM1800",
  "R2100D",  # 30
  "RA67",
  "RA69",
  "RA71",
  "CR6006",  # 34
  "CR6008",
  "CR6009",
  "RA70",
  "RA75",
  "RA72",
  "<unk40>", # 40
  "<unk41>",
  "<unk42>",
  "RA80",
  "RA81",
  "RA82",
  "RA83",
  "RA74",
  "<unk48>",
  "YY01",
  "RB01",    # 50
  "RB03"     # 51
]

def get_modelid_by_name(name):
  for i, m in enumerate(xqModelList):
    if m.lower() == name.lower():
      return i
  return -1


class XQImage():
  model = None
  type = 0
  version = None
  files = []  # list of files
  
  def __init__(self, model, type = 0):
    self.model = model.upper()
    self.type = type
    self.header = XQImgHdr()
    self.version = None
    self.files = []

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
    if len(self.version) & 3 != 0:
      self.version += b'\x00' * (4 - len(self.version) & 3)
    self.add_file(self.version, 'xiaoqiang_version')

  def add_file(self, data, name, mtd = None):
    file = types.SimpleNamespace()
    file.data = data
    file.header = XQImgFile()
    file.header.magic = int.from_bytes(b'\xBE\xBA', byteorder='little')
    file.header.rsvd0 = 0 
    file.header.addr = 0xFFFFFFFF
    file.header.size = len(data)
    file.header.mtd = 0xFFFF if mtd is None else mtd
    file.header.dummy = 0
    file.header.name = name.encode('latin_1')
    self.files.append(file)
  
  def build_image(self, sign = None):
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
    return buf
  
  def save_image(self, filename, sign = None):
    self.outfilename = filename
    buf = self.build_image(sign)
    with open(filename, 'wb') as file:
      file.write(buf)

  def build_sign(self):
    def i2b(value):
      return value.to_bytes(4, byteorder='little')
    payload = None
    if self.model == "R3G":
      poffset = 0x1058
      payload = i2b(0x416078) + i2b(0) + i2b(0) + i2b(0x402810)
    if self.model == "R3600":  # AX3600
      poffset = 0x1070
      payload = i2b(0x415290) + i2b(0) + i2b(0x402634) + i2b(0)
    if self.model == "RA69":   # AX6
      poffset = 0x1070
      payload = i2b(0x4152A8) + i2b(0) + i2b(0x402634) + i2b(0)
    if self.model == "RA70":   # AX9000
      poffset = 0x1078
      payload = i2b(0x4152D0) + i2b(0) + i2b(0x40265C) + i2b(0)
    if self.model == "RA72":   # AX6000
      poffset = 0x1078
      payload = i2b(0x4152E0) + i2b(0) + i2b(0x402630) + i2b(0)
    if not payload:
      raise OSError('HDR1 Payload is not defined for device "{}".'.format(self.model))
    # add header of sign section (16 bytes)
    sign = i2b(poffset) + (b'\x00' * 12)
    # add fake sign 
    size = poffset - len(payload)
    for i in range(0, size, 4):
      sign += (0xEAA00000 + i).to_bytes(4, byteorder='little')
    # add payload
    sign += payload
    return sign



