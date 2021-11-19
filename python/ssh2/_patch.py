#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform

fn_dir = './'
for filename in [fn for fn in os.listdir(fn_dir) if fn.split(".")[-1] in ['pyd']]:
  #print(filename)
  with open(filename, "rb") as file:
    buf = file.read()
  buf = buf.replace(b'libcrypto-1_1-x64.dll\0', b'libcrypto-1_1.dll\0\0\0\0\0')
  with open(filename, "wb") as file:
    file.write(buf)
  
print("==== Modules patched! ====")
