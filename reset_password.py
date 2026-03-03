#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to reset a forgotten root password (SSH/TELNET).
Attempts to connect via SSH (if password is saved in config) or via TELNET,
then sets a new password.

Usage:
  ./run.sh reset_password.py [new_password]
  ./run.sh reset_password.py --ip 192.168.31.1 new_password

Requirements:
  - The device must be on the same network
  - Either SSH (with known password) OR TELNET (usually password "root") must be accessible
"""

import sys
import time

import xmir_base
import gateway
from gateway import die


def reset_password_via_gateway(gw, new_passw):
    """Resets the password using an already connected gateway (SSH or TELNET)."""
    gw.run_cmd('echo -e "{new_passw}\\n{new_passw}" | passwd root'.format(new_passw=new_passw))
    time.sleep(0.5)
    if gw.use_ssh:
        gw.ssh_close()
    else:
        gw.shutdown()
    if gw.check_ssh(gw.ip_addr, gw.ssh_port, new_passw) != 0:
        die('Failed to verify the new password via SSH')
    gw.passw = new_passw
    print("Root password successfully changed.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--ip':
        if len(sys.argv) < 4:
            die("Usage: reset_password.py --ip <IP> <new_password>")
        ip_addr = sys.argv[2]
        new_passw = sys.argv[3]
    elif len(sys.argv) > 1:
        new_passw = sys.argv[1]
        ip_addr = None
    else:
        new_passw = input("Enter new password for root user: ")
        ip_addr = None

    new_passw = new_passw.strip()
    if len(new_passw) == 0:
        die('Password cannot be empty!')

    # Create gateway without automatic SSH detection
    gw = gateway.Gateway(detect_ssh=False)

    if ip_addr:
        gw.ip_addr = ip_addr
        print("Using IP: {}".format(ip_addr))

    if gw.status < 1:
        gw.detect_device()
    if gw.status < 1:
        die("Xiaomi device not found (IP: {})".format(gw.ip_addr))

    print("Device: {}".format(gw.device_name))
    print("IP: {}  SSH port: {}".format(gw.ip_addr, gw.ssh_port))

    # 1. Try SSH with saved password (if present in memcfg)
    if gw.passw:
        ret = gw.check_ssh(gw.ip_addr, gw.ssh_port, gw.passw)
        if ret >= 0:
            print("SSH connection with saved password — OK")
            gw.use_ssh = True
            reset_password_via_gateway(gw, new_passw)
            return

    # 2. Try TELNET (password is usually "root" after unlock)
    if not gw.check_telnet(timeout=3):
        die("Neither SSH (with known password) nor TELNET is accessible.\n"
            "Ensure TELNET is enabled on the device (telnet_en=1).")

    print("TELNET detected. Attempting to connect...")

    telnet_passwords = ['root']
    if gw.passw and gw.passw != 'root':
        telnet_passwords.insert(0, gw.passw)
    if gw.xqpassword and gw.xqpassword not in telnet_passwords:
        telnet_passwords.append(gw.xqpassword)

    tn = None
    used_passw = None
    for psw in telnet_passwords:
        tn = gw.get_telnet(verbose=0, password=psw)
        if tn:
            used_passw = psw
            break

    if not tn:
        die("Failed to connect via TELNET.\n"
            "Tried passwords: " + ", ".join(repr(p) for p in telnet_passwords) +
            "\nTry the default password: root")

    print("TELNET connection — OK (password: {})".format(repr(used_passw)))
    gw.use_ssh = False
    gw.passw = used_passw
    gw.ping(verbose=0)

    reset_password_via_gateway(gw, new_passw)


if __name__ == "__main__":
    main()