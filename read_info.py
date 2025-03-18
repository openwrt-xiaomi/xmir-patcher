#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import types
import binascii
import random
import tarfile
import io
import requests

import xmir_base
import gateway
from gateway import die
from envbuffer import EnvBuffer


class RootFS():
  num = None       # 0 / 1
  mtd_num = None   # 10 / 11
  mtd_dev = None   # "/dev/mtd10"
  partition = None # "rootfs0" / "rootfs1" / "rootfs_1"

class Bootloader():
  type = None      # 'uboot' / 'breed' / 'pandora'
  img = None
  img_size = None
  addr = None
  spi_rom = False

class BaseInfo():
  linux_stamp = None
  linux_ver = None
  linux_arch = None
  cpu_arch = None
  cpu_name = None
  spi_rom = False
  
class Version():
  openwrt = None   # '12.09.1'
  fw = None
  channel = None   # 'release' / 'stable'
  buildtime = None
  hardware = None  # 'R3G'
  uboot1 = None    # '4.2.S.1'
  uboot2 = None

class DevInfo():
  gw = None        # Gateway()
  verbose = 0
  syslog = []      # list of FileObject()
  dmesg = None     # text
  info = BaseInfo()
  partlist = []    # list of {addr, size, name}
  allpartnum = -1  # "ALL" partition number
  kcmdline_s = ""  # original kernel command line
  kcmdline = {}    # key=value
  nvram = {}       # key=value
  rootfs = RootFS()
  board_name = None
  model = None
  ver = Version()
  bl = Bootloader()  # first bootloader
  bl_list = []       # list of Bootloaders
  env_list = []      # list of EnvBuffer
  env = types.SimpleNamespace()
  env.fw = EnvBuffer()
  env.breed = EnvBuffer() 
  env.bdata = EnvBuffer()

  def __init__(self, gw = None, verbose = 0, infolevel = 1):
    self.gw = gateway.Gateway() if gw is None else gw
    self.verbose = verbose
    os.makedirs('outdir', exist_ok = True)
    os.makedirs('tmp', exist_ok = True)
    if infolevel > 0:
      self.update(infolevel)

  def update(self, infolevel):
    if infolevel >= 1:
      self.get_dmesg()
      self.get_part_table()
      if not self.partlist or len(self.partlist) <= 1:
        die("Partition list is empty! (solution: disable all WiFi modules and reboot device)")
      self.get_kernel_cmdline()
      self.get_rootfs()
      self.get_baseinfo()
      if not self.info.cpu_arch:
        die("Can't detect CPU arch! Try to reboot device.")
    if infolevel >= 2:
      self.get_ver()
    if infolevel >= 3:
      self.get_nvram()
    if infolevel >= 4:
      self.get_bootloader()
    if infolevel >= 5:
      self.get_env_list()

  def run_command(self, cmd, fn = None, encoding = "latin_1", binary = False, verbose = 1):
    if not fn:
      fn = hex(random.getrandbits(64)) + '.txt'
      fn = fn[1:]
    fn_local  = f'outdir/{fn}'
    fn_remote = f'/tmp/{fn}'
    if os.path.exists(fn_local):
      os.remove(fn_local)
    if '>' not in cmd:
      cmd += " > " + fn_remote
    try:
      self.gw.run_cmd(cmd)
      self.gw.download(fn_remote, fn_local, verbose = verbose)
      self.gw.run_cmd("rm -f " + fn_remote)
    except Exception:
      return None
    if not os.path.exists(fn_local):
      return None
    if os.path.getsize(fn_local) <= 0:
      return None
    openmode = 'rb' if binary else 'r'
    with open(fn_local, openmode, encoding = encoding) as file:
      output = file.read()
    return output    
  
  def get_dmesg(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.dmesg = self.run_command('dmesg', 'dmesg.log')
    if self.dmesg is None:
      print(f'ERROR on downloading "/tmp/dmesg.log"')
    return self.dmesg

  def get_part_addr_dmesg(self, partlist):
    if not self.dmesg:
      return -1
    x = self.dmesg.find(" MTD partitions on ")
    if x <= 0:
      return -2
    parttbl = re.findall(r'0x0000(.*?)-0x0000(.*?) : "(.*?)"', self.dmesg)
    if len(parttbl) <= 0:
      return -3
    k = 0
    for i, part in enumerate(parttbl):
      addr = int(part[0], 16)
      size = int(part[1], 16) - addr
      name = part[2]
      for p, data in enumerate(partlist):
        if data['name'] == name:
          #print(f"{name:12S}: {addr:08X} {size:08X}")
          if size != data['size']:
            x = self.dmesg.find(f'mtd: partition "{name}" extends beyond the end of device "')
            if x <= 0:
              raise ValueError(f"Incorrect size into partition table ({name})")
          if addr != data['addr'] and data['addr'] >= 0:
            raise ValueError(f"Incorrect addr for partition ({name})")
          if data['addr'] < 0:
            data['addr'] = addr
            k += 1
    return k

  def get_part_table(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.partlist = [ ]
    self.allpartnum = -1
    mtd_list = self.run_command('cat /proc/mtd', 'mtd_list.txt')
    if not mtd_list or len(mtd_list) <= 1:
      return [ ]
    mtdtbl = re.findall(r'mtd([0-9]+): ([0-9a-fA-F]+) ([0-9a-fA-F]+) "(.*?)"', mtd_list)
    if len(mtdtbl) <= 1:
      return [ ]
    mtd_max_num = max( [ int(mtd[0]) for i, mtd in enumerate(mtdtbl) ] )
    partlist = [ { 'addr': -1, 'size': -1, 'name': None } for i in range(mtd_max_num + 1) ]
    mtd_info = self.get_part_info(mtd_max_num, verbose)
    for i, mtd in enumerate(mtdtbl):
      mtdid = int(mtd[0])
      addr = -1
      size = int(mtd[1], 16)
      name = mtd[3]
      if mtd_info and mtdid < len(mtd_info):
        if mtd_info[mtdid]["addr"] is not None:
          addr = mtd_info[mtdid]["addr"]
      partlist[mtdid]['addr'] = addr
      partlist[mtdid]['size'] = size
      partlist[mtdid]['name'] = name
      pass
    self.get_part_addr_dmesg(partlist)
    if partlist[0]['addr'] < 0:
      if partlist[0]['name']:
        if partlist[0]['size'] > 0x00800000:  # 8MiB
          partlist[0]['addr'] = 0  # detect "ALL" part
    if partlist[0]['addr'] == 0:
      if partlist[0]['size'] > 0x00800000:  # 8MiB:
        self.allpartnum = 0  # detect "ALL" part
    fdt_info = self.get_part_from_fdt(partlist, verbose)
    if self.verbose:
      print("MTD partitions:")
    err_addr = -1
    for i, part in enumerate(partlist):
      size = part['size']
      name = part['name']
      if part['addr'] < 0:
        if name in fdt_info:
          if size == fdt_info[name]['size']:
            part['addr'] = fdt_info[name]['addr']
      if part['addr'] < 0:
        if name == "m25p80":
          part['addr'] = 0xFFFFFFFF
        else:
          if self.dmesg and re.search(f'mounted UBI device ., volume ., name "{name}"', self.dmesg):
            part['addr'] = 0xFFFFFFFF
      if part['addr'] < 0 and fdt_info:
        part['addr'] = 0xFFFFFFFF
      addr = part['addr']
      if mtd_info and i < len(mtd_info):
        if mtd_info[i]["ro"] is not None:
          part['ro'] = False if mtd_info[i]["ro"] == 0 else True
      if verbose:
        xaddr = ("0x%08X" % addr) if addr >= 0 else "??????????"
        ro = '?'
        if 'ro' in part:
          ro = '0' if part['ro'] == False else '1'
        print('  %2d > addr: %s  size: 0x%08X  ro:%s  name: "%s"' % (i, xaddr, size, ro, name))
      if addr < 0:
        err_addr = mtdid
    if verbose:
      print(" ")
    if err_addr >= 0:
      return [ ]
    self.partlist = partlist
    return self.partlist

  def get_part_info(self, mtd_max_num, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    fn = 'mtd_info.txt'
    mtd_dev = '/sys/class/mtd/mtd$i'
    dn = '2>/dev/null'
    trim = r"tr -d '\n'"
    a2f = f"tee -ia /tmp/{fn}"  # append to file
    delim = f"echo -n '|' >> /tmp/{fn}"
    cmd  = f'rm -f /tmp/{fn} ;'
    cmd += f'for i in $(seq 0 {mtd_max_num}) ; do'
    cmd += f'  echo "" >> /tmp/{fn} ;'
    cmd += f'  echo -n $i= >> /tmp/{fn} ;'
    cmd += f"  cat {mtd_dev}/offset {dn} | {trim} | {a2f} ; {delim} ;"
    cmd += f"  cat {mtd_dev}/type   {dn} | {trim} | {a2f} ; {delim} ;"
    cmd += f"  cat {mtd_dev}/flags  {dn} | {trim} | {a2f} ; {delim} ;"
    cmd += f"  cat {mtd_dev}/mtdblock$i/ro  {dn} | {trim} | {a2f} ; {delim} ;"
    cmd += f"  cat {mtd_dev}/dev    {dn} | {trim} | {a2f} ; {delim} ;"
    cmd += f"  readlink -f {mtd_dev}/device {dn} | {trim} | {a2f} ; {delim} ;"
    cmd += f"  mtd -l 1 dump /dev/mtd$i {dn} | wc -c | {trim} | {a2f} ; {delim} ;"
    cmd += f'done'
    out_text = self.run_command(cmd, fn)
    if not out_text:
      return [ ]
    info = [ { "addr": None, "ro": None } for i in range(mtd_max_num + 1) ]
    for line in out_text.split('\n'):
      line = line.strip()
      if '=' in line:
        data = line.split('=')
        mtd_num = int(data[0])
        mtd_info = data[1].split('|')
        info[mtd_num]["addr"]   = int(mtd_info[0], 0) if len(mtd_info[0]) > 0 else None
        info[mtd_num]["type"]   = mtd_info[1].strip()
        info[mtd_num]["flags"]  = int(mtd_info[2], 0) if len(mtd_info[2]) > 0 else None
        info[mtd_num]["ro"]     = 0 if mtd_info[6] == '1' else 1
        info[mtd_num]["dev"]    = mtd_info[4].strip()
        info[mtd_num]["device"] = mtd_info[5].strip()
    return info    

  def get_part_from_fdt(self, partlist, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    fn = 'mtd_fdt.txt'
    fdtpath = '/sys/firmware/devicetree/base/**/'
    execgrep = '-exec grep -l "^fixed-partitions" {} +'
    hexfmt = "'1/1 \"%02x\"'"
    trim = r"tr -d '\n'"
    cmd  = f'fn=/tmp/{fn};'
    cmd += f'rm -f $fn;'
    cmd += f'dlist=$( find {fdtpath} -type f -name compatible {execgrep} );'
    cmd += f'[ -z "$dlist" ] && dlist=$( find {fdtpath} -type f -name nand-bus-width );'
    cmd += f'for trgfile in $dlist ; do'
    cmd += f'  bdir=$( dirname $trgfile );'
    cmd += f'  echo "" >>$fn;'
    cmd += f'  echo "PARTLIST:$bdir" >>$fn;'
    cmd += f'  plist=$( find $bdir/**/ -mindepth 1 -maxdepth 1 -type f -name label );'
    cmd += f'  for label in $plist ; do'
    cmd += f'    pdir=$( dirname $label );'
    cmd += f'    preg=$( cat $pdir/reg | hexdump -v -n8 -e {hexfmt} );'  # bigendian
    cmd +=  '    echo "0x${preg:0:8}|0x${preg:8:8}|$(cat $label | tr -d ''\\n'')" >>$fn;'
    cmd += f'  done;'
    cmd += f'done'
    fdt_text = self.run_command(cmd, fn)
    if not fdt_text:
      return { }
    fdt_dev = [ ]
    mtd_list = None
    for line in fdt_text.split('\n'):
      line = line.strip()
      if line.startswith('PARTLIST:'):
        if mtd_list:
          fdt_dev.append(mtd_list)
        mtd_list = { }
      if line.startswith('0x'):
        data = line.split('|')
        name = data[2].strip()
        if name:
          mtd_list[name] = { 'addr': int(data[0], 0), 'size': int(data[1], 0) }
    if mtd_list:
      fdt_dev.append(mtd_list)
    if not fdt_dev:
      return { }
    if len(fdt_dev) == 1:
      return fdt_dev[0]
    scores = [ 0 ] * len(fdt_dev)
    for i, mtd_list in enumerate(fdt_dev):
      for _, (name, mtd) in enumerate(mtd_list.items()):
        for part in partlist:
          if part['name'] == name and part['size'] == mtd['size']:
            if part['addr'] == mtd['addr']:
              scores[i] += 1
            elif part['addr'] < 0:
              pass #nothing
            else:
              scores[i] -= 1
    max_scores = max(scores)
    if max_scores <= 0:
      return { }
    devnum = scores.index(max_scores)
    return fdt_dev[devnum]

  def get_part_num(self, name_or_addr, comptype = None):
    if not self.partlist:
      return -2
    if isinstance(name_or_addr, int):
      addr = name_or_addr
      for i, part in enumerate(self.partlist):
        if self.allpartnum >= 0 and i == self.allpartnum:
          continue  # skip "ALL" part
        if comptype and comptype == '#':  # range
          if addr >= part['addr'] and addr < part['addr'] + part['size']:
            return i
        else:
          if addr == part['addr']:
            return i
    if isinstance(name_or_addr, str):
      name = name_or_addr.lower()
      for i, part in enumerate(self.partlist):
        partname = part['name'].lower()
        if len(partname) > 2 and partname[1:2] == ':':
          partname = partname[2:]
        if comptype and comptype[0] == 'e':  # endswith
          if partname.endswith(name):
            return i
        elif partname == name:
          return i
    return -1

  def get_part_list(self, name_or_addr_list, comptype = None):
    if not self.partlist:
      return None
    lst = []
    for i, val in enumerate(name_or_addr_list):
      p = self.get_part_num(val, comptype)
      if p >= 0:
        lst.append(p)
    return lst

  def get_part(self, name_or_addr, comptype = None):
    i = self.get_part_num(name_or_addr, comptype)
    if i < 0:
      return None
    return self.partlist[i]  

  def get_part_by_addr(self, addr):
    return self.get_part(addr, None)

  def get_rootfs(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.rootfs = RootFS()
    if not self.kcmdline_s and not self.dmesg:
      return self.rootfs
    kcmdline = f'Kernel command line: {self.kcmdline_s} \n'
    if self.dmesg:
      # flag_boot_rootfs=0 mounting /dev/mtd10 
      x = re.search(r'flag_boot_rootfs=([0-9]) mounting (\S+)', self.dmesg)
      if x:
        self.rootfs.num = int(x.group(1))
        self.rootfs.mtd_dev = x.group(2)
      # UBI: attached mtd10 (name "rootfs0", size 32 MiB) to ubi0 
      x = re.search(r'attached mtd([0-9]+) \(name "(.*?)", size', self.dmesg)
      if x and x.group(2).lower().startswith('rootfs'):
        self.rootfs.mtd_num = int(x.group(1))
        self.rootfs.partition = x.group(2).strip()
      # mtd: device 11 (rootfs) set to be root filesystem
      x = re.search(r'mtd: device ([0-9]+) \(rootfs\) set to be root filesystem', self.dmesg)
      if x:
        self.rootfs.mtd_num = int(x.group(1))
    if self.rootfs.num is None:
      k = re.search(r'Kernel command line:(.*?) ubi\.mtd=(\S+)', kcmdline)   # ([^\s]+)
      if k:
        self.rootfs.partition = k.group(2)
    if self.rootfs.num is None:
      k = re.search(r'Kernel command line:(.*?) firmware=([0-9])', kcmdline)
      if k:
        self.rootfs.num = int(k.group(2))
    if self.rootfs.num is None and self.rootfs.mtd_num is None:
      x = re.search(r'Kernel command line:(.*?) root=(\S+)', kcmdline)
      if x and x.group(2).startswith('/dev/mtdblock'):
        self.rootfs.mtd_dev = x.group(2) 
        self.rootfs.mtd_num = int(self.rootfs.mtd_dev.replace('/dev/mtdblock', ''))
    if self.rootfs.num is None and self.rootfs.partition:
      pname = self.rootfs.partition.lower()
      if pname.startswith('rootfs') or pname.startswith('firmware') or pname.startswith('ubi'):
        self.rootfs.num = 0
        if pname.endswith('1'):
          self.rootfs.num = 1
    if verbose:
      print('RootFS info:')
      print('  num = {}'.format(self.rootfs.num))
      print('  mtd_num = {}'.format(self.rootfs.mtd_num))
      print('  mtd_dev = "{}"'.format(self.rootfs.mtd_dev))
      print('  partition = "{}"'.format(self.rootfs.partition))
      print(" ")
    return self.rootfs
    
  def get_baseinfo(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.info = BaseInfo()
    ret = self.info
    if verbose:
      print('Base info:')
    if self.dmesg:
      # Linux version 3.10.14 (jenkins@cefa8cf504dc) (gcc version 4.8.5 (crosstool-NG crosstool-ng-1.22.0) ) 
      x = re.search(r'Linux version (.*?) ', self.dmesg)
      if x:
        ret.linux_ver = x.group(1).strip()
    kernel_version = self.get_kernel_version(verbose = verbose)
    if not ret.linux_ver:
      if kernel_version:
        ret.linux_ver = kernel_version
    ret.linux_stamp = self.kernel_ver_stamp
    ret.linux_arch = self.kernel_arch
    if verbose:
      print('  Linux version: {}'.format(ret.linux_ver))
    fn_local  = 'outdir/openwrt_release.txt'
    fn_remote = '/etc/openwrt_release'
    if os.path.exists(fn_local):
      os.remove(fn_local)
    try:
      self.gw.download(fn_remote, fn_local, verbose=0)
    except Exception:
      if verbose:
        print('  File "{}" cannot download!'.format(fn_remote))
      return ret
    if not os.path.exists(fn_local):
      return ret
    if os.path.getsize(fn_local) <= 1:
      return ret
    with open(fn_local, "r", encoding="latin_1") as file:
      txt = file.read()
    x = re.search("DISTRIB_TARGET=['\"](.*?)['\"]", txt)
    if not x:
      return ret
    if verbose:
      print("  DISTRIB_TARGET =", x.group(1))
    target = x.group(1).strip().lower()
    board = target.split(r'/')[0]
    subtarget = target.split(r'/')[1]
    cpu_arch = None
    cpu_name = ''
    if board == 'ramips':
      cpu_arch = 'mips'
      cpu_name = subtarget
    if board == 'mediatek':
      cpu_arch = 'arm64'
      cpu_name = subtarget[:6]
    if board.startswith('ar71'):  # Atheros
      cpu_arch = 'mips'
      cpu_name = board[:6]
    if board == 'ipq' and subtarget.startswith('ipq'):
      cpu_name = subtarget[:7]
    elif board.startswith('ipq') and len(board) >= 7:
      cpu_name = board[:7]
    if cpu_name.startswith('ipq401'):
      cpu_arch = 'armv7'
    if cpu_name.startswith('ipq806'):
      cpu_arch = 'armv7'
    if cpu_name.startswith('ipq807'):
      cpu_arch = 'arm64'
    if cpu_name.startswith('ipq50'):
      cpu_arch = 'arm64'
    if cpu_name.startswith('ipq60'):
      cpu_arch = 'arm64'
    if cpu_name.startswith('ipq95'):
      cpu_arch = 'arm64'
    x = re.search("DISTRIB_ARCH=['\"](.*?)['\"]", txt)
    if x:
      if verbose:
        print("  DISTRIB_ARCH =", x.group(1))
      arch = x.group(1)
      if arch.startswith("mips_") or arch.startswith("mipsel_") or arch.startswith("ramips_"):
        cpu_arch = 'mips'
      if arch.startswith("arm_"):
        cpu_arch = 'armv7'
      if arch.startswith("aarch64_"):
        cpu_arch = 'arm64'      
    ret.cpu_arch = cpu_arch if cpu_arch else None
    ret.cpu_name = cpu_name if cpu_name else None
    if verbose:
      print('  CPU arch: {}'.format(ret.cpu_arch))
      print('  CPU name: {}'.format(ret.cpu_name))
    if board == 'ramips' and self.dmesg:
      # spi-mt7621 1e000b00.spi: sys_freq: 50000000  
      x = re.search(r'spi-mt(.*?) (.*?).spi: sys_freq: ', self.dmesg)
      if x:
        ret.spi_rom = True
        if verbose:
          print('  SPI rom: {}'.format(ret.spi_rom))
    if verbose:
      print(" ")
    return ret

  def get_kernel_cmdline(self, verbose = None, retdict = True):
    verbose = verbose if verbose is not None else self.verbose
    self.kcmdline_s = ""
    self.kcmdline = {} if retdict else None
    fn_local  = 'outdir/kcmdline.log'
    fn_remote = '/tmp/kcmdline.log'
    try:
      self.gw.run_cmd("cat /proc/cmdline > " + fn_remote)
      self.gw.download(fn_remote, fn_local)
      self.gw.run_cmd("rm -f " + fn_remote)
    except Exception:
      return self.kcmdline
    if not os.path.exists(fn_local):
      return self.kcmdline
    if os.path.getsize(fn_local) <= 1:
      return self.kcmdline
    with open(fn_local, "rb") as file:
      data = file.read()
    data = data.replace(b"\n", b' ')
    data = data.replace(b"\x00", b' ')
    data = data.decode('latin_1')
    data = data.strip()
    self.kcmdline_s = data
    if verbose:
      print("Kernel command line:")
      print(" ", data)
    if not retdict:
      return data
    env = EnvBuffer(data, ' ', crc_prefix = False, encoding = 'latin_1')
    self.kcmdline = env.var
    #self.kcmdline = type("Names", [object], self.kcmdline)
    return self.kcmdline

  def get_kernel_version(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.kernel_ver_stamp = None
    self.kernel_version = None
    self.kernel_buildver = None
    self.kernel_arch = None
    fn = 'kver.txt'
    cmd  = f'uname -a  > /tmp/{fn} ; '   # Linux XiaoQiang 5.4.213 #0 SMP PREEMPT Tue Feb 18 11:11:56 2025 armv7l GNU/Linux
    cmd += f'uname -r >> /tmp/{fn} ; '   # 5.4.213
    cmd += f'uname -v >> /tmp/{fn} ; '   # #0 SMP PREEMPT Tue Feb 18 11:11:56 2025
    cmd += f'uname -m >> /tmp/{fn} ; '   # armv7l
    cmd += f'uname -p >> /tmp/{fn} ; '   # <Processor type>
    out_text = self.run_command(cmd, fn)
    if not out_text:
        return None
    #if 'Linux' not in out_text:
    #    return None
    out_lines = out_text.split('\n')
    if len(out_lines) < 4:
        return None
    self.kernel_ver_stamp = out_lines[0].strip()
    self.kernel_version = out_lines[1].strip()
    self.kernel_buildver = out_lines[2].strip()
    self.kernel_arch = out_lines[3].strip()
    if verbose:
        print(f"  Kernel version: {self.kernel_ver_stamp}")
    return self.kernel_version

  def get_nvram(self, verbose = None, retdict = True):
    verbose = verbose if verbose is not None else self.verbose
    self.nvram = {} if retdict else None
    fn_local  = 'outdir/nvram.txt'
    fn_remote = '/tmp/nvram.txt'
    try:
      self.gw.run_cmd("nvram show > " + fn_remote)
      self.gw.download(fn_remote, fn_local)
      self.gw.run_cmd("rm -f " + fn_remote)
    except Exception:
      return self.nvram
    if not os.path.exists(fn_local):
      return self.nvram
    if os.path.getsize(fn_local) <= 1:
      return self.nvram
    with open(fn_local, "r", encoding="latin_1") as file:
      data = file.read()
    if not retdict:
      return data
    if verbose:
      print("NVRam params:")
    env = EnvBuffer(data, '\n', crc_prefix = False, encoding = 'latin_1')
    self.nvram = env.var
    if verbose and self.nvram:
      for i, (k, v) in enumerate(self.nvram.items()): 
        if verbose == 1 and not k.startswith('flag_') and k != 'ipaddr' and k != 'serverip':
          continue
        print("  {key}{value}".format(key=k, value=('=' + v if v is not None else '')))
    if verbose:
      print(" ")
    #self.nvram = type("Names", [object], self.nvram)
    return self.nvram
    
  def get_board_name(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.board_name = None
    fn_local  = 'outdir/board_name.txt'
    fn_remote = '/tmp/sysinfo/board_name'
    self.gw.download(fn_remote, fn_local)
    if os.path.getsize(fn_local) <= 0:
      return None
    with open(fn_local, "r") as file:
      self.board_name = file.read()
    self.board_name = self.board_name.strip()
    if verbose:
      print("Board name: {}".format(self.board_name))
      print("")
    return self.board_name

  def get_model(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.model = None
    fn_local  = 'outdir/model.txt'
    fn_remote = '/tmp/sysinfo/model'
    self.gw.download(fn_remote, fn_local)
    if os.path.getsize(fn_local) <= 0:
      return None
    with open(fn_local, "r") as file:
      self.model = file.read()
    self.model = self.model.strip()
    if verbose:
      print("Model: {}".format(self.model))
      print("")
    return self.model

  def get_ver(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.ver = Version()
    if verbose:
      print("Version info:")
    fn_local  = 'outdir/uboot_version.txt'
    fn_remote = '/etc/uboot_version'
    try:
      self.gw.download(fn_remote, fn_local, verbose = 0)
      with open(fn_local, "r") as file:
        self.ver.uboot1 = file.read().strip()
    except Exception:
      pass
    if verbose:
      print("  UBoot: {}".format(self.ver.uboot1))
    fn_local  = 'outdir/openwrt_version.txt'
    fn_remote = '/etc/openwrt_version'
    try:
      self.gw.download(fn_remote, fn_local, verbose = 0)
      with open(fn_local, "r") as file:
        self.ver.openwrt = file.read().strip()
    except Exception:
      pass
    if verbose:
      print("  OpenWrt: {}".format(self.ver.openwrt))
    fn_local  = 'outdir/fw_ver.txt'
    fn_remote = '/etc/xiaoqiang_version'
    try:
      self.gw.download(fn_remote, fn_local, verbose = 0)
    except Exception:
      fn_remote = None
    if not fn_remote:
      fn_remote = '/usr/share/xiaoqiang/xiaoqiang_version'
      try:
        self.gw.download(fn_remote, fn_local, verbose = 0)
      except Exception:
        fn_remote = None
    if fn_remote and os.path.getsize(fn_local) > 0:
      with open(fn_local, "r") as file:
        s = file.read()
        x = re.search(r"option ROM '(.*?)'", s)
        self.ver.fw = x.group(1) if x else None
        x = re.search(r"option CHANNEL '(.*?)'", s)
        self.ver.channel = x.group(1) if x else None
        x = re.search(r"option HARDWARE '(.*?)'", s)
        self.ver.hardware = x.group(1) if x else None
        x = re.search(r"option UBOOT '(.*?)'", s)
        self.ver.uboot2 = x.group(1) if x else None
        x = re.search(r"option BUILDTIME '(.*?)'", s)
        self.ver.buildtime = x.group(1) if x else None
    if verbose:
      print("  Firmware: {}".format(self.ver.fw))
      print("  Channel: {}".format(self.ver.channel))
      print("  BuildTime: {}".format(self.ver.buildtime))
      print("  Hardware: {}".format(self.ver.hardware))
      print("  UBoot(2): {}".format(self.ver.uboot2))
      print("")
    return self.ver

  def get_md5_for_mtd_data(self, partname, offset = 0, size = None):
    if not self.partlist:
        return -10
    mtd_num = self.get_part_num(partname)
    if mtd_num < 0:
        return -9 
    mtd_part = self.partlist[mtd_num]
    bs = 4096
    if not size:
        size = mtd_part['size']
    if size > mtd_part['size']:
        return -8
    if size % bs != 0:
        return -7
    if offset % bs != 0:
        return -6
    skip = f'skip={offset // bs}' if offset else ''
    num = str(random.randint(10000, 1000000))
    md5_local_fn = f"tmp/mtd{mtd_num}_{offset}_{size}_{num}.md5"
    md5_remote_fn = f"/tmp/mtd{mtd_num}_{offset}_{size}_{num}.md5"
    count = size // bs
    cmd = f'dd if=/dev/mtd{mtd_num} bs={bs} count={count} {skip} | md5sum > "{md5_remote_fn}" '
    try:
        self.gw.run_cmd(cmd)
        self.gw.download(md5_remote_fn, md5_local_fn)
    except Exception:
        return -5
    if not os.path.exists(md5_local_fn):
        return -4
    with open(md5_local_fn, 'r', encoding = 'latin1') as file:
        md5 = file.read()
    os.remove(md5_local_fn)
    if not md5:
        return -3
    if md5.startswith('md5sum:'):
        return -2
    md5 = md5.split(' ')[0]
    md5 = md5.strip()
    if len(md5) != 32:
        return -1
    return md5.lower()

  def get_bootloader(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.bl = Bootloader()
    self.bl_list = []
    ret = self.bl
    if verbose:
      print("Bootloader info:")
    blist = ['bootloader', 'uboot', 'SBL1', 'APPSBL', 'SBL2', 'SBL3', 'BL2', 'FIP']
    plst = self.get_part_list(blist)
    if not plst:
      return ret
    for i, p in enumerate(plst):  
      bl = Bootloader()
      bl.addr = self.partlist[p]['addr']
      size = self.partlist[p]['size']
      name = self.partlist[p]['name']
      name = ''.join(e for e in name if e.isalnum())
      fn_local  = 'outdir/mtd{id}_{name}.bin'.format(id=p, name=name)
      fn_remote = '/tmp/bl_{name}.bin'.format(name=name)
      bs = 128*1024
      cnt = size // bs
      try:
        self.gw.run_cmd("dd if=/dev/mtd{i} of={o} bs={bs} count={cnt}".format(i=p, o=fn_remote, bs=bs, cnt=cnt))
        self.gw.download(fn_remote, fn_local)
        self.gw.run_cmd("rm -f " + fn_remote)
      except Exception:
        continue
      if verbose:
        print("  addr: 0x%08X (size: 0x%08X)" % (bl.addr, self.partlist[p]['size']))
      if not os.path.exists(fn_local):
        continue
      if os.path.getsize(fn_local) <= 1:
        continue
      with open(fn_local, "rb") as file:
        data = file.read()
      bl.img = data
      self.bl_list.append(bl)
      if data[0:4] == b'\x27\x05\x19\x56':
        bl.img_size = 0x40 + int.from_bytes(data[0x0C:0x0C+4], byteorder='big')
      else:
        if self.info.cpu_arch == 'mips':
          bl.spi_rom = True
      if bl.img_size is None:
        x = data.find(b'\x00' * 0x240)
        if x > 0:
          bl.img_size = x
        x = data.find(b'\xFF' * 0x240)
        if x > 0 and x < (bl.img_size if bl.img_size is not None else len(data)):
          bl.img_size = x
      max_size = bl.img_size if bl.img_size is not None else len(data)
      if verbose:
        print("    image size: {} bytes".format(bl.img_size))
      #if not bl.type:
      #  x = data.find(b"Breed ")
      #  if (x > 0 and x < 0x40):
      #    bl.type = 'breed'
      if not bl.type:
        x = data.find(b'hackpascal@gmail.com')
        if x > 0 and x < max_size:
          bl.type = 'breed'
      if not bl.type:
        x = data.find(b"PandoraBox-Boot")
        if x > 0 and x < max_size:
          bl.type = 'pandora'
      if not bl.type:
        x = data.find(b"UBoot Version")
        if x > 0 and x < max_size:
          bl.type = 'uboot'
      if verbose:
        print("    type: {}".format(bl.type))
    if self.bl_list:
      self.bl = self.bl_list[0]
    if verbose:
      print("") 
    return self.bl  
      
  def get_env_list(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.env.fw = EnvBuffer()
    self.env.breed = EnvBuffer() 
    self.env.bdata = EnvBuffer()    
    self.env_list = []
    ret = self.env.fw
    if verbose:
      print("ENV info:")
    envlist = ['config', 'nvram', 'APPSBLENV', 'bdata']
    plst = self.get_part_list(envlist)
    if not plst:
      return ret
    env_breed_addr = 0x60000  # breed env addr for r3g
    env_breed_size = 0x20000
    pb = self.get_part_num(env_breed_addr, '#')  
    if pb >= 0:
      plst.append(1000 + pb)
    for i, p in enumerate(plst):
      env = EnvBuffer()
      type = ''
      if p >= 1000 and p < 2000:
        type = 'breed'
        p = p - 1000
      part = self.partlist[p]
      name = part['name']
      name = ''.join(e for e in name if e.isalnum())
      if type == 'breed':
        env.addr = env_breed_addr
        data_size = part['size'] - (env.addr - part['addr'])
        if data_size < env_breed_size:
          continue
      else:
        env.addr = part['addr']
        data_size = part['size']
      env.max_size = data_size
      fn_local  = 'outdir/mtd{id}_{name}.bin'.format(id=p, name=name)
      fn_remote = '/tmp/env_{name}.bin'.format(name=name)
      if part['size'] < 128*1024:
        bs = 1024
        cnt = part['size'] // bs
      else:
        bs = 128*1024
        cnt = part['size'] // bs
      try:
        self.gw.run_cmd("dd if=/dev/mtd{i} of={o} bs={bs} count={cnt}".format(i=p, o=fn_remote, bs=bs, cnt=cnt))
        self.gw.download(fn_remote, fn_local)
        self.gw.run_cmd("rm -f " + fn_remote)
      except Exception:
        continue
      if verbose:
        print("  addr: 0x%08X (size: 0x%08X) " % (env.addr, env.max_size), type)
      if not os.path.exists(fn_local):
        continue
      if os.path.getsize(fn_local) <= 1:
        continue
      with open(fn_local, "rb") as file:
        data = file.read()
      if env.addr is None:
        continue
      prefix = data[0:4]      
      if prefix == b"\x00\x00\x00\x00" or prefix == b"\xFF\xFF\xFF\xFF":
        if type != 'breed':
          continue
      env.data = data
      env.offset = 0
      self.env_list.append(env)
      if self.env.fw.addr is None:
        self.env.fw = env
      if self.env.bdata.addr is None and name.lower().endswith('bdata'):
        self.env.bdata = env
      if self.env.breed.addr is None and type == 'breed':
        self.env.breed = env
      if type == 'breed':
        env.offset = env.addr - part['addr']
        data = data[env.offset:]
        if data[0:4] != b'ENV\x00':
          continue
        max_size = env_breed_size
        end = data.find(b"\x00\x00", 4)
        if end > max_size:
          continue
      else:
        max_size = data.find(b"\xFF\xFF\xFF\xFF", 4)
        if max_size <= 0:
          max_size = env.max_size
      env.max_size = max_size  
      if type != 'breed':  
        env_crc32 = int.from_bytes(prefix, byteorder='little')
        for i in range(1, 256):
          size = 1024 * i
          if size < len(data):
            buf = data[4:size]
            crc = binascii.crc32(buf)
          else:  
            buf = data[4:] + (b'\x00' * (size - len(data) - 4))
            crc = binascii.crc32(buf)
          if crc == env_crc32:
            if verbose:
              print("    CRC32: 0x%08X" % crc)
            if size <= data_size:
              env.max_size = size
            break
      if verbose:
        print("    max size: 0x%X" % env.max_size)
      #if verbose:
      #  env.buf = EnvBuffer(data, '\x00')
      #  buf, crc = env.buf.pack(env.max_size)
      #  print("    XXX CRC: 0x%X (len = %X)" % (crc, len(buf)))
      end = data.find(b"\x00\x00", 4)      
      if (end <= 4):
        continue
      data = data[4:end+1]
      env.delim = '\x00'
      env.crc_prefix = False
      try:
        env.encoding = 'UTF-8'
        env.var = env.parse_env_b(data, env.delim, encoding = env.encoding)
      except Exception:
        env.encoding = 'latin_1'
        env.var = env.parse_env_b(data, env.delim, encoding = env.encoding)
      env.crc_prefix = True
      if verbose >= 2 and env.var:
        for i, (k, v) in enumerate(env.var.items()):
          if (v is not None):
            v = '=' + v
            print("    " + k + v)
    if self.env_list:
      self.env.fw = self.env_list[0]
    if verbose:
      print("") 
    return self.env.fw


class SysLog():
  gw = None       # Gateway()
  verbose = 1
  timeout = 10
  files = []
  skiplogs = True
  mtdlist = []
  bdata = None    # EnvBuffer()

  def __init__(self, gw, timeout = 17, verbose = 1, infolevel = 1):
    self.gw = gateway.Gateway(detect_ssh = False) if gw is None else gw
    self.verbose = verbose
    self.timeout = timeout
    os.makedirs('outdir', exist_ok = True)
    os.makedirs('tmp', exist_ok = True)
    if infolevel > 0:
      self.update(infolevel)
      
  def update(self, infolevel):
    if infolevel >= 1:
      self.download_syslog()
    if infolevel >= 2:
      self.parse_baseinfo(fatal_error = True)
      self.parse_mtdlist()
    if infolevel >= 3:
      self.parse_bdata(fatal_error = True)

  def download_syslog(self, timeout = None):
    timeout = timeout if timeout is not None else self.timeout
    self.files = []
    if not self.gw:
      gw = gateway.Gateway(detect_ssh = False)
      gw.web_login()
    else:
      gw = self.gw
      if gw.status < 1:
        gw.detect_device()
      if not gw.stok:
        gw.web_login()
    if gw.status < 1:
      die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))
    if self.verbose > 0:
      print("Start generating syslog...")
    r2 = gw.api_request("API/misystem/sys_log", resp = 'text', timeout = timeout)
    if '"code":0' not in r2:
      die("SysLog not generated!")
    try:
      path = re.search(r'"path":"(.*?)"', r2)
      path = path.group(1).strip()
    except Exception:
      die("SysLog not generated! (2)")
    url = "http://" + path
    if self.verbose > 0:
      print('Downloading SysLog from file "{}" ...'.format(url))
    zip = b''
    with requests.get(url, stream=True, timeout = timeout) as r3:
      r3.raise_for_status()
      for chunk in r3.iter_content(chunk_size=8192): 
        zip += chunk
    fn_local = 'outdir/syslog.tar.gz'
    with open(fn_local, "wb") as file:
      file.write(zip)
    #if os.path.exists("syslog_test.tar.gz"):  # TEST
    #  fn_local = "syslog_test.tar.gz"
    tar = tarfile.open(fn_local, mode='r:gz')
    for member in tar.getmembers():
      if not member.isfile() or not member.name:
        continue 
      if self.skiplogs and member.name.find('usr/log/') >= 0:  # skip raw syslog files
        continue
      item = types.SimpleNamespace()
      item.name = member.name
      item.size = member.size
      item.data = tar.extractfile(member).read()
      self.files.append(item)
      if self.verbose >= 3:
        print('name = "{}", size = {} ({})'.format(item.name, item.size, len(item.data)))
        if len(item.data) < 200:
          print(item.data)
    tar.close()
    return self.files
    
  def get_file_by_name(self, filename, fatal_error = False):
    if self.files:
      for i, item in enumerate(self.files):
        if os.path.basename(item.name) == filename:
          return item
    if fatal_error:
      die('File "{}" not found in syslog!'.format(filename))
    return None

  def parse_baseinfo(self, fatal_error = False):
    self.device_sn = ""
    file = self.get_file_by_name('xiaoqiang.log', fatal_error)
    txt = file.data.decode('latin_1')
    sn = re.search('====SN\n(.*?)\n====', txt)
    if not sn:
      if fatal_error:
        die('Device SN not found into syslog!')
      return ""
    sn = sn.group(1).strip()
    if self.verbose >= 1:
      print('Device SN: {}'.format(sn))
    self.device_sn = sn
    return sn

  def parse_mtdlist(self):
    self.mtdlist = []
    file = self.get_file_by_name('xiaoqiang.log', fatal_error = True)
    txt = file.data.decode('latin_1')
    x = txt.find("\nMTD  table:\n")
    if x <= 0:
      die('MTD table not found into syslog!')
    mtdtbl = re.findall(r'mtd([0-9]+): ([0-9a-fA-F]+) ([0-9a-fA-F]+) "(.*?)"', txt)
    if len(mtdtbl) <= 0:
      return []
    mtdlist = []
    if self.verbose:
      print("SysLog MTD table:")
    for i, mtd in enumerate(mtdtbl):
      item = types.SimpleNamespace()
      item.id = int(mtd[0])
      item.size = int(mtd[1], 16)
      item.name = mtd[3]
      mtdlist.append(item)
      if self.verbose:
        print('  %2d > size: 0x%08X  name: "%s"' % (item.id, item.size, item.name))
    self.mtdlist = mtdlist
    return mtdlist

  def get_mtd_by_name(self, name):
    if self.mtdlist:
      name = name.lower()
      for i, mtd in enumerate(self.mtdlist):
        if mtd.name.lower().endswith(name):
          return mtd
    return None

  def parse_bdata(self, fatal_error = False):
    self.bdata = None
    file = self.get_file_by_name('bdata.txt', fatal_error)
    if not file:
      return None
    try:
      data = file.data.decode('UTF-8')
    except Exception:
      data = file.data.decode('latin_1')
    env = EnvBuffer(data, '\n')
    if self.verbose >= 2:
      print('SysLog BData List:')
      for i, (k, v) in enumerate(env.var.items()):
        v = '' if (v is None) else ('=' + v)
        print("  " + k + v)
    self.bdata = env
    return env


if __name__ == "__main__":
  if len(sys.argv) > 1 and sys.argv[1] == 'syslog':
    gw = gateway.Gateway(timeout = 4, detect_ssh = False)
    if gw.status < 1:
      die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))
    slog = SysLog(gw, timeout = 22, verbose = 1, infolevel = 2)
    sys.exit(0)
  
  fn_dir    = ''
  fn_old    = 'full_info_old.txt'
  fn_local  = 'full_info.txt'
  fn_remote = '/outdir/full_info.txt'

  if os.path.exists(fn_local): 
    if os.path.exists(fn_old):
      os.remove(fn_old)
    os.rename(fn_local, fn_old)

  info = DevInfo(verbose = 1, infolevel = 99)

  file = open(fn_local, "w")
  file.write("_MTD_partitions_:\n")
  for i, part in enumerate(info.partlist):
    name = part['name']
    addr = "%08X" % part['addr']
    size = "%08X" % part['size']
    ro = "?"
    if 'ro' in part:
      ro = '1' if part['ro'] else '0'
    file.write(f'  {"%2d" % i} > addr: {addr}  size: {size}  ro: {ro}  name: "{name}" \n')
  file.write("\n")  
  file.write("_Base_info_:\n")
  file.write('  Linux stamp: {}\n'.format(info.info.linux_stamp))
  file.write('  Linux version: {}\n'.format(info.info.linux_ver))
  file.write('  CPU arch: {}\n'.format(info.info.cpu_arch))
  file.write('  CPU name: {}\n'.format(info.info.cpu_name))
  file.write('  SPI rom: {}\n'.format(info.info.spi_rom))
  file.write("\n")  
  file.write("_Kernel_command_line_:\n")
  if (info.kcmdline):
    for i, (k, v) in enumerate(info.kcmdline.items()):
      v = '' if (v is None) else ('=' + v)
      file.write("  " + k + v + '\n')
  file.write("\n")  
  file.write("_NVRam_params_:\n")
  if (info.nvram):
    for i, (k, v) in enumerate(info.nvram.items()):
      v = '' if (v is None) else ('=' + v)
      file.write("  " + k + v + '\n')
  file.write("\n")  
  file.write("_RootFS_current_:\n")
  file.write('  num = {}\n'.format(info.rootfs.num))
  file.write('  mtd_num = {}\n'.format(info.rootfs.mtd_num))
  file.write('  mtd_dev = "{}"\n'.format(info.rootfs.mtd_dev))
  file.write('  partition = "{}"\n'.format(info.rootfs.partition))
  file.write("\n")
  #file.write('Board name: "{}" \n\n'.format(info.board_name))
  #file.write('Model: "{}" \n\n'.format(info.model))
  file.write("_Version_info_:\n")
  file.write("  UBoot: {} \n".format(info.ver.uboot1))
  file.write("  OpenWrt: {} \n".format(info.ver.openwrt))
  file.write("  Firmware: {} \n".format(info.ver.fw))
  file.write("  Channel: {} \n".format(info.ver.channel))
  file.write("  BuildTime: {} \n".format(info.ver.buildtime))
  file.write("  Hardware: {} \n".format(info.ver.hardware))
  file.write("  UBoot(2): {} \n".format(info.ver.uboot2))
  file.write("\n")
  file.write("_Bootloader_info_:\n")
  for i, bl in enumerate(info.bl_list):
    p = info.get_part_num(bl.addr, '#')
    name = info.partlist[p]['name'] if p >= 0 else "<unknown_name>"
    file.write("  {}:\n".format(name))
    file.write("    addr: 0x%08X \n" % (bl.addr if bl.addr else 0))
    file.write("    size: 0x%08X \n" % (len(bl.img) if bl.img else 0))
    file.write("    image size: {} bytes \n".format(bl.img_size))
    file.write("    type: {} \n".format(bl.type))
  file.write("\n")  
  file.write("_ENV_info_:\n")
  for i, env in enumerate(info.env_list):
    p = info.get_part_num(env.addr, '#')
    name = info.partlist[p]['name'] if p >= 0 else "<unknown_name>"
    file.write("  {}:\n".format(name))
    file.write("    addr: 0x%08X \n" % (env.addr if env.addr else 0))
    file.write("    size: 0x%08X \n" % (env.max_size if env.max_size else 0))
    file.write("    len: %d bytes \n" % env.len)
    file.write("    prefix: {} \n".format(env.data[env.offset:env.offset+4] if env.data else None))
    if env.var:
      for i, (k, v) in enumerate(env.var.items()):
        v = '' if (v is None) else ('=' + v)
        file.write("      " + k + v + '\n')
  file.write("\n")  
  file.close()  
    
  print("Full device information saved to file {}".format(fn_local))
