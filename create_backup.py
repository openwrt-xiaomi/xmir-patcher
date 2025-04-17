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


def backup_and_download(pid, filename, chunk_size = 0, die_on_error = True):
    global fn_dir
    os.remove(filename) if os.path.exists(filename) else None
    with open(filename, 'wb') as file:
        pass
    part_size = dev.partlist[pid]["size"]
    blk_size = 128*1024
    if not chunk_size:
        chunk_size = 20*1024*1024
    if chunk_size % blk_size != 0:
        die(f'Incorrect value of chunk_size = {chunk_size}')
    max_blocks = chunk_size // blk_size
    dump_size = 0
    while dump_size < part_size:
        if dump_size % blk_size != 0:
            die(f'Internal error on backup_and_download (dump_size = {dump_size})')
        skip = dump_size // blk_size
        fn_local = fn_dir + f'dump_mtd{pid}_{skip}.bin'
        os.remove(fn_local) if os.path.exists(fn_local) else None
        count = (part_size - dump_size) // blk_size
        if count == 0:
            count = 1
        if count > max_blocks:
            count = max_blocks
        cmd = f"rm -f {fn_remote} ; dd if=/dev/mtd{pid} of={fn_remote} bs={blk_size} skip={skip} count={count}"
        ret = gw.run_cmd(cmd, timeout = 25, die_on_error = False)
        if ret is None:
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
        if not os.path.exists(fn_local) or os.path.getsize(fn_local) == 0:
            print(f'ERROR: File "{fn_local}" not found!')
            if die_on_error:
                sys.exit(1)
            gw.run_cmd("rm -f " + fn_remote)
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
  backup_and_download(pid, fn_local)
  print(" ")
  print('Backup of "{}" saved to file "./{}"'.format(name, fn_local))
else:
  print("Full backup creating...")
  for p, part in enumerate(dev.partlist):
    if part['addr'] == 0 and part['size'] > 0x00800000:  # 8MiB
      name = "FULL_DUMP"
    else:
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
    ret = backup_and_download(p, fn_local, die_on_error = False)
    if ret:
      print('Backup of "{}" saved to file "./{}"'.format(name, fn_local))
  print(" ")
  print("Completed!")


