#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import types
import binascii


class EnvBuffer():
  addr = None
  data = None      # partition dump
  offset = None    # ENV offset in partition
  len = 0
  max_size = None
  var = {}         # key=value
  encoding = 'latin_1'
  crc_prefix = True
  delim = '\x00'
  
  def __init__(self, data = None, delim = '\x00', crc_prefix = True, encoding = 'latin_1'):    
    self.encoding = encoding
    self.delim = delim
    self.crc_prefix = crc_prefix
    self.var = {}
    if data is not None:
      prefix_len = 4 if crc_prefix else 0
      if isinstance(data, str):
        self.var = self.parse_env(data, delim)
      else:
        end = data.find((delim + delim).encode(encoding), prefix_len)
        if (end > prefix_len):        
          data = data[prefix_len:end+1]
          self.var = self.parse_env_b(data, delim, encoding)
  
  def parse_env_b(self, data, delim, encoding = 'latin_1'):
    dict = {}
    self.len = len(data)
    data = data.split(delim.encode('latin_1'))
    for i, s in enumerate(data): 
      s = s.strip()
      if len(s) < 1:
        continue
      x = s.find(b'=')
      if x == 0:
        continue
      if x >= 1:
        key = s[0:x].decode(encoding)
        val = s[x+1:].decode(encoding)
        dict[key.strip()] = val.strip()
      else:
        key = s.decode(encoding)
        dict[key.strip()] = None      
    return dict  

  def parse_env(self, data, delim):
    dict = {}
    self.len = len(data)
    data = data.split(delim)
    for i, s in enumerate(data): 
      s = s.strip()
      if len(s) < 1:
        continue
      x = s.find('=')
      if x == 0:
        continue
      if x >= 1:
        key = (s[0:x]).strip()
        if key:
          dict[key] = (s[x+1:]).strip()
      else:
        dict[s.strip()] = None
    return dict  

  def set_env(self, key, value):    
    self.var[key] = value
    
  def pack(self, bufsize, crc_prefix = None, encoding = None):
    crc_prefix = crc_prefix if crc_prefix is not None else self.crc_prefix
    encoding = encoding if encoding is not None else self.encoding
    buf = b''
    if self.var:
      for i, (k, v) in enumerate(self.var.items()):
        v = '' if (v is None) else ('=' + v)
        buf += (k + v + '\x00').encode(encoding)
    if len(buf) + 64 > bufsize:
      raise OSError("Buffer overflow")
    prefix_len = 4 if crc_prefix else 0
    buf += b'\x00' * (bufsize - len(buf) - prefix_len)
    crc = binascii.crc32(buf)
    buf = (crc).to_bytes(4, byteorder='little') + buf
    return buf









