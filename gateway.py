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
import xmir_base
import ssh2
from ssh2.error_codes import LIBSSH2_ERROR_EAGAIN
from ssh2.utils import wait_socket
import telnetlib
import ftplib
if sys.version_info < (3,8,0):
  print("ERROR: Requires Python v3.8 or higher!")
  sys.exit(1)
from multiprocessing import shared_memory
import xqmodel
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
  def __init_fields(self):
    self.use_ssh = True
    self.use_ftp = False
    self.verbose = 2
    self.timeout = 4
    self.memcfg = None  # shared memory "XMiR_12345"
    self.model_id = -2
    self.device_name = None
    self.device_info = None
    self.rom_version = None
    self.rom_channel = None
    self.mac_address = None
    self.encryptmode = 0     # 0: sha1, 1: sha256
    self.nonce_key = None
    self.stok = None    # HTTP session token
    self.status = -2
    self.ftp = None
    self.socket = None  # TCP socket for SSH 
    self.ssh = None     # SSH session
    self.login = 'root' # default username
  
  def __init__(self, timeout = 4, verbose = 2, detect_device = True, detect_ssh = True, load_cfg = True):
    self.__init_fields()
    self.verbose = verbose
    self.timeout = timeout
    self.device_name = None
    self.device_info = None
    self.xqpassword = None
    self.status = -2
    self.xqModelList = xqmodel.xqModelList
    self.get_modelid_by_name = xqmodel.get_modelid_by_name
    self.init_memcfg(load_cfg)
    atexit.register(self.shutdown)
    atexit.register(self.free_memcfg)    
    os.makedirs('outdir', exist_ok = True)
    os.makedirs('tmp', exist_ok = True)
    if detect_device:
      self.detect_device()
    if detect_ssh:
      verb = 1 if verbose else 0
      interact = True if verbose else False
      port = self.detect_ssh(verbose = 1, interactive = interact)
      if port <= 0:
        die("Can't found valid SSH server on IP {}".format(self.ip_addr))
  def detect_device(self):
    self.model_id = -2
    self.device_name = None
    self.device_info = None
    self.rom_version = None
    self.rom_channel = None
    self.mac_address = None
    self.encryptmode = 0
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
    self.model_id = self.get_modelid_by_name(self.device_name)
    self.status = -1
    x = r0.text.find('a href="/cgi-bin/luci/web/init/hello')
    if (x > 10):
      die("You need to make the initial configuration in the WEB of the device!")
    self.status = 1
    ''' ==== get init_info ====
      {"code":0,"isSupportMesh":1,"secAcc":1,"inited":1,"connect":0,
       "modules":{"replacement_assistant":"1"},
       "hardware":"RB03","language":"en","server":"AP","romversion":"1.0.54","countrycode":"DE",
       "id":"36418/J1VT25382","routername":"Redmi_A141","displayName":"Redmi router AX6S","maccel":"1",
       "model":"xiaomi.router.rb03","bound":0,"isRedmi":1,
       "routerId":"a4aa1022-57a2-a530-d568-7905f1685a57"}    
    '''
    info = self.get_init_info()
    if info and info["code"] == 0:
      self.device_info = info
      if info["inited"] != 1:
        die("You need to make the initial configuration in the WEB of the Device!")
      if "newEncryptMode" in info:
        self.encryptmode = int(info["newEncryptMode"])
    self.xqpassword = self.get_xqpassword()
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
  # default password for Telnet
  def get_xqpassword(self, sn = None):
    if sn is None:
      if not self.device_info:
        return None
      if 'id' not in self.device_info:
        return None
      sn = self.device_info['id']  # id = SerialNumber
    guid = 'd44fb0960aa0-a5e6-4a30-250f-6d2df50a'   # finded into mkxqimage
    salt = '-'.join( reversed(guid.split('-')) )
    password = hashlib.md5( (sn + salt).encode('utf-8') ).hexdigest()
    return password[:8]
  def xqhash(self, string):
    if self.encryptmode == 0:
      return hashlib.sha1(string).hexdigest()
    else:
      return hashlib.sha256(string).hexdigest()
  def web_login(self):
    self.stok = None
    if not self.nonce_key or not self.mac_address:
      die("Xiaomi Mi Wi-Fi device is wrong model or not the stock firmware in it.")
    dtype = 0 # 0: Web, 1: Android, 2: iOS, 3: Mac, 4: PC 
    device = self.mac_address
    nonce = "{}_{}_{}_{}".format(dtype, device, int(time.time()), random.randint(1000, 10000))
    web_pass = self.webpassword
    if not web_pass:
      web_pass = input("Enter device WEB password: ")
    account_str = (web_pass + self.nonce_key).encode('utf-8')
    account_str = self.xqhash(account_str)
    password = (nonce + account_str).encode('utf-8')
    password = self.xqhash(password)
    username = 'admin'
    data = "username={username}&password={password}&logtype=2&nonce={nonce}".format(username = username, password = password, nonce = nonce)
    requrl = "http://{ip_addr}/cgi-bin/luci/api/xqsystem/login".format(ip_addr = self.ip_addr)
    res = requests.post(requrl, data = data, headers = get_http_headers())
    try:
      stok = re.findall(r'"token":"(.*?)"', res.text)[0]
    except Exception:
      self.webpassword = ""
      die("WEB password is not correct! (encryptmode = {})".format(self.encryptmode))
    self.webpassword = web_pass
    self.stok = stok
    return stok
  @property
  def apiurl(self):
    return "http://{ip_addr}/cgi-bin/luci/;stok={stok}/api/".format(ip_addr = self.ip_addr, stok = self.stok)
  def get_pub_info(self, api_name, timeout = 5):
    subsys = 'xqsystem'
    if api_name == 'router_info' or api_name == 'topo_graph':
      subsys = 'misystem'
    try:
      url = "http://{ip_addr}/cgi-bin/luci/api/{subsys}/{api_name}".format(ip_addr = self.ip_addr, subsys = subsys, api_name = api_name)
      res = requests.get(url, timeout = timeout)
      res.raise_for_status()
    except Exception:      
      return {}
    return json.loads(res.text)
  def get_init_info(self, timeout = 5):
    return self.get_pub_info('init_info', timeout = timeout)
  def get_factory_info(self, timeout = 5):
    self.facinfo = self.get_pub_info('fac_info', timeout = timeout)
    return self.facinfo
  def get_bdata_info(self, timeout = 5):
    return self.get_pub_info('bdata', timeout = timeout)
  def get_ip_info(self, timeout = 5):
    return self.get_pub_info('get_ip', timeout = timeout)
  def get_upgrade_status(self, timeout = 5):
    return self.get_pub_info('upgrade_status', timeout = timeout)
  def get_router_info(self, timeout = 5):
    return self.get_pub_info('router_info', timeout = timeout)
  def get_topo_graph_info(self, timeout = 5):
    return self.get_pub_info('topo_graph', timeout = timeout)

  def get_device_systime(self, fix_tz = True):
    # http://192.168.31.1/cgi-bin/luci/;stok=14b996378966455753104d187c1150b4/api/misystem/sys_time
    # response: {"time":{"min":32,"day":4,"index":0,"month":10,"year":2023,"sec":7,"hour":6,"timezone":"XXX"},"code":0}
    res = requests.get(self.apiurl + 'misystem/sys_time')
    try:
        dres = json.loads(res.text)
        code = dres['code']
    except Exception:
        raise RuntimeError(f'Error on parse response for command "sys_time" => {res.text}')
    if code != 0:
        raise RuntimeError(f'Error on get sys_time => {res.text}')
    dst = dres['time']
    if fix_tz and 'timezone' in dst:
        if "'" in dst['timezone'] or ";" in dst['timezone']:
            dst['timezone'] = "GMT0"
    return dst

  def set_device_systime(self, dst, year = 0, month = 0, day = 0, hour = 0, min = 0, sec = 0, timezone = ""):
    if dst:
        year     = dst['year']
        month    = dst['month']
        day      = dst['day']
        hour     = dst['hour']
        min      = dst['min']
        sec      = dst['sec']
        timezone = dst['timezone']
    params = { 'time': f"{year}-{month}-{day} {hour}:{min}:{sec}", 'timezone': timezone }
    res = requests.get(self.apiurl + 'misystem/set_sys_time', params = params)
    try:
        dres = json.loads(res.text)
        code = dres['code']
    except Exception:
        raise RuntimeError(f'Error on parse response for command "set_sys_time" => {res.text}')
    if code != 0:
        raise RuntimeError(f'Error on exec command "set_sys_time" => {res.text}')
    return res.text

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
  def reboot_device(self, wait_timeout = None):
    try:
      params = { 'client': 'web' }
      res = requests.post(self.apiurl + "xqsystem/reboot", params = params, timeout=self.timeout)
      if res.text.find('"code":0') < 0:
        return False
      if wait_timeout:
        if not self.wait_shutdown(wait_timeout):
          return False
      return True
    except Exception as e:
      return False
  #===============================================================================
  def shutdown(self):
    self.ssh_close()
    try:
      self.ftp.quit()
    except Exception:
      pass
    try:
      self.ftp.close()
    except Exception:
      pass
    self.ftp = None
  #===============================================================================
  def free_memcfg(self):
    if self.memcfg:
      try:
        self.memcfg.close() # https://docs.python.org/3/library/multiprocessing.shared_memory.html
      except Exception:
        pass
  
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
  @property
  def img_write(self):
    return self.get_config_param('img_write', True)
  @img_write.setter
  def img_write(self, value):
    self.set_config_param('img_write', value)
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
  def check_tcp_connect(self, ip, port, contimeout = 2, retobj = False):
    sock = None
    start_time = datetime.datetime.now()
    while datetime.datetime.now() - start_time <= datetime.timedelta(seconds = contimeout):
      try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.connect((ip, port))
        if retobj:
          return sock
        break
      except Exception:
        sock = None
    return True if sock else False
  def check_ssh(self, ip, port, password, contimeout = 2, timeout = 3):
    err = 0
    ssh = None
    sock = self.check_tcp_connect(ip, port, contimeout, retobj = True)
    if not sock:
      err = -1
    if password and err == 0:
      try:
        ssh = ssh2.session.Session()
        sock.settimeout(timeout)
        ssh.handshake(sock)
      except Exception as e:
        err = -2
      if err == 0:
        try:
          ssh.userauth_password(self.login, password)
        except Exception as e:
          err = -3
    try:
      ssh.disconnect()
    except Exception:
      pass
    try:
      sock.close()
    except Exception:
      pass
    return err
  def _detect_ssh(self, verbose = 1, interactive = True, contimeout = 2, aux_port = 0):
    ip_addr = self.ip_addr
    ssh_port = self.ssh_port
    if aux_port == 0 and self.model_id > 0 and self.model_id < 22:
      if ssh_port != 122:
        aux_port = 122  # exploit for "misystem/c_upload" (connect.py)
    passw = self.passw
    if passw:
      ret = self.check_ssh(ip_addr, ssh_port, passw, contimeout = contimeout)
      if ret >= 0:
        return ssh_port  # OK
      if ret == -1:
        ssh_port = 0
    portlist = []
    if ssh_port:
      portlist.append(ssh_port)
    if aux_port and aux_port != ssh_port:
      portlist.append(aux_port)
    plist = []
    for i, port in enumerate(portlist):
      ret = self.check_ssh(ip_addr, port, None, contimeout = contimeout)
      if ret == 0:
        plist.append(port)
    if not plist:
      if verbose >= 2:
        print("Can't found valid SSH server on IP {}".format(ip_addr))
      return -1
    if passw:
      pswlist = [ passw ]
      if passw != 'root':
        pswlist.append('root')
    else:
      pswlist = ['root', None]
    for p, psw in enumerate(pswlist):
      if psw is None:
        if not interactive:
          continue
        psw = input('Enter password for "root" user: ')
      for i, port in enumerate(plist):
        ret = self.check_ssh(ip_addr, port, psw, contimeout = contimeout)
        if ret >= 0:
          self.passw = psw
          self.ssh_port = port
          if verbose:
            print("Detect valid SSH server on port {} (auth OK)".format(port))
          return port
        if ret == -3 and passw and psw == passw:
          if verbose:
            print("Set SSH password = None")
          self.passw = None
          passw = None
    if verbose >= 2:
      print("Can't found valid SSH server on IP {}".format(ip_addr))
    return -2
  def detect_ssh(self, verbose = 1, interactive = True, contimeout = 2, aux_port = 0):
    ssh_port = self._detect_ssh(verbose, interactive, contimeout, aux_port)
    if ssh_port > 0:
      return ssh_port
    err = ssh_port
    telnet_en = self.check_telnet(timeout = contimeout, verbose = 0)
    if not telnet_en:
      return err
    passw = 'root'
    tn = self.get_telnet(verbose = 0, password = passw)
    if not tn and self.xqpassword:
      passw = self.xqpassword
      tn = self.get_telnet(verbose = 0, password = passw)
    if not tn:
      return err
    self.use_ssh = False
    self.passw = passw
    ftp_en = self.check_tcp_connect(self.ip_addr, 21, contimeout = 1)
    if ftp_en:
      self.use_ftp = True
    return 23
  def ssh_close(self):
    try:
      self.ssh.disconnect()
    except Exception:
      pass
    try:
      self.socket.close()
    except Exception:
      pass
    self.ssh = None
    self.socket = None
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
      contimeout = 1 if contimeout is None else contimeout
      start_time = datetime.datetime.now()
      while datetime.datetime.now() - start_time <= datetime.timedelta(seconds = contimeout):
        try:
          self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.socket.settimeout(0.5)
          self.socket.connect((self.ip_addr, self.ssh_port))
          break
        except Exception as e:
          self.socket = None
          pass
      if not self.socket:
        raise Exception('')
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
  def get_telnet(self, verbose = 0, password = None):
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
      if password is None:
        password = self.passw
      tn.write("{}\n".format(password).encode('ascii'))
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
      if self.use_ftp:
        ftp = self.get_ftp(verbose)
        if not ftp:
          return False
    return True
  def run_cmd(self, cmd, msg = None, timeout = None, die_on_error = True):
    ret = True
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
          ssh.set_timeout(100)
          ret = False
          if die_on_error:
            die("SSH execute command timed out! CMD: \"{}\"".format(cmd))
        if timeout is not None:
          ssh.set_timeout(saved_timeout)
        try:
          channel.close()
          channel.wait_closed()
        except Exception:
          pass
        #status = channel.get_exit_status()
        if not ret:
          break
      else:
        cmd += '\n'
        tn.write(cmd.encode('ascii'))
        tn.read_until(tn.prompt, timeout = 4 if timeout is None else timeout)
    if not self.use_ssh:
      tn.write(b"exit\n")
    return ret
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
    elif self.use_ftp:
      ftp = self.get_ftp(self.verbose)
      file = open(fn_local, 'wb')
      ftp.retrbinary('RETR ' + fn_remote, file.write)
      file.close()
    else:
      raise RuntimeError('FIXME')
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
    elif self.use_ftp:
      ftp = self.get_ftp(self.verbose)
      ftp.storbinary('STOR ' + fn_remote, file)
    else:
      raise RuntimeError('FIXME')
    file.close()
    return True
#===============================================================================
if __name__ == "__main__":
  if len(sys.argv) > 1:
    ip_addr = sys.argv[1]
    gw = Gateway(detect_device = False, detect_ssh = False)
    gw.ip_addr = ip_addr
    print("Device IP-address changed to {}".format(ip_addr))
    