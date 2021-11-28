#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import datetime
import random
import hashlib
import subprocess
import re
import requests
import atexit

import socket
import ssh2
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN
from ssh2.utils import wait_socket

import telnetlib
import ftplib

if sys.version_info < (3,8,0):
  print("ERROR: Requires Python v3.8 or higher!")
  sys.exit(1)

from multiprocessing import shared_memory


EXPLOIT_VIA_DROPBEAR = True


def die(*args):
  err = 1
  prefix = "ERROR: "
  msg = "<undefined>"
  if len(args) > 0:
    if isinstance(args[0], int):
      err = args[0]
    else:
      msg = args[0]
  if (err == 0):
    prefix = ""
  if len(args) > 1:
    msg = args[1]
  print(" ")
  print(prefix + msg)
  print(" ")
  sys.exit(err)

def get_http_headers():
  headers = {}
  headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
  headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:65.0) Gecko/20100101 Firefox/65.0"
  return headers


class Gateway():
  use_ssh = EXPLOIT_VIA_DROPBEAR
  verbose = 2
  timeout = 4
  memcfg = None  # shared memory "XMiR_12345"
  device_name = None
  rom_version = None
  rom_channel = None
  mac_address = None
  nonce_key = None
  stok = None    # HTTP session token
  status = -2
  ftp = None
  socket = None  # TCP socket for SSH 
  ssh = None     # SSH session
  login = 'root' # default username
  
  def __init__(self, timeout = 4, verbose = 2, detect_device = True, load_cfg = True):
    self.verbose = verbose
    self.timeout = timeout
    self.device_name = None
    self.status = -2
    self.init_memcfg(load_cfg)
    atexit.register(self.shutdown)
    os.makedirs('outdir', exist_ok = True)
    os.makedirs('tmp', exist_ok = True)
    if detect_device:
      self.detect_device()

  def detect_device(self):
    self.device_name = None
    self.rom_version = None
    self.rom_channel = None
    self.mac_address = None
    self.nonce_key = None
    self.status = -2
    try:
      r0 = requests.get("http://{ip_addr}/cgi-bin/luci/web".format(ip_addr = self.ip_addr), timeout = self.timeout)
      r0.raise_for_status()
      #with open("r0.txt", "wb") as file:
      #  file.write(r0.text.encode("utf-8"))
      hardware = re.findall(r'hardware = \'(.*?)\'', r0.text)
      if hardware and len(hardware) > 0:
        self.device_name = hardware[0]
      else:
        hardware = re.findall(r'hardwareVersion: \'(.*?)\'', r0.text)
        if hardware and len(hardware) > 0:
          self.device_name = hardware[0]
      self.device_name = self.device_name.upper()
      romver = re.search(r'romVersion: \'(.*?)\'', r0.text)
      self.rom_version = romver.group(1).strip() if romver else None
      romchan = re.search(r'romChannel: \'(.*?)\'', r0.text)
      self.rom_channel = romchan.group(1).strip().lower() if romchan else None
      mac_address = re.search(r'var deviceId = \'(.*?)\'', r0.text)
      self.mac_address = mac_address.group(1) if mac_address else None
      nonce_key = re.search(r'key: \'(.*)\',', r0.text)
      self.nonce_key = nonce_key.group(1) if nonce_key else None
    except requests.exceptions.HTTPError as e:
      print("Http Error:", e)
    except requests.exceptions.ConnectionError as e:
      #print("Error Connecting:", e)
      return self.status
    except requests.exceptions.ConnectTimeout as e:
      print ("ConnectTimeout Error:", e)
    except requests.exceptions.Timeout as e:
      print ("Timeout Error:", e)
    except requests.exceptions.RequestException as e:
      print("Request Exception:", e)
    except Exception:      
      pass
    if not self.device_name:
      die("You need to make the initial configuration in the WEB of the device!")
    self.status = -1
    x = r0.text.find('a href="/cgi-bin/luci/web/init/hello')
    if (x > 10):
      die("You need to make the initial configuration in the WEB of the device!")
    self.status = 1
    return self.status

  def web_ping(self, timeout, wait_timeout = 0):
    ret = True
    start_time = datetime.datetime.now()
    try:
      res = requests.get("http://{ip_addr}/cgi-bin/luci/web".format(ip_addr = self.ip_addr), timeout = timeout)
      res.raise_for_status()
      mac_address = re.search(r'var deviceId = \'(.*?)\'', res.text)
      self.mac_address = mac_address.group(1) if mac_address else None
      nonce_key = re.search(r'key: \'(.*)\',', res.text)
      self.nonce_key = nonce_key.group(1) if nonce_key else None
    except Exception:      
      ret = False
    if wait_timeout > 0:
      dt = (wait_timeout * 1000 * 1000) - (datetime.datetime.now() - start_time).microseconds
      if dt > 0:
        time.sleep(dt / 1000 / 1000)
    return ret

  def web_login(self):
    self.stok = None
    if not self.nonce_key or not self.mac_address:
      die("Xiaomi Mi Wi-Fi device is wrong model or not the stock firmware in it.")
    nonce = "0_" + self.mac_address + "_" + str(int(time.time())) + "_" + str(random.randint(1000, 10000))
    web_pass = self.webpassword
    if not web_pass:
      web_pass = input("Enter device WEB password: ")
    account_str = (web_pass + self.nonce_key).encode('utf-8')
    account_str = hashlib.sha1(account_str).hexdigest()
    password = (nonce + account_str).encode('utf-8')
    password = hashlib.sha1(password).hexdigest()
    username = 'admin'
    data = "username={username}&password={password}&logtype=2&nonce={nonce}".format(username = username, password = password, nonce = nonce)
    requrl = "http://{ip_addr}/cgi-bin/luci/api/xqsystem/login".format(ip_addr = self.ip_addr)
    res = requests.post(requrl, data = data, headers = get_http_headers())
    try:
      stok = re.findall(r'"token":"(.*?)"', res.text)[0]
    except Exception:
      self.webpassword = ""
      die("WEB password is not correct!")
    self.webpassword = web_pass
    self.stok = stok
    return stok

  @property
  def apiurl(self):
    return "http://{ip_addr}/cgi-bin/luci/;stok={stok}/api/".format(ip_addr = self.ip_addr, stok = self.stok)

  def get_factory_info(self, timeout = 5):
    self.facinfo = {}
    if not self.stok:
      self.web_login()
    try:
      res = requests.get(self.apiurl + 'xqsystem/fac_info', timeout = timeout)
      res.raise_for_status()
    except Exception:      
      return {}
    self.facinfo = json.loads(res.text)
    return self.facinfo

  def wait_shutdown(self, timeout, verbose = 1):
    if verbose:
      print('Waiting for shutdown: ', end='', flush=True)
    start_time = datetime.datetime.now()
    while datetime.datetime.now() - start_time <= datetime.timedelta(seconds = timeout):
      if verbose:
        print('.', end='', flush=True)
      if self.web_ping(1, 1) is False:
        if verbose:
          print('.', flush=True)
        time.sleep(1)
        self.stok = None
        return True
    if verbose:
      print('timedout', flush=True)
    return False

  def wait_reboot(self, timeout, verbose = 1):
    if verbose:
      print('Waiting for reboot: ', end='', flush=True)
    start_time = datetime.datetime.now()
    while datetime.datetime.now() - start_time <= datetime.timedelta(seconds = timeout):
      if verbose:
        print('.', end='', flush=True)
      if self.web_ping(1, 1) is True:
        if verbose:
          print('log', end='', flush=True)
        self.web_login()  # TODO
        if verbose:
          print('on', end='', flush=True)
        for i in range(5):
          time.sleep(1)
          if verbose:
            print('.', end='', flush=True)
        print('', flush=True)
        return True
    if verbose:
      print('timedout', flush=True)
    return False    

  #===============================================================================
  def shutdown(self):
    if self.use_ssh:
      try:
        self.ssh.disconnect()
      except Exception:
        pass
      try:
        self.socket.close()
      except Exception:
        pass
    else:  
      try:
        self.ftp.quit()
      except Exception:
        pass
      try:
        self.ftp.close()
      except Exception:
        pass
    self.ftp = None
    self.ssh = None
    self.socket = None

  #===============================================================================
  def init_memcfg(self, load_cfg = True):
    _env_master_cfg = 'XMiR_cfg'
    _memcfgname = 'XMiR_'
    _memcfgsize = 1024*1024
    ppid = os.environ[_env_master_cfg] if _env_master_cfg in os.environ else None
    if ppid is None:
      load_cfg = False
    if load_cfg:
      try:
        sm = shared_memory.SharedMemory(_memcfgname + ppid)
      except FileNotFoundError:
        del os.environ[_env_master_cfg]
        load_cfg = False
    if not load_cfg:    
      sm = shared_memory.SharedMemory(_memcfgname + '%d' % os.getpid(), create=True, size=_memcfgsize)
      if not _env_master_cfg in os.environ:
        os.environ[_env_master_cfg] = str(os.getpid())
    self.memcfg = sm

  def load_memcfg(self):
    cfg = {}
    if not self.memcfg:
      return cfg
    size = bytes(self.memcfg.buf[:4])
    size = int.from_bytes(size, byteorder='little', signed=True)
    if size <= 0:
      return cfg
    data = bytes(self.memcfg.buf[4:4+size])
    cfg = json.loads(data.decode('utf-8'))
    return cfg

  def get_memcfg_param(self, key, defvalue = None):
    cfg = self.load_memcfg()    
    return cfg[key] if key in cfg else defvalue

  def set_memcfg_param(self, key, value):
    cfg = self.load_memcfg()
    cfg[key] = value.strip() if isinstance(value, str) else value
    self.save_memcfg(cfg)

  def save_memcfg(self, cfg):
    data = b''
    if cfg:
      data = json.dumps(cfg, ensure_ascii=False).encode('utf-8')
    size = len(data)
    self.memcfg.buf[:4] = size.to_bytes(4, byteorder='little', signed=True)
    if size > 0:
      self.memcfg.buf[4:4+len(data)] = data

  #===============================================================================
  @property
  def ssh_port(self):
    return self.get_memcfg_param('ssh_port', 22)

  @ssh_port.setter
  def ssh_port(self, value):
    self.set_memcfg_param('ssh_port', value)

  @property
  def passw(self):
    return self.get_memcfg_param('passw', None)  # password for root user

  @passw.setter
  def passw(self, value):
    self.set_memcfg_param('passw', value)

  @property
  def webpassword(self):
    return self.get_memcfg_param('webpassword', None)

  @webpassword.setter
  def webpassword(self, value):
    self.set_memcfg_param('webpassword', value)

  #===============================================================================
  @property
  def ip_addr(self):
    return self.get_config_param('device_ip_addr', '192.168.1.1').strip()

  @ip_addr.setter
  def ip_addr(self, value):
    self.set_config_param('device_ip_addr', value)

  #===============================================================================
  def load_config(self):
    config = {}
    if os.path.exists('config.txt'): 
      with open('config.txt', 'r') as file:
        config = json.load(file)
    return config

  def get_config_param(self, key, defvalue = None):
    config = self.load_config()    
    return config[key] if key in config else defvalue

  def set_config_param(self, key, value):
    config = self.load_config()
    config[key] = value.strip() if isinstance(value, str) else value
    self.save_config(config)

  def save_config(self, config):    
    with open('config.txt', 'w') as file:
      json.dump(config, file, indent=4, sort_keys=True)

  #===============================================================================
  def set_timeout(self, timeout):
    self.timeout = timeout
    if self.use_ssh and self.ssh:
      self.ssh.set_timeout(int(self.timeout * 1000))

  def get_ssh(self, verbose = 0, contimeout = None):
    if self.ssh:
      try:
        self.ssh.keepalive_send()
        return self.ssh
      except Exception:
        pass
    self.shutdown()
    try:
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      if contimeout is not None:
        self.socket.settimeout(contimeout)
      self.socket.connect((self.ip_addr, self.ssh_port))
      self.socket.settimeout(None)  # enable blocking mode
      self.ssh = ssh2.session.Session()
      self.ssh.handshake(self.socket)
      self.ssh.userauth_password(self.login, self.passw)
      self.ssh.set_blocking(True)
      self.ssh.set_timeout(int(self.timeout * 1000))
      return self.ssh
    except Exception as e:
      #print(e)
      if verbose:
        die("SSH server not responding (IP: {})".format(self.ip_addr))
      self.shutdown()
    return None

  def check_telnet(self, timeout = 2, port = 23, verbose = 0):
    try:
      tn = telnetlib.Telnet(self.ip_addr, port=port, timeout=timeout)
      tn.close()
      return True
    except Exception as e:
      if verbose:
        die("TELNET not responding (IP: {})".format(self.ip_addr))
    return False

  def get_telnet(self, verbose = 0):
    try:
      tn = telnetlib.Telnet(self.ip_addr, timeout=4)
    except Exception as e:
      if verbose:
        die("TELNET not responding (IP: {})".format(self.ip_addr))
      return None
    try:
      p_login = b'login: '
      p_passw = b'Password: '
      prompt = "{}@XiaoQiang:(.*?)#".format(self.login).encode('ascii')
      idx, obj, output = tn.expect([p_login, prompt], timeout=2)
      if idx < 0:
        raise Exception('')
      if idx > 0:
        tn.prompt = obj.group()
        return tn
      tn.write("{}\n".format(self.login).encode('ascii'))
      idx, obj, output = tn.expect([p_passw, prompt], timeout=2)
      if idx < 0:
        raise Exception('')
      if idx > 0:
        tn.prompt = obj.group()
        return tn
      tn.write("{}\n".format(self.passw).encode('ascii'))
      idx, obj, output = tn.expect([prompt], timeout=2)
      if idx < 0:
        raise Exception('')
      tn.prompt = obj.group()
      return tn
    except Exception as e:
      #print(e)
      if verbose:
        die("Can't login to TELNET (IP: {})".format(self.ip_addr))
    return None

  def get_ftp(self, verbose = 0):
    if self.ftp and self.ftp.sock:
      try:
        self.ftp.voidcmd("NOOP")
        return self.ftp  #Already connected
      except Exception:
        pass
    self.shutdown()
    try:
      #timeout = 10 if self.timeout < 10 else self.timeout
      self.ftp = ftplib.FTP(self.ip_addr, user=self.login, passwd=self.passw, timeout=self.timeout)
      self.ftp.voidcmd("NOOP")
      return self.ftp
    except Exception:
      if verbose:
        die("ftp not responding (IP: {})".format(self.ip_addr))
      self.shutdown()
    return None

  def ping(self, verbose = 2, contimeout = None):
    if self.use_ssh:
      ssh = self.get_ssh(verbose, contimeout)
      if not ssh:
        return False
    else:
      tn = self.get_telnet(verbose)
      if not tn:
        return False
      ftp = self.get_ftp(verbose)
      if not ftp:
        return False
    return True

  def run_cmd(self, cmd, msg = None, timeout = None):
    if self.use_ssh:
      ssh = self.get_ssh(self.verbose)
    else:
      tn = self.get_telnet(self.verbose)
    if (msg):
      print(msg)
    cmdlist = []
    if isinstance(cmd, str):      
      cmdlist.append(cmd)
    else:
      cmdlist = cmd
    for idx, cmd in enumerate(cmdlist):
      if self.use_ssh:
        channel = ssh.open_session()
        if timeout is not None:
          saved_timeout = ssh.get_timeout()
          ssh.set_timeout(int(timeout * 1000))
        #channel.pty('xterm')
        #print("exec = '{}'".format(cmd))
        channel.execute(cmd)
        try:
          channel.wait_eof()
        except ssh2.exceptions.Timeout:
          die("SSH execute command timed out! CMD: \"{}\"".format(cmd))
        if timeout is not None:
          ssh.set_timeout(saved_timeout)
        try:
          channel.close()
          channel.wait_closed()
        except Exception:
          pass
        #status = channel.get_exit_status()
      else:
        cmd = (cmd + '\n').encode('ascii')
        tn.write(cmd)
        tn.read_until(tn.prompt, timeout = 4 if timeout is None else timeout)
    if not self.use_ssh:
      tn.write(b"exit\n")
    return True

  def download(self, fn_remote, fn_local, verbose = 1):
    if verbose and self.verbose:
      print('Download file: "{}" ....'.format(fn_remote))
    if self.use_ssh:
      ssh = self.get_ssh(self.verbose)
      channel, fileinfo = ssh.scp_recv2(fn_remote)
      total_size = fileinfo.st_size
      read_size = 0
      with open(fn_local, 'wb') as file:
        while read_size < total_size:
          size, data = channel.read()
          if size > 0:
            if read_size + len(data) > total_size:
              file.write(data[:total_size - read_size])
            else:
              file.write(data)
            read_size += size
    else:
      ftp = self.get_ftp(self.verbose)
      file = open(fn_local, 'wb')
      ftp.retrbinary('RETR ' + fn_remote, file.write)
      file.close()
    return True

  def upload(self, fn_local, fn_remote, verbose = 1):
    try:
      file = open(fn_local, 'rb')
    except Exception:
      die('File "{}" not found.'.format(fn_local))
    if verbose and self.verbose:
      print('Upload file: "{}" ....'.format(fn_local))
    if self.use_ssh:
      ssh = self.get_ssh(self.verbose)
      finfo = os.stat(fn_local)
      channel = ssh.scp_send64(fn_remote, finfo.st_mode & 0o777, finfo.st_size, finfo.st_mtime, finfo.st_atime)
      size = 0
      for data in file:
        channel.write(data)
        size = size + len(data)
      #except ssh2.exceptions.SCPProtocolError as e:
    else:
      ftp = self.get_ftp(self.verbose)
      ftp.storbinary('STOR ' + fn_remote, file)
    file.close()
    return True


#===============================================================================
if __name__ == "__main__":
  if len(sys.argv) > 1:
    ip_addr = sys.argv[1]
    gw = Gateway(detect_device = False)
    gw.ip_addr = ip_addr
    print("Device IP-address changed to {}".format(ip_addr))
    
