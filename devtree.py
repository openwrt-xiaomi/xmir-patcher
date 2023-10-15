#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import ctypes

FDT_MAGIC = b"\xD0\x0D\xFE\xED"

class fdt_header(ctypes.BigEndianStructure):
  _fields_ = [("magic",             ctypes.c_uint),
              ("totalsize",         ctypes.c_uint),
              ("off_dt_struct",     ctypes.c_uint),
              ("off_dt_strings",    ctypes.c_uint),
              ("off_mem_rsvmap",    ctypes.c_uint),
              ("version",           ctypes.c_uint),
              ("last_comp_version", ctypes.c_uint),
              ("boot_cpuid_phys",   ctypes.c_uint),
              ("size_dt_strings",   ctypes.c_uint),
              ("size_dt_struct",    ctypes.c_uint)]

class fdt_reserve_entry(ctypes.BigEndianStructure):
  _fields_ = [("address", ctypes.c_uint64),
              ("size",    ctypes.c_uint64)]

class fdt_node_header(ctypes.BigEndianStructure):
  _fields_ = [("tag",     ctypes.c_uint),
              ("name",    ctypes.c_char * 128)]

class fdt_property(ctypes.BigEndianStructure):
  _fields_ = [("tag",     ctypes.c_uint),
              ("len",     ctypes.c_uint),
              ("nameoff", ctypes.c_uint),
              ("data",    ctypes.c_char)]

FDT_TAGSIZE = 4

FDT_BEGIN_NODE  = 0x1  # Start node: full name
FDT_END_NODE    = 0x2  # End node
FDT_PROP        = 0x3	 # Property: name off, size, content
FDT_NOP         = 0x4  # nop
FDT_END         = 0x9

FDT_V1_SIZE	 = 7 * 4
FDT_V2_SIZE	 = FDT_V1_SIZE + 4
FDT_V3_SIZE  = FDT_V2_SIZE + 4
FDT_V16_SIZE = FDT_V3_SIZE
FDT_V17_SIZE = FDT_V16_SIZE + 4


def get_dtb_totalsize(img, pos = 0, check = True):
  if img[pos:pos+4] != FDT_MAGIC:
    return -1
  hdrsize = ctypes.sizeof(fdt_header)
  dt = fdt_header.from_buffer_copy(img[pos:pos+hdrsize])
  if not check and dt.totalsize > hdrsize + 128:
    return dt.totalsize
  if dt.totalsize > hdrsize + 128:
    if dt.off_dt_struct > hdrsize and dt.off_dt_struct < dt.totalsize:
      if dt.off_dt_strings > hdrsize and dt.off_dt_strings < dt.totalsize:
        if dt.version == 17 and dt.last_comp_version == 16:
          if dt.boot_cpuid_phys == 0:
            if dt.size_dt_strings < dt.totalsize and dt.size_dt_struct < dt.totalsize:
              return dt.totalsize
  return -1

def find_dtb(img, pos=0, maxsize = 256000):
  while True:
    k = img.find(FDT_MAGIC + b"\x00", pos)
    if k < 0:
      break
    pos = k + 4
    totalsize = get_dtb_totalsize(img, k, check = True)
    if totalsize > 0 and totalsize <= maxsize:
      return k, totalsize
  return None, None

def get_dtb(img, pos=0):
  pos, size = find_dtb(img, pos)
  return img[pos:pos+size] if pos is not None else None

def get_dtb_part_info(dtb, part_name):
  k = dtb.find(b'fixed-partitions\x00')
  if k <= 0:
    return None
  while True:
    k = dtb.find(b"partition@", k)
    if k < 0:
      break
    k = dtb.find(b"\x00", k) + 1
    k = (k + 3) & 0xFFFFFFFC
    k += 12
    n = dtb.find(b"\x00", k)
    name = dtb[k:n]
    name_len = len(name)
    name = name.decode('latin_1')
    if name != part_name:
      continue
    k += name_len + 1
    k = (k + 3) & 0xFFFFFFFC
    k += 12
    addr = int.from_bytes(dtb[k:k+4], byteorder='big')
    size = int.from_bytes(dtb[k+4:k+8], byteorder='big')    
    return {'addr': addr, 'size': size, 'name': name}
  return None


