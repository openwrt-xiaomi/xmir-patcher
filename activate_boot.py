#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import xmir_base
import gateway
from gateway import die
import read_info
from envbuffer import EnvBuffer


def breed_boot_change(gw, dev, fw_num, fw_addr, fw_name):
  if dev is None:
    dev = read_info.DevInfo(verbose = 0, infolevel = 1)
  if fw_num is not None:
    pname = 'kernel%d' % fw_num
    p = dev.get_part_num(pname)
    if p < 0:
      die('Partition "{}" not found!)'.format(pname))
    fw_addr = dev.partlist[p]['addr']
  if not fw_addr:
    if len(fw_name) < 4:
      die('Incorrect boot partition name! (len: {})'.format(len(fw_name)))
    p = dev.get_part_num(fw_name)
    if p <= 0:
      die('Partition "{}" not found!)'.format(fw_name))
    fw_addr = dev.partlist[p]['addr']
  #dev.verbose = 2
  if dev.env.breed.data is None:
    dev.get_env_list()
  env = dev.env.breed
  if env.data is None or env.max_size is None:
    die("Can't found breed env address!")
  env.var['autoboot.command'] = "boot flash 0x%X" % fw_addr
  cmdline = 'uart_en=1'
  if 'linux.cmdline' in env.var:
    cmdline = env.var['linux.cmdline']    
    if 'uart_en=' in cmdline:
      cmdline = cmdline.replace('uart_en=0', 'uart_en=1')
    else:
      cmdline += ' uart_en=1'
  env.var['linux.cmdline'] = cmdline
  print("Breed ENV params for update:")
  for i, (k, v) in enumerate(env.var.items()):
    v = '' if (v is None) else ('=' + v)
    print("  " + k + v)
  bufsize = env.max_size
  buf = env.pack(bufsize)
  buf = b'ENV\x00' + buf[4:]
  #print("env =", buf[:128])
  data = env.data[0:env.offset] + buf + env.data[(env.offset + len(buf)):]
  fn_local  = 'tmp/env_breed.bin'
  fn_remote = '/tmp/env_breed.bin'
  with open(fn_local, "wb") as file:
    file.write(data)
  gw.upload(fn_local, fn_remote)
  pe = dev.get_part_num(env.addr, '#')
  if pe < 0:
    die('Partition for writing ENV {} not found!'.format("0x%08X" % env.addr))
  part_addr = dev.partlist[pe]['addr']
  part_name = dev.partlist[pe]['name']
  cmd = 'mtd write {bin} "{part}"'.format(bin=fn_remote, part=part_name)
  print("Send command: {}".format(cmd))
  gw.run_cmd(cmd)
  print('Breed ENV changed! Boot from {} activated.'.format("0x%08X" % fw_addr))
  gw.run_cmd("rm -f " + fn_remote)
  return fw_addr


def uboot_boot_change(gw, fw_num):
  if fw_num != 0 and fw_num != 1:
    die("Boot partition number not correct! Must be 0 or 1!")
  cmd = []
  cmd.append("nvram set flag_ota_reboot=0")
  cmd.append("nvram set flag_boot_success=1")
  cmd.append("nvram set flag_last_success={}".format(fw_num))
  cmd.append("nvram set flag_try_sys1_failed=0")
  cmd.append("nvram set flag_try_sys2_failed=0")
  cmd.append("nvram set flag_boot_rootfs={}".format(fw_num))
  cmd.append("nvram commit")
  out = gw.run_cmd(';'.join(cmd))
  return False if out is None else True


if __name__ == "__main__":
  gw = gateway.Gateway()
  dev = read_info.DevInfo(verbose = 0, infolevel = 1)
  dev.get_bootloader()
  if not dev.bl.img:
    die("Can't dump current bootloader!")

  for i, part in enumerate(dev.partlist):
    print('  %2d > addr: 0x%08X  size: 0x%08X  name: "%s"' % (i, part['addr'], part['size'], part['name']))

  if len(sys.argv) > 1:
    fw_name = sys.argv[1] 
  else:
    if dev.bl.type == 'breed':
      print("The device has an Breed bootloader installed.")
      print("It is possible to specify a specific kernel boot address (HEX-number).")
      print("It is also possible to specify the kernel number or the name of its partition.")
      fw_name = input("Enter kernel (number, address or name): ")
    else:
      fw_name = input("Enter kernel number (0 or 1): ")

  fw_name = fw_name.strip()
  if fw_name == "":
    die("Boot partition not specified!")

  fw_num = None
  fw_addr = None
  if len(fw_name) >= 6 and fw_name.lower().startswith('0x'):
    fw_addr = int(fw_name, 16)
  else:
    try:
      fw_num = int(fw_name)
      if fw_num != 0 and fw_num != 1:
        die("Boot partition number not correct! Must be 0 or 1!")
    except Exception:
      pass

  #if dev.bl.type == 'pandora':
  #  die('Pandora bootloader not supported!')

  if dev.bl.type == 'breed':
    fw_addr = breed_boot_change(gw, dev, fw_num, fw_addr, fw_name)
    if fw_name != '0' and fw_name != '1':
      sys.exit(0)
    fw_addr = None  

  fw_num = None
  try:
    fw_num = int(fw_name)
  except Exception:
    pass

  if fw_addr:
    die('Required Breed bootloader for set custom boot address!')

  if fw_num is None:
    die("Boot partition not specified!")

  print("Run scripts for change NVRAM params...")
  uboot_boot_change(gw, fw_num)
  print('Ready! Boot from partition "kernel{}" activated.'.format(fw_num))


'''
/*** Algorithm from stock uboot: ***/

  #define OK 0

  if ( flag_try_sys1_failed > 1 || flag_try_sys2_failed > 1 || flag_ota_reboot > 1 || flag_last_success > 1 )
    goto boot_rootfs0;

  if ( flag_try_sys1_failed == 1 && flag_try_sys2_failed == 1 )
  {
    if ( verifying_kernel0() == OK )
      goto boot_rootfs0; 

    if ( verifying_kernel1() == OK )
      goto boot_rootfs1;
  }  

  if ( flag_ota_reboot == 1 )
  {
    flag_last_success = 1 - flag_last_success;
  }
  else
  {
    if ( flag_last_success == 0 )
      flag_try_sys2_failed = flag_try_sys1_failed;

    if ( flag_try_sys2_failed == 1 )
      flag_last_success = 1 - flag_last_success;
  }
  
  if ( flag_last_success == 0 )
    goto boot_rootfs0;
  else
    goto boot_rootfs1;

boot_rootfs1:
  img_addr = 0x600000    // kernel1
  flag_boot_rootfs = 1;
  goto boot;

boot_rootfs0:
  img_addr = 0x200000    // kernel0
  flag_boot_rootfs = 0;
  goto boot;

boot:
  setenv("flag_boot_rootfs", flag_boot_rootfs);
  factory_mode = 0;
  crash_log_magic = 0;
  ranand_read(&crash_log_magic, 0x140000, 4);
  if ( crash_log_magic == 0x5AA5 )
  {
    factory_mode = 1;
    printf("System is in factory mode.\n");
    setenv("uart_en", "1");
    setenv("boot_wait", "on");
  }
  saveenv();
  ranand_read(img_header, img_addr, 64);
  img_header_magic = ntohl(*(uint32_t *)img_header)
  if ( img_header_magic != 0x27051956 )
  {
    printf("Bad Magic Number,%08X, try to reboot\n", img_header_magic);
    goto bad_data;
  }
  if ( getenv("verify") != 'n' ) {
    if ( verify_image(img_addr) != OK )
      printf("Bad Data CRC\n");
      goto bad_data;
    }
  }

  do_bootm_linux(...)

bad_data:
  if ( flag_boot_rootfs == 0 )
    setenv("flag_try_sys1_failed", "1");
  else
    setenv("flag_try_sys2_failed", "1");

  setenv("flag_ota_reboot", "0");
  saveenv();
  if ( factory_mode )
  {
    printf("System is in factory mode. U-Boot BOOT ERROR! \n");
    nullsub_4();
    while ( 1 )     // HARD CPU RESTART
      ;
  }
  return CRITICAL_ERROR

'''


