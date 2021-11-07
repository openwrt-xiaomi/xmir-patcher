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
  "R1800",
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
  header = XQImgHdr()
  version = None
  files = []  # list of files
  
  def __init__(self, model = None, type = 0):
    self.model = None
    self.type = 0
    self.header = XQImgHdr()
    self.version = None
    self.files = []
    if model is None:
      self.model = None
    else:
      if isinstance(model, int):
        self.model = model
      else:
        self.model = get_modelid_by_name(model)
    self.type = type

  def add_version(self, version, hardware = 0, channel = 'release'):
    self.version = None
    if version is None:
      return
    data = "config core 'version'\n"
    data += "\t" + "option ROM '{}'\n".format(version)
    if channel:
      data += "\t" + "option CHANNEL '{}'\n".format(channel.lower())
    if hardware is not None:
      if isinstance(hardware, int):
        if hardware == 0 and self.model:
          hardware = xqModelList[self.model]
        else:
          hardware = xqModelList[hardware]
      data += "\t" + "option HARDWARE '{}'\n".format(hardware.upper())
    self.version = data.encode('ascii')
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
    file.header.name = name.encode('ascii')
    self.files.append(file)
  
  def get_image(self, sign):
    buf = bytearray()
    self.header = XQImgHdr()
    self.header.magic = int.from_bytes(b'HDR1', byteorder='little')
    self.header.sign = 0
    self.header.crc32 = 0
    self.header.type = self.type
    self.header.model = self.model
    buf += bytes(self.header)
    for i, f in enumerate(self.files):
      self.header.files[i] = len(buf)
      buf += bytes(f.header)
      buf += f.data
    self.header.sign = len(buf)
    buf += sign
    for i in range(ctypes.sizeof(self.header)):
      buf[i] = bytes(self.header)[i]
    self.header.crc32 = 0xFFFFFFFF - binascii.crc32(buf[12:])  # JAMCRC
    for i in range(12):
      buf[i] = bytes(self.header)[i]
    return buf
  
  def save_image(self, sign, filename):
    self.outfilename = filename
    buf = self.get_image(sign)
    with open(filename, 'wb') as file:
      file.write(buf)
  
  
  
