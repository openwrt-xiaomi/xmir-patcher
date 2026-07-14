#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import xmir_base
from gateway import *

gw = Gateway(detect_device=False, detect_ssh=False)
ip = gw.ip_addr

def check_port(port, label, timeout=3):
    try:
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False

print(f'\nChecking connection to {ip} ...\n')

web  = check_port(80,   'Web UI  (80)')
ssh  = check_port(22,   'SSH     (22)')
teln = check_port(23,   'Telnet  (23)')
dock = check_port(9001, 'SimpleDocker (9001)')

print(f'  Web UI        (80)  : {"OPEN  ✓" if web  else "closed"}')
print(f'  SSH           (22)  : {"OPEN  ✓" if ssh  else "closed"}')
print(f'  Telnet        (23)  : {"OPEN  ✓" if teln else "closed"}')
print(f'  SimpleDocker (9001) : {"OPEN  ✓" if dock else "closed"}')
print()

if ssh:
    print('SSH is available. You can connect with:')
    print(f'  ssh -o HostKeyAlgorithms=+ssh-rsa root@{ip}')
elif dock:
    print('SSH is closed but SimpleDocker is running.')
    print('Use option 2 to open SSH via SimpleDocker cgroup escape.')
else:
    print('No exploit entry point detected.')
    print('Make sure the USB drive with SimpleDocker is connected.')
print()
