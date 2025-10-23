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
import gzip
import base64
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


class ExploitFixed(Exception): pass

class ExploitError(Exception): pass

class ExploitNotWorked(Exception): pass


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


class Gateway():
  def __init_fields(self):
    self.use_ssh = True
    self.use_ftp = False
    self.verbose = 2
    self.con_timeout = 2
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
    self.web_scheme = 'http'
    self.stok = None    # HTTP session token
    self.status = -2
    self.errcode = -1
    self.ftp = None
    self.socket = None  # TCP socket for SSH 
    self.ssh = None     # SSH session
    self.login = 'root' # default username
    self.user_agent = "curl/8.4.0"
    self.last_resp_text = None
    self.hackCheck = None
  
  def __init__(self, timeout = 4, verbose = 2, detect_device = True, detect_ssh = True, load_cfg = True):
    random.seed()
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

  def api_request(self, path, params = None, resp = 'json', post = '', timeout = 4, stream = False, scheme = None):
    self.last_resp_code = 0
    self.last_resp_text = None
    headers = { }
    if post == 'raw' or post == 'bin':
        headers["Content-Type"] = "application/octet-stream"
    elif post == 'json':
        headers["Content-Type"] = "application/json"
    elif post:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    headers["User-Agent"] = self.user_agent
    web_scheme = scheme if scheme else self.web_scheme
    url = f"{web_scheme}://{self.ip_addr}/cgi-bin/luci/"
    if path.startswith('API/'):
        url += f';stok={self.stok}/api' + path[3:]
    else:
        url += path
    t_timeout = (self.con_timeout, timeout) if timeout is not None else (self.con_timeout, self.timeout)
    #print(f'{t_timeout=}')
    if post:
        response = requests.post(url,  data = params, stream = stream, headers = headers, timeout = t_timeout, verify = False)
    else:
        response = requests.get(url, params = params, stream = stream, headers = headers, timeout = t_timeout, verify = False)
    self.last_resp_code = response.status_code
    if resp and not stream:
        try:
            self.last_resp_text = response.text
        except Exception:
            pass
        if resp == 'text':
            return response.text
        if resp == 'TEXT':
            response.raise_for_status()
            return response.text
        if resp.lower() == 'json':
            if response.status_code == 500:  # Internal Server Error
                return None
            response.raise_for_status()
            try:
                dres = json.loads(response.text)
            except Exception:
                raise RuntimeError(f'Received incorrect JSON from "{path}" => {response.text}')
            return dres
    return response
    #return response.status_code, response.content

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
    web_scheme = None
    page = ''
    for scheme in [ 'http', 'https' ]:
        page = ''
        try:
            page = self.api_request('web', scheme = scheme, resp = 'TEXT', timeout = self.timeout)
            #with open("r0.txt", "wb") as file:
            #  file.write(page.encode("utf-8"))
        except requests.exceptions.ConnectionError as e:
            continue  # try other scheme
        except requests.exceptions.ConnectTimeout as e:
            continue  # try other scheme
        except requests.exceptions.HTTPError as e:
            print("Initial Request Http Error:", e)
        except requests.exceptions.Timeout as e:
            print("Initial Request Timeout Error:", e)
        except requests.exceptions.RequestException as e:
            print("Initial Request exception:", e)
        except Exception as e:      
            print("Initial Request Exception:", e)
        web_scheme = scheme
        break
    if not page:
        return -2
    if web_scheme:
        if web_scheme == 'https' and self.web_scheme != web_scheme:
            print('Switch to using Secure HTTP (HTTPS)')
        self.web_scheme = scheme
    try:
      hardware = re.findall(r'hardware = \'(.*?)\'', page)
      if hardware and len(hardware) > 0:
        self.device_name = hardware[0]
      else:
        hardware = re.findall(r'hardwareVersion: \'(.*?)\'', page)
        if hardware and len(hardware) > 0:
          self.device_name = hardware[0]
      self.device_name = self.device_name.upper()
      romver = re.search(r'romVersion: \'(.*?)\'', page)
      self.rom_version = romver.group(1).strip() if romver else None
      romchan = re.search(r'romChannel: \'(.*?)\'', page)
      self.rom_channel = romchan.group(1).strip().lower() if romchan else None
      mac_address = re.search(r'var deviceId = \'(.*?)\'', page)
      self.mac_address = mac_address.group(1) if mac_address else None
      nonce_key = re.search(r'key: \'(.*)\',', page)
      self.nonce_key = nonce_key.group(1) if nonce_key else None
    except Exception:
      pass
    if not self.device_name:
      die("You need to make the initial configuration in the WEB of the device!")
    self.model_id = self.get_modelid_by_name(self.device_name)
    self.status = -1
    x = page.find('a href="/cgi-bin/luci/web/init/hello')
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

  def web_ping(self, con_timeout, wait_timeout = 0):
    ret = True
    start_time = datetime.datetime.now()
    try:
      page = self.api_request('web', resp = 'TEXT', timeout = (con_timeout, 4))
      mac_address = re.search(r'var deviceId = \'(.*?)\'', page)
      self.mac_address = mac_address.group(1) if mac_address else None
      nonce_key = re.search(r'key: \'(.*)\',', page)
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

  def web_login(self, timeout = 4):
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
    data = f"username={username}&password={password}&logtype=2&nonce={nonce}"
    web_scheme = None
    code = None
    text = None
    for scheme in [ 'http', 'https' ]:
        text = None
        if scheme == 'http' and self.web_scheme == 'https':
            continue
        try:
            text = self.api_request('api/xqsystem/login', data, scheme = scheme, post = 'x-www-form', resp = 'text', timeout = timeout)
            if text and text.startswith('{'):
                dresp = json.loads(text)
                if 'code' in dresp:
                    code = int(dresp['code']) 
                    if code == 401:  # Invalid token
                        continue
        except requests.exceptions.ConnectionError as e:
            continue  # try other scheme
        except requests.exceptions.ConnectTimeout as e:
            continue  # try other scheme
        web_scheme = scheme
        break
    if not text:
        self.webpassword = ""
        die(f"Cannot get response for api/xqsystem/login! (encryptmode = {self.encryptmode})")
    if web_scheme:
        if web_scheme == 'https' and self.web_scheme != web_scheme:
            print('Switch to using Secure HTTP (HTTPS)')
        self.web_scheme = scheme
    try:
        stok = re.findall(r'"token":"(.*?)"', text)[0]
    except Exception:
        self.webpassword = ""
        die(f"WEB password is not correct! ERR={code} (encryptmode = {self.encryptmode})")
    self.webpassword = web_pass
    self.stok = stok
    return stok

  @property
  def apiurl(self):
    return "http://{ip_addr}/cgi-bin/luci/;stok={stok}/api/".format(ip_addr = self.ip_addr, stok = self.stok)

  def get_pub_info(self, api_name, timeout = 5):
    if '/' in api_name:
        path = api_name
    elif api_name in [ 'router_info', 'topo_graph' ]:
        path = f'api/misystem/{api_name}'
    else:
        path = f'api/xqsystem/{api_name}'
    return self.api_request(path, timeout = timeout)

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
    dres = self.api_request('API/misystem/sys_time')
    if not dres or dres['code'] != 0:
        raise RuntimeError(f'Error on get sys_time => {dres}')
    dst = dres['time']
    if fix_tz and 'timezone' in dst:
        if "'" in dst['timezone'] or ";" in dst['timezone']:
            dst['timezone'] = "GMT0"
    return dst

  def set_device_systime(self, dst, year = 0, month = 0, day = 0, hour = 0, min = 0, sec = 0, timezone = "", wait = True):
    if dst:
        year     = dst['year']
        month    = dst['month']
        day      = dst['day']
        hour     = dst['hour']
        min      = dst['min']
        sec      = dst['sec']
        timezone = dst['timezone']
    params = { 'time': f"{year}-{month}-{day} {hour}:{min}:{sec}", 'timezone': timezone }
    dres = self.api_request('API/misystem/set_sys_time', params, timeout = self.timeout)
    if not dres or dres['code'] != 0:
        raise RuntimeError(f'Error on exec command "set_sys_time" => {dres}')
    if wait:
        time.sleep(3.1) # because internal code exec: "echo 'ok,xiaoqiang' > /tmp/ntp.status; sleep 3; date -s \""..time.."\""
    return True

  def get_diag_paras(self, timeout = None):
    # http://192.168.31.1/cgi-bin/luci/;stok=14b996378966455753104d187c1150b4/api/xqnetwork/diag_get_paras
    # response: {"code":0,"signal_thr":"-60","usb_read_thr":0,"disk_write_thr":0,"disk_read_thr":0,"iperf_test_thr":"25","usb_write_thr":0}
    dres = self.api_request('API/xqnetwork/diag_get_paras', timeout = timeout)
    if not dres or dres['code'] != 0:
        raise RuntimeError(f'Error on get diag_get_paras => {dres}')
    return dres

  def get_diag_iperf_test_thr(self, timeout = None):
    resp = self.get_diag_paras(timeout = timeout)
    return str(resp['iperf_test_thr'])

  def set_diag_paras(self, iperf_test_thr=20, usb_read_thr=0, usb_write_thr=0, disk_read_thr=0, disk_write_thr=0, timeout=None):
    params = {
                'iperf_test_thr': str(iperf_test_thr),
                'usb_read_thr':   str(usb_read_thr),
                'usb_write_thr':  str(usb_write_thr),
                'disk_read_thr':  str(disk_read_thr),
                'disk_write_thr': str(disk_write_thr),
             }
    dres = self.api_request('API/xqnetwork/diag_set_paras', params, timeout = timeout)
    if not dres:
        err = f'Error on exec command "diag_set_paras" => {dres} (status:{self.last_resp_code})'
        if self.last_resp_code == 500:  # Internal Server Error
            raise EOFError(err)
        raise RuntimeError(err)
    return dres['code']  # 0 if OK

  def set_diag_iperf_test_thr(self, value, timeout = None):
    code = self.set_diag_paras(iperf_test_thr = value, timeout = timeout)
    return True if code == 0 else False

  hackCheck_skipKeys_v1 = [ "ssid", "pwd", "password", "username" ]

  hackCheck_skipKeys_v2 = [
    "name", "password", "password5g", "password5g2", "npassword", "pppoeName",
    "pppoePwd", "pwd", "pwd1", "pwd2", "pwd3", "newPwd", "service", "ssid", "ssid1", "ssid2", "ssid3",
    "ssid5g", "ssid5g2", "nssid", "nssid5G", "nssid5G2", "username", "apn", "pdp", "user", "passwd",
    "contact_phone", "phoneList", "msgtext", "acs_username", "acs_password", "conn_username", "conn_password",
  ]

  def detect_hackCheck(self, update = False):
    if not update and self.hackCheck is not None:
        return self.hackCheck
    self.hackCheck = 0
    self.set_diag_paras(iperf_test_thr = 25, usb_write_thr = 0, usb_read_thr = 0)
    try:
        code = self.set_diag_paras(iperf_test_thr = 25, usb_write_thr = 'simple_payload\n')
    except EOFError:  # Internal Server Error
        self.hackCheck = 3  # XQSecureUtil.filterChars = "[=[\n[`;|$&\n]]=]" ; return nil
        return self.hackCheck
    try:
        code = self.set_diag_paras(iperf_test_thr = 25, usb_write_thr = 'simple_payload;', usb_read_thr = 0)
    except EOFError:  # Internal Server Error
        self.hackCheck = 2  # XQSecureUtil.filterChars = "[`;|$&]" ; return nil
        return self.hackCheck
    code = self.set_diag_paras(iperf_test_thr = 'simple_payload;', usb_write_thr = 11, usb_read_thr = 22)
    if code != 0:
        raise RuntimeError(f'Error on exec command "diag_set_paras" => code:{code} (status:{self.last_resp_code})')
    diag_paras = self.get_diag_paras()
    #print(f'diag_paras: {diag_paras}')
    # restore def values
    self.set_diag_paras(iperf_test_thr = 25, usb_write_thr = 0, usb_read_thr = 0)
    if isinstance(diag_paras['iperf_test_thr'], int) and diag_paras['iperf_test_thr'] == 25:
        self.hackCheck = 1  # XQSecureUtil.filterChars = "[`;|$&]" ; return ''
        return self.hackCheck
    # hackCheck not detected
    return self.hackCheck

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
    api = 'API/xqsystem/reboot'
    try:
      text = self.api_request(api, { 'client': 'web' }, post = 'json', resp = 'text')
      if '"code":0' not in text:
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
      self.ftp.close()
    except Exception:
      pass
    self.ftp = None

  #===============================================================================
  def free_memcfg(self):
    if self.memcfg:
      if os.name != "nt":
        try:
          self.memcfg.unlink()
        except Exception:
          pass
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
    return self.get_config_param('device_ip_addr', '192.168.31.1').strip()

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
      if self.check_ftp(check_upload = True) == 0:
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
        die(f"TELNET not responding (IP: {self.ip_addr})")
    return False

  def get_telnet(self, verbose = 0, password = None):
    from telnetlib import NOP, IAC, SB, NAWS, SE
    try:
      tn = telnetlib.Telnet(self.ip_addr, timeout=4)
    except Exception as e:
      if verbose:
        die(f"TELNET not responding (IP: {self.ip_addr})")
      return None
    try:
      p_login = b'login: '
      p_passw = b'Password: '
      prompt = f"{self.login}@XiaoQiang:(.*?)# ".encode('ascii')
      idx, obj, output = tn.expect([p_login, prompt], timeout=2)
      if idx < 0:
        raise Exception('TELNET auth error (1)')
      tn.sock.sendall(IAC + SB + NAWS + b'\x03\xE8\x00\x20' + IAC + SE)
      if idx > 0:
        tn.prompt = obj.group()
        tn.write(b"echo 123 >/dev/null\n")
        tn.read_until(b'\r\n' + tn.prompt, timeout = 2)
        return tn
      tn.write(f"{self.login}\n".encode('ascii'))
      idx, obj, output = tn.expect([p_passw, prompt], timeout=2)
      if idx < 0:
        raise Exception('TELNET auth error (2)')
      if idx > 0:
        tn.prompt = obj.group()
        return tn
      if password is None:
        password = self.passw
      tn.write(f"{password}\n".encode('ascii'))
      idx, obj, output = tn.expect([prompt], timeout=2)
      if idx < 0:
        raise Exception('TELNET auth error (3)')
      tn.prompt = obj.group()
      return tn
    except Exception as e:
      #print(e)
      if verbose:
        die(f"Can't login to TELNET (IP: {self.ip_addr})")
    return None

  def check_ftp(self, check_upload = False, timeout = None):
    ret = -1
    if not timeout:
        timeout = self.timeout
    ftp = None
    try:
        ftp = ftplib.FTP(self.ip_addr, user=self.login, passwd=self.passw, timeout=timeout)
        ftp.voidcmd("NOOP")
        if check_upload:
            import io
            fp = io.BytesIO(b"HELLO_123")
            remote_fn = '/tmp/_test_payload.bin'
            ftp.storbinary(f'STOR {remote_fn}', fp)
            ftp.delete(remote_fn)
        ret = 0
    except ftplib.error_perm as e:
        ret = -3
        if '500 Unknown command' in str(e):
            ret = -11
    except ftplib.error_proto as e:
        ret = -2
        if 'unrecognized option: w' in str(e):
            ret = -10
    except Exception as e:
        ret = -1
    finally:
        if ftp:
            try:
                ftp.close()
            except Exception:
                pass        
    return ret

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

  def run_cmd(self, command, msg = None, timeout = None, die_on_error = True, reboot = False):
    error = 0
    reslist = [ ]
    self.errcode = -1
    if self.use_ssh:
        ssh = self.get_ssh(self.verbose)
    else:
        tn = self.get_telnet(self.verbose)
    if msg:
        print(msg)
    cmdlist = [ ]
    if isinstance(command, str):      
        cmdlist.append(command)
    else:
        cmdlist = command
    if not cmdlist:
        raise ValueError('Incorrect command list')
    if '\n' in ';'.join(cmdlist):
        raise ValueError('Incorrect command format (1)')
    for idx, cmd in enumerate(cmdlist):
        if self.use_ssh:
            channel = ssh.open_session()
            saved_timeout = ssh.get_timeout()
            if timeout is not None:
                ssh.set_timeout(int(timeout * 1000))
            #channel.pty('xterm')
            #print("exec = '{}'".format(cmd))
            try:
                channel.execute(cmd)
                channel.wait_eof()
            except ssh2.exceptions.Timeout:
                error = -4
            except ssh2.exceptions.SocketRecvError as e:
                error = -5
            except Exception as e:
                error = -10
            finally:
                if reboot:
                    self.shutdown()
                    self.errcode = 0
                    return ''
                channel.close()
                channel.wait_closed()
            if error != 0 and die_on_error:
                die(f'SSH: execute command ERR={error}, CMD: "{cmd}"')
            if error == 0:
                self.errcode = channel.get_exit_status()
                res = b''
                size = 1
                while size > 0:
                    size, data = channel.read()
                    if data:
                        res += data
                res = res.decode('latin1')
                reslist.append(res if res != '\n' else '')
            else:
                self.errcode = -2
                reslist.append(None)
            ssh.set_timeout(saved_timeout)
        else: # telnet
            end = b'echo -e "\\xA6$?\\xA7\\xB8_END"'
            try:
                tn.write(cmd.encode('latin1') + b'\n' + end + b'\n')
                res = tn.read_until(b'\xA7\xB8_END\r\n' + tn.prompt, timeout = 4 if timeout is None else timeout)
                p1 = res.find(b'\r\n')
                p2 = res.rfind(b'\r\n' + tn.prompt + end)
                p3 = res.rfind(b'\r\n\xA6')
                p4 = res.rfind(b'\xA7\xB8_END')
                if p1 < 0 or p2 < 0 or p3 < 0 or p4 < 0 or p3 >= p4:
                    if die_on_error:
                        die('TELNET: execute command: incorrect response (1)')
                    reslist.append(None)
                    self.errcode = -2
                else:
                    self.errcode = int(res[p3+3:p4].decode(), 10)
                    res = res[p1+2:p2].decode('latin1')
                    res = res.replace('\r\n', '\n')
                    reslist.append(res if res != '\n' else '')
            except Exception as e:
                error = -4
                if die_on_error:
                    die(f'TELNET: execute command error: "{e}"')
        if error != 0:
            break
    if not self.use_ssh: # telnet
        try:
            tn.write(b"exit\n")
            tn.close()
        except Exception:
            pass
    if error == 0:
        return reslist if isinstance(command, list) else reslist[0]
    else:
        return None

  def download(self, fn_remote, fn_local, verbose = 1):
    if verbose and self.verbose:
        print(f'Download file: "{fn_remote}" ....')
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
        channel.send_eof()
        channel.wait_eof()
        channel.wait_closed()
    elif self.use_ftp:
        ftp = self.get_ftp(self.verbose)
        with open(fn_local, 'wb') as file:
            ftp.retrbinary('RETR ' + fn_remote, file.write)
    else: # telnet
        os.remove(fn_local) if os.path.exists(fn_local) else None
        size = self.get_remote_file_size(fn_remote)
        if size < 0:
            return False
        if size == 0:
            with open(fn_local, 'wb') as file:
                pass
            return True
        tn = self.get_telnet(self.verbose)
        fin = b" ; echo 'X''_FIN_''X'"
        blksize = 64*1000
        filesize = 0
        with open(fn_local, 'wb') as file:
            while filesize < size:
                count = blksize
                if filesize + count > size:
                    count = size - filesize
                cmd = f"dd if='{fn_remote}' iflag=skip_bytes,count_bytes skip={filesize} count={count} 2>/dev/null | base64"
                tn.write(cmd.encode('latin1') + fin + b'\n')
                res = tn.read_until(b'X_FIN_X\r\n' + tn.prompt, timeout = 4)
                p1 = res.find(b'\r\n')
                p2 = res.rfind(b'X_FIN_X\r\n')
                if p1 < 0 or p2 < 0 or p1 >= p2:
                    break
                data = base64.standard_b64decode(res[p1+2:p2].replace(b'\r\n', b''))
                filesize += len(data)
                file.write(data)
        try:
            tn.write(b"exit\n")
            tn.close()
        except Exception:
            pass
        if filesize != size:
            os.remove(fn_local) if os.path.exists(fn_local) else None
            return False
    return True

  def upload(self, fn_local, fn_remote, md5chk = True, verbose = 1):
    if not os.path.exists(fn_local):
        die(f'File "{fn_local}" not found.')
    if md5chk:
        md5_local = self.get_md5_for_local_file(fn_local)
    if verbose and self.verbose:
        print(f'Upload file: "{fn_local}" ....')
    if self.use_ssh:
        ssh = self.get_ssh(self.verbose)
        finfo = os.stat(fn_local)
        channel = ssh.scp_send64(fn_remote, finfo.st_mode & 0o777, finfo.st_size, finfo.st_mtime, finfo.st_atime)
        size = 0
        with open(fn_local, 'rb') as file:
            for data in file:
                channel.write(data)
                size = size + len(data)
        channel.send_eof()
        channel.wait_eof()
        channel.wait_closed()
        #except ssh2.exceptions.SCPProtocolError as e:
    elif self.use_ftp:
        ftp = self.get_ftp(self.verbose)
        with open(fn_local, 'rb') as file:
            ftp.storbinary('STOR ' + fn_remote, file)
    else: # telnet
        with open(fn_local, 'rb') as file:
            data = file.read()
        data = gzip.compress(data, compresslevel = 9)
        data = base64.standard_b64encode(data)
        fn_remote_tmp = '/tmp/_T_' + os.path.basename(fn_remote)
        if len(fn_remote_tmp) > 80:
            raise ValueError('Incorrect length of filename')
        self.run_cmd(f"rm -f '{fn_remote_tmp}'")
        tn = self.get_telnet(self.verbose)
        filesize = 0
        while filesize < len(data):
            chunk = data[filesize:filesize+400]
            if len(chunk) > 0:
                fopt = b'>' if filesize == 0 else b'>>'
                cmd = b"echo -n " + chunk + fopt + fn_remote_tmp.encode()
                tn.write(cmd + b'\n')
                res = tn.read_until(b'\r\n' + tn.prompt, timeout = 4)
                p1 = res.find(b'echo -n ')
                p2 = res.rfind(b'\r\n' + tn.prompt)
                if p1 < 0 or p2 < 0 or p1 >= p2 or p2 - p1 != len(cmd):
                    break
            filesize += len(chunk)
        try:
            tn.write(b"exit\n")
            tn.close()
        except Exception:
            pass
        if filesize != len(data):
            self.run_cmd(f"rm -f '{fn_remote_tmp}'")
            return False
        self.run_cmd(f"rm -f '{fn_remote}' ; cat '{fn_remote_tmp}' | base64 -d | gzip -d > '{fn_remote}'")
        self.run_cmd(f"rm -f '{fn_remote_tmp}'")
    if md5chk:
        md5_remote = self.get_md5_for_remote_file(fn_remote)
        if md5_remote != md5_local:
            if md5chk == 2:
                die(f'File "{fn_local}" uploaded, but MD5 incorrect!')
            #if verbose:
            print(f'ERROR: File "{fn_local}" uploaded, but MD5 incorrect!')
            return False
    return True

  def get_remote_file_size(self, fn_remote):
    size = self.run_cmd(f"wc -c '{fn_remote}' 2>&1")
    if not size:
        return -1
    size = size.strip()
    if size.startswith('wc:'):
        return -2  # file not found
    if len(size) < 3 or ' ' not in size:
        return -3
    size = size.split(' ')[0]
    return int(size, 10)

  def get_md5_for_remote_file(self, fn_remote, timeout = 8):
    md5 = self.run_cmd(f"md5sum '{fn_remote}' 2>&1", timeout = timeout)
    if not md5:
        return -1
    md5 = md5.strip()
    if md5.startswith('md5sum:'):
        return -2  # file not found
    if len(md5) < 32:
        return -3
    md5 = md5[:32]
    return md5.lower()
  
  def get_md5_for_local_file(self, fn_local, size = None):
    hasher = hashlib.md5()
    bs = 512*1024
    if size is None:
        with open(fn_local, 'rb') as file:
            for chunk in iter(lambda: file.read(bs), b''):
                hasher.update(chunk)
    elif size > 0:
        tail_size = 0
        nsize = size
        filesize = os.path.getsize(fn_local)
        if size > filesize:
            tail_size = size - filesize
            nsize = filesize
        readed = 0
        with open(fn_local, 'rb') as file:
            while True:
                if readed + bs > nsize:
                    bs = nsize - readed
                chunk = file.read(bs)
                hasher.update(chunk)
                readed += bs
                if readed >= nsize:
                    break
        if tail_size:
            hasher.update(b'\0' * tail_size)
    return hasher.hexdigest()

  def post_connect(self, exec_cmd, contimeout = 20, passw = 'root'):
    telnet_en = False
    self.use_ssh = True
    if passw is not None:
        self.passw = passw
    ssh_en = self.ping(verbose = 0, contimeout = contimeout)  # RSA host key generate slowly!
    if ssh_en:
        print('#### SSH server are activated! ####')
    else:
        print(f"WARNING: SSH server not responding (IP: {self.ip_addr})")

    if not ssh_en:
        print("")
        exec_cmd("bdata set telnet_en=1 ; bdata commit")
        print('Run TelNet server on port 23 ...')
        exec_cmd("/etc/init.d/telnet enable ; /etc/init.d/telnet restart")
        time.sleep(0.5)
        self.use_ssh = False
        telnet_en = self.ping(verbose = 2)
        if not telnet_en:
            # FIXME
            print(f"ERROR: TelNet server not responding (IP: {self.ip_addr})")
            return -2
        print('#### TelNet server are activated! ####')

    if ssh_en or telnet_en:
        self.run_cmd('nvram set uart_en=1; nvram set boot_wait=on; nvram commit')
        self.run_cmd('nvram set bootdelay=3; nvram set bootmenu_delay=5; nvram commit')

    if ssh_en:
        return 0

    if telnet_en:
        self.install_dropbearmulti(force = True, die_on_error = True)
        return 0

    return -1
   
  def install_dropbearmulti(self, force = True, die_on_error = False):
    rc, msg = self._install_dropbearmulti(force = force)
    if rc and die_on_error:
        die(msg)
    return rc, msg
    
  def _install_dropbearmulti(self, force = True):
    if True:
        arch = self.run_cmd("cat /etc/openwrt_release | grep DISTRIB_ARCH=")
        if not arch:
            return 10, 'TELNET: Cannot read remote file /etc/openwrt_release'
        pos = arch.find("DISTRIB_ARCH='")
        if pos < 0:
            return 20, 'TELNET: Cannot detect arch for remote device'
        arch = arch[pos+1:].split("'")[1]
        print(f'ARCH = {arch}')
        arch_suffix = None
        if arch.startswith('arm_'):
            arch_suffix = '_armv7a' if 'neon-vfp' in arch else '_armv5'
        if arch.startswith('aarch64'):
            arch_suffix = '_arm64'
        if arch.startswith('mips'):
            arch_suffix = '_mips'
        if not arch_suffix:
            return 30, f'TELNET: Unknown arch = "{arch}"'
        self.run_cmd(r'echo -e "root\nroot" | passwd root')
        self.run_cmd(r'kill -9 `pgrep dropbearmulti` &>/dev/null')
        fn_local = f'data/payload_ssh/dropbearmulti{arch_suffix}'
        fn_remote = '/tmp/dropbearmulti'
        md5_local = self.get_md5_for_local_file(fn_local)
        if not(md5_local) or isinstance(md5_local, int) or len(md5_local) != 32:
            return 40, f'File "{fn_local}" not found'
        md5 = self.get_md5_for_remote_file(fn_remote)
        if md5 != md5_local:
            if not self.upload(fn_local, fn_remote):
                return 50, f'TELNET: Cannot upload file "{fn_local}" to device'
        self.run_cmd('chmod +x /tmp/dropbearmulti')
        self.run_cmd('[ -d /etc/dropbear ] || { mkdir -p /etc/dropbear ; chown root /etc/dropbear ; chmod 0755 /etc/dropbear; }')
        if False:
            # generate host keys
            fn = '/etc/dropbear/dropbear_ed25519_host_key'
            fsize = self.get_remote_file_size(fn)
            if not fsize or fsize <= 0:
                self.run_cmd(f'rm -f {fn} ; /tmp/dropbearmulti dropbearkey -t ed25519 -f {fn} 2>&- >&-', timeout = 11)
            fn = '/etc/dropbear/dropbear_ecdsa_host_key'
            fsize = self.get_remote_file_size(fn)
            if not fsize or fsize <= 0:
                self.run_cmd(f'rm -f {fn} ; /tmp/dropbearmulti dropbearkey -t ecdsa -f {fn} 2>&- >&-', timeout = 11)
            # run dropbearmulti
            self.run_cmd('/tmp/dropbearmulti -p 122')
            pass
        print(f'Install XMiR-SSH ...')
        xdir = '/etc/crontabs/dropbearmulti'
        fn_bin = '/usr/sbin/dropbear'
        fn_BIN = f'{xdir}/dropbear'
        fn_conf = '/etc/config/dropbear'
        fn_CONF = f'{xdir}/uci.cfg'
        fn_initd = '/etc/init.d/dropbear'
        fn_INITD = f'{xdir}/init.d.sh'
        fn_INSTALL = f'{xdir}/install.sh'
        fsize_bin = self.get_remote_file_size(fn_bin)
        fsize_initd = self.get_remote_file_size(fn_initd)
        if fsize_bin and fsize_initd and fsize_bin > 0 and fsize_initd > 0:
            msg = 'SSH: dropbear is found, but it cannot run!'
            if not force:
                return 60, msg
        # install XMiR dropbear
        self.run_cmd(f'kill -9 `pgrep dropbear` &>/dev/null')
        #self.run_cmd(f'rm -f {fn_bin} &>/dev/null')
        self.run_cmd(f'rm -f {fn_conf} &>/dev/null')
        self.run_cmd(f'mkdir -p {xdir}')
        self.run_cmd(f'cp -f /tmp/dropbearmulti {fn_BIN}')
        self.run_cmd(f'chmod +x {fn_BIN}')
        if not self.upload('data/payload_ssh/dropbear.uci.cfg', fn_CONF):
            return 70, f'TELNET: Cannot upload file "{fn_CONF}" to device'
        if not self.upload('data/payload_ssh/dropbear2.init.d.sh', fn_INITD):
            return 73, f'TELNET: Cannot upload file "{fn_INITD}" to device'
        if not self.upload('data/payload_ssh/dropbear2.install.sh', fn_INSTALL):
            return 76, f'TELNET: Cannot upload file "{fn_INSTALL}" to device'
        uci = [ "uci set firewall.dropbearmulti=include",
                "uci set firewall.dropbearmulti.type='script'",
               f"uci set firewall.dropbearmulti.path='{fn_INSTALL}'",
                "uci set firewall.dropbearmulti.enabled='1'",
                "uci commit firewall",
              ]
        self.run_cmd(';'.join(uci))
        self.run_cmd(f'chmod +x {fn_INITD} ; chmod +x {fn_INSTALL}')
        print(f'Run XMiR-SSH ...')
        self.run_cmd(f'{fn_INSTALL}', timeout = 20)
        self.use_ssh = True
        ssh_en = self.ping(verbose = 0, contimeout = 8)
        if ssh_en:
            print('#### XMiR-SSH server are activated! ####')
            return 0, ''
        return 90, f"installed XMiR-SSH server not responding (IP: {self.ip_addr})"
    return 1, 'unknown error'


#===============================================================================

def import_module(mod_name, gw):
    import importlib.util
    mod_spec = importlib.util.spec_from_file_location(mod_name, f"{mod_name}.py")
    mod_object = importlib.util.module_from_spec(mod_spec)
    sys.modules[mod_name] = mod_object
    if gw is not None:
        mod_object.inited_gw = gw
    mod_spec.loader.exec_module(mod_object)

def create_gateway(timeout = 4, die_if_sshOk = True, die_if_ftpOk = True, web_login = True, ssh_port = 22, try_telnet = False):
    gw = Gateway(timeout = timeout, detect_ssh = False)
    if gw.status < 1:
        die(f"Xiaomi Mi Wi-Fi device not found (IP: {gw.ip_addr})")
    print(f"device_name = {gw.device_name}")
    print(f"rom_version = {gw.rom_version} {gw.rom_channel}")
    print(f"mac_address = {gw.mac_address}")
    gw.ssh_port = ssh_port if ssh_port else 22
    ret = gw.detect_ssh(verbose = 1, interactive = True)
    while ret == 23:
        ret = 0
        if not try_telnet:
            break
        print(f'Detected running TELNET server. Try to start SSH server...')
        if gw.passw and gw.passw != 'root':
            print('Default TELNET password =', gw.passw)
        gw.shutdown()
        tn = gw.get_telnet(verbose = 0, password = gw.passw)
        if not tn:
            print(f'WARNING: Cannot connect to TELNET server')
            break
        gw.use_ssh = False
        gw.run_cmd(r"sed -i 's/release/XXXXXX/g' /etc/init.d/dropbear")
        gw.run_cmd(r"nvram set ssh_en=1 ; nvram set boot_wait=on ; nvram set bootdelay=3 ; nvram commit")
        gw.run_cmd(r"echo -e 'root\nroot' | passwd root", die_on_error = False)
        gw.shutdown()
        time.sleep(1)
        gw.passw = 'root'
        print(f'Use new password for root user = "{gw.passw}"')
        tn = gw.get_telnet(verbose = 0, password = gw.passw)
        if not tn:
            print(f'WARNING: Cannot connect to TelNet server')
            break
        gw.shutdown()
        gw.run_cmd(r"/etc/init.d/dropbear enable; /etc/init.d/dropbear restart")
        time.sleep(1)
        ret = gw._detect_ssh(verbose = 1, interactive = True)
        if ret > 0:
            break # Ok
        print(f'Cannot start stock SSH server. Try to start XMiR-SSH server...')
        rc, msg = gw.install_dropbearmulti(force = True)
        if rc != 0:
            print('ERROR:', msg)
            break
        ret = gw._detect_ssh(verbose = 1, interactive = True)
        if ret <= 0:
            print('ERROR: installed XMiR-SSH server not responding!')
        break
    if ret > 0:
        if die_if_sshOk:
            die(0, f"SSH server already installed and running (port = {ret})")
    ccode = gw.device_info["countrycode"]
    print(f'CountryCode = {ccode}')
    if web_login:
        if isinstance(web_login, str):
            gw.webpassword = web_login
        gw.web_login()
    return gw

#===============================================================================
if __name__ == "__main__":
  if len(sys.argv) > 1:
    ip_addr = sys.argv[1]
    gw = Gateway(detect_device = False, detect_ssh = False)
    gw.ip_addr = ip_addr
    print("Device IP-address changed to {}".format(ip_addr))
    
