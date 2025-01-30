#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import xmir_base
import gateway
from gateway import die
import read_info


gw = gateway.Gateway()

dev = read_info.DevInfo(verbose = 0, infolevel = 1)
dev.get_dmesg()
dev.get_part_table()
if not dev.partlist or len(dev.partlist) <= 1:
  die("Partition list is empty!")

fn_dir    = 'backups/'
fn_old    = fn_dir + 'full_dump.old'
fn_local  = fn_dir + 'full_dump.bin'
fn_remote = '/tmp/mtd_dump.bin'
a_part = None
pid = None
if len(sys.argv) > 1:
  for p, part in enumerate(dev.partlist):
    print('  %2d > addr: 0x%08X  size: 0x%08X  name: "%s"' % (p, part['addr'], part['size'], part['name']))
  print(" ")
  a_part = input("Enter partition name or mtd number: ")
  if a_part != 'a':
    try:
      i_part = int(a_part)
    except:
      i_part = None
    if i_part is not None:
      p = i_part
      if p < 0 or p >= len(dev.partlist):
        die('Partition "mtd{}" not found!'.format(a_part))
    else:
      p = dev.get_part_num(a_part)
      if p < 0:
        die('Partition "{}" not found!'.format(a_part))
    name = dev.partlist[p]['name']
    name = ''.join(e for e in name if e.isalnum())
    fn_old    = fn_dir + 'mtd{id}_{name}.old'.format(id=p, name=name)
    fn_local  = fn_dir + 'mtd{id}_{name}.bin'.format(id=p, name=name)
    pid = p

os.makedirs(fn_dir, exist_ok = True)

if pid is None and a_part != 'a':
  for p, part in enumerate(dev.partlist):
    if part['addr'] == 0 and part['size'] > 0x00800000:  # 8MiB
      pid = p
      name = dev.partlist[p]['name']  # "ALL"
      name = ''.join(e for e in name if e.isalnum())
      addr = dev.partlist[p]['addr']
      size = dev.partlist[p]['size']
      break

def backup_and_download(pid, filename, die_on_error = True):
    global fn_dir
    os.remove(filename) if os.path.exists(filename) else None
    with open(filename, 'wb') as file:
        pass
    part_size = dev.partlist[pid]["size"]
    fn_remote = f'/tmp/dump_mtd.bin'
    blk_size = 20*1024*1024
    dump_size = 0
    while dump_size < part_size:
        skip = dump_size // blk_size
        fn_local = fn_dir + f'dump_mtd{pid}_{skip}.bin'
        os.remove(fn_local) if os.path.exists(fn_local) else None
        cmd = f"rm -f {fn_remote} ; dd if=/dev/mtd{pid} of={fn_remote} bs={blk_size} count=1 skip={skip}"
        ret = gw.run_cmd(cmd, timeout = 25, die_on_error = False)
        if not ret:
            print(f'ERROR on execute command: "{cmd}"')
            if die_on_error:
                sys.exit(1)
            return False
        print(f'Download file "./{fn_local}"...')
        try:
            ret = gw.download(fn_remote, fn_local, verbose = 0)
        except Exception:
            print(f'ERROR: Remote file "{fn_remote}" not found!')
            if die_on_error:
                sys.exit(1)
            return False
        if not os.path.exists(fn_local):
            print(f'ERROR: File "{fn_local}" not found!')
            if die_on_error:
                sys.exit(1)
            return False
        chunk_size = os.path.getsize(fn_local)
        if chunk_size:
            with open(fn_local, 'rb') as file:
                data = file.read()
            with open(filename, 'ab+') as file:
                file.write(data)
        dump_size += chunk_size
        os.remove(fn_local)
        pass
    gw.run_cmd("rm -f " + fn_remote)
    print(f'File "{filename}" created!"')
    return True

if pid is not None:
  if os.path.exists(fn_dir): 
    if os.path.exists(fn_local): 
      if os.path.exists(fn_old):
        os.remove(fn_old)
      os.rename(fn_local, fn_old)
  if a_part is None:
    print("Full backup creating...")
  backup_and_download(pid, fn_local)
  print(" ")
  if a_part is None:
    print('Full backup saved to file "./{}"'.format(fn_local))
  else:
    print('Backup of "{}" saved to file "./{}"'.format(name, fn_local))
else:
  print("Full backup creating...")
  for p, part in enumerate(dev.partlist):
    if part['addr'] == 0 and part['size'] > 0x00800000:  # 8MiB
      continue  # skip "ALL" part
    name = dev.partlist[p]['name']
    name = ''.join(e for e in name if e.isalnum())
    addr = dev.partlist[p]['addr']
    size = dev.partlist[p]['size']
    fn_old    = fn_dir + 'mtd{id}_{name}.old'.format(id=p, name=name)
    fn_local  = fn_dir + 'mtd{id}_{name}.bin'.format(id=p, name=name)    
    if os.path.exists(fn_dir): 
      if os.path.exists(fn_local): 
        if os.path.exists(fn_old):
          os.remove(fn_old)
        os.rename(fn_local, fn_old)
    cmd = "dd if=/dev/mtd{id} of={o}".format(id=p, o=fn_remote)
    ret = gw.run_cmd(cmd, timeout=30, die_on_error = False)
    if not ret:
      print('ERROR on execute command: "{}"'.format(cmd))
    else:
      print('Download dump to file "./{}"...'.format(fn_local))
      try:
        gw.download(fn_remote, fn_local, verbose = 0)
      except Exception:
        print('Remote file "{}" not found!'.format(fn_remote))
        continue
    gw.run_cmd("rm -f " + fn_remote)
    if ret:
      print('Backup of "{}" saved to file "./{}"'.format(name, fn_local))
  print(" ")
  print("Completed!")


