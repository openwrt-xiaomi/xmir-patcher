#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import types
import binascii
import tarfile
import io
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import gateway
from gateway import die
from envbuffer import EnvBuffer


class RootFS():
  num = None       # 0 / 1
  dev = None       # "/dev/mtd10"
  mtd_name = None  # "mtd10" / "mtd11"
  partition = None # "rootfs0" / "rootfs1"

class Bootloader():
  type = None      # 'uboot' / 'breed' / 'pandora'
  img = None
  img_size = None
  addr = None
  spi_rom = False

class BaseInfo():
  linux_ver = None
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
        die("Partition list is empty!")
      self.get_rootfs()
      self.get_baseinfo()
      if not self.info.cpu_arch:
        die("Can't detect CPU arch!")
    if infolevel >= 2:
      self.get_ver()
    if infolevel >= 3:
      self.get_kernel_cmdline()
      self.get_nvram()
    if infolevel >= 4:
      self.get_bootloader()
    if infolevel >= 5:
      self.get_env_list()

  def get_dmesg(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.dmesg = None
    fn_local  = 'outdir/dmesg.log'
    fn_remote = '/tmp/dmesg.log'
    try:
      self.gw.run_cmd("dmesg > " + fn_remote)
      self.gw.download(fn_remote, fn_local)
      self.gw.run_cmd("rm -f " + fn_remote)
    except Exception:
      return self.kcmdline
    if not os.path.exists(fn_local):
      return None
    if os.path.getsize(fn_local) <= 1:
      return None
    with open(fn_local, "r") as file:
      self.dmesg = file.read()
    return self.dmesg

  def get_part_table(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.partlist = []
    if not self.dmesg:
      return self.partlist
    x = self.dmesg.find(" MTD partitions on ")
    if x <= 0:
      return self.partlist
    parttbl = re.findall(r'0x0000(.*?)-0x0000(.*?) : "(.*?)"', self.dmesg)
    if len(parttbl) <= 0:
      return self.partlist
    if verbose:
      print("MTD partitions:")
    for i, part in enumerate(parttbl):
      addr = int(part[0], 16)
      size = int(part[1], 16) - addr
      name = part[2]
      self.partlist.append({'addr': addr, 'size': size, 'name': name})
      if verbose:
        print('  %2d > addr: 0x%08X  size: 0x%08X  name: "%s"' % (i, addr, size, name))
    if verbose:
      print(" ")
    return self.partlist

  def get_part_num(self, name_or_addr, comptype = None):
    if not self.partlist:
      return -2
    for i, part in enumerate(self.partlist):
      if isinstance(name_or_addr, int):
        if part['addr'] == 0 and part['size'] > 0x00800000:
          continue  # skip "ALL" part
        addr = name_or_addr
        if addr >= part['addr'] and addr < part['addr'] + part['size']:
          return i
      else:   
        if comptype and comptype[0] == 'e':
          if part['name'].lower().endswith(name_or_addr.lower()):
            return i
        if part['name'].lower() == name_or_addr.lower():
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

  def get_part_by_addr(self, addr):
    if not self.partlist:
      return None
    for i, part in enumerate(self.partlist):
      if part['addr'] == 0 and part['size'] > 0x00800000:
        continue  # skip "ALL" part
      if part['addr'] == addr:
        return part
    return None

  def get_rootfs(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.rootfs = RootFS()
    if not self.dmesg:
      return self.rootfs
    if verbose:
      print('RootFS info:')
    # flag_boot_rootfs=0 mounting /dev/mtd10 
    res = re.findall(r'flag_boot_rootfs=(.*?) mounting (.*?)\n', self.dmesg)
    if len(res) > 0:
      res = res[0]
      if verbose:
        print('  num = {}'.format(res[0]))
        print('  dev = "{}"'.format(res[1]))
      self.rootfs.num = int(res[0]) if res[0] else None
      self.rootfs.dev = res[1]
    # UBI: attached mtd10 (name "rootfs0", size 32 MiB) to ubi0 
    res = re.findall(r'attached (.*?) \(name "(.*?)", size', self.dmesg)
    if len(res) > 0:
      res = res[0]
      self.rootfs.mtd_name = res[0]
      self.rootfs.partition = res[1]
      if verbose:
        print('  mtd_name = {}'.format(res[0]))
        print('  partition = "{}"'.format(res[1]))
    if verbose:
      print(" ")
    return self.rootfs
    
  def get_baseinfo(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.info = BaseInfo()
    ret = self.info
    if not self.dmesg:
      return ret
    if verbose:
      print('Base info:')
    # Linux version 3.10.14 (jenkins@cefa8cf504dc) (gcc version 4.8.5 (crosstool-NG crosstool-ng-1.22.0) ) 
    x = re.search(r'Linux version (.*?) ', self.dmesg)
    ret.linux_ver = x.group(1).strip() if x else None
    if verbose:
      print('  Linux version: {}'.format(ret.linux_ver))
    # MIPS secondary cache 256kB, 8-way, linesize 32 bytes.
    x = re.search(r'MIPS secondary cache (.*?) linesize ', self.dmesg)
    if x:
      ret.cpu_arch = 'mips'
    # CPU: ARMv7 Processor [512f04d0] revision 0 (ARMv7), cr=10c5387d
    x = re.search(r'CPU: ARMv7 Processor(.*?)revision ', self.dmesg)
    if x:
      ret.cpu_arch = 'armv7'
    if verbose:
      print('  CPU arch: {}'.format(ret.cpu_arch))
    # start MT7621 PCIe register access
    x = re.search(r'start (.*?) PCIe register access', self.dmesg)
    if x:
      ret.cpu_name = x.group(1).strip().lower() if x else None
    x = self.dmesg.find("acpuclk-ipq806x acpuclk-ipq806x: ")
    if x > 0:
      ret.cpu_name = 'ipq806x'
    if verbose:
      print('  CPU name: {}'.format(ret.cpu_name))
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
    with open(fn_local, "r") as file:
      data = file.read()
    if verbose:
      print("Kernel command line:")
      print(" ", data)
    if not retdict:
      return data
    data = data.strip()
    data = data.replace("\n", ' ')
    data = data.replace("\x00", ' ')
    data = data.strip()
    env = EnvBuffer(data, ' ', crc_prefix = False, encoding = 'ascii')
    self.kcmdline = env.var
    #self.kcmdline = type("Names", [object], self.kcmdline)
    return self.kcmdline

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
    with open(fn_local, "r") as file:
      data = file.read()
    if not retdict:
      return data
    if verbose:
      print("NVRam params:")
    env = EnvBuffer(data, '\n', crc_prefix = False, encoding = 'ascii')
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

  def get_bootloader(self, verbose = None):
    verbose = verbose if verbose is not None else self.verbose
    self.bl = Bootloader()
    self.bl_list = []
    ret = self.bl
    if verbose:
      print("Bootloader info:")
    plst = self.get_part_list(['bootloader', 'uboot', 'SBL1', 'APPSBL', 'SBL2', 'SBL3'], comptype = 'ends')
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
    plst = self.get_part_list(['config', 'nvram', 'APPSBLENV', 'bdata'], comptype = 'ends')
    if not plst:
      return ret
    env_breed_addr = 0x60000  # breed env addr for r3g
    env_breed_size = 0x20000
    pb = self.get_part_num(env_breed_addr)  
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
      env.encoding = 'ascii'
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
  mtdlist = []
  bdata = None    # EnvBuffer()

  def __init__(self, gw, timeout = 10, verbose = 1, infolevel = 1):
    self.gw = gateway.Gateway() if gw is None else gw
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
      self.parse_mtdlist()
    if infolevel >= 3:
      self.parse_bdata()

  def download_syslog(self, timeout = None):
    timeout = timeout if timeout is not None else self.timeout
    self.files = []
    if not self.gw:
      gw = gateway.Gateway()
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
    r2 = requests.get(gw.apiurl + "misystem/sys_log", timeout = self.timeout)
    if r2.text.find('"code":0') < 0:
      die("SysLog not generated!")
    try:
      path = re.search(r'"path":"(.*?)"', r2.text)
      path = path.group(1).strip()
    except Exception:
      die("SysLog not generated! (2)")
    url = "http://" + path
    if self.verbose > 0:
      print('Downloading SysLog from file "{}" ...'.format(url))
    zip = b''
    with requests.get(url, stream=True, timeout = self.timeout) as r3:
      r3.raise_for_status()
      for chunk in r3.iter_content(chunk_size=8192): 
        zip += chunk
    fn_local = 'outdir/syslog.tar.gz'
    with open(fn_local, "wb") as file:
      file.write(zip)
    if os.path.exists("syslog_test.tar.gz"):  # TEST
      fn_local = "syslog_test.tar.gz"
    tar = tarfile.open(fn_local, mode='r:gz')
    for member in tar.getmembers():
      if not member.isfile() or not member.name:
        continue 
      if member.name.find('usr/log/') >= 0:  # skip raw syslog files
        continue
      item = types.SimpleNamespace()
      item.name = member.name
      item.size = member.size
      item.data = tar.extractfile(member).read()
      self.files.append(item)
      if self.verbose >= 2:
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

  def parse_mtdlist(self):
    self.mtdlist = []
    file = self.get_file_by_name('xiaoqiang.log', fatal_error = True)
    txt = file.data.decode('ascii')
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

  def parse_bdata(self):
    self.bdata = None
    file = self.get_file_by_name('bdata.txt', fatal_error = True)
    env = EnvBuffer(file.data.decode('ascii'), '\n')
    if self.verbose >= 2:
      print('SysLog BData List:')
      for i, (k, v) in enumerate(env.var.items()):
        v = '' if (v is None) else ('=' + v)
        print("  " + k + v)
    self.bdata = env
    return env


if __name__ == "__main__":
  if len(sys.argv) > 1 and sys.argv[1] == 'syslog':
    gw = gateway.Gateway(timeout = 4)
    if gw.status < 1:
      die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))
    slog = SysLog(gw, timeout = 10, verbose = 1, infolevel = 2)
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
  #if not info.partlist:
  #  die("В ядерном логе не обнаружена информация о разметке NAND")

  file = open(fn_local, "w")
  file.write("_MTD_partitions_:\n")
  for i, part in enumerate(info.partlist):
    file.write("  %2d > addr: %08X  size: %08X  name: \"%s\" \n" % (i, part['addr'], part['size'], part['name']))
  file.write("\n")  
  file.write("_Base_info_:\n")
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
  file.write('  dev = "{}"\n'.format(info.rootfs.dev))
  file.write('  mtd_name = "{}"\n'.format(info.rootfs.mtd_name))
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
    p = info.get_part_num(bl.addr)
    name = info.partlist[p]['name'] if p >= 0 else "<unknown_name>"
    file.write("  {}:\n".format(name))
    file.write("    addr: 0x%08X \n" % (bl.addr if bl.addr else 0))
    file.write("    size: 0x%08X \n" % (len(bl.img) if bl.img else 0))
    file.write("    image size: {} bytes \n".format(bl.img_size))
    file.write("    type: {} \n".format(bl.type))
  file.write("\n")  
  file.write("_ENV_info_:\n")
  for i, env in enumerate(info.env_list):
    p = info.get_part_num(env.addr)
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
