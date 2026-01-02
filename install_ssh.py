#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time

import xmir_base
from gateway import *
import read_info

gw = Gateway()

FN_kmod      = 'kmod/xmir_patcher-{kver}-{arch}{preempt}.ko'
fn_kmod      = '/tmp/xmir_patcher.ko'
FN_patch     = f'tmp/ssh_patch.sh'
fn_patch     = '/tmp/ssh_patch.sh'
FN_install   = f'tmp/ssh_install.sh'
fn_install   = '/tmp/ssh_install.sh'
FN_uninstall = f'tmp/ssh_uninstall.sh'
fn_uninstall = '/tmp/ssh_uninstall.sh'

os.makedirs('tmp', exist_ok = True)

ssh_patch = '''#!/bin/sh
[ -e "/tmp/ssh_patch.log" ] && return 0

SSH_EN=`nvram get ssh_en`
if [ "$SSH_EN" != "1" ]; then
    nvram set ssh_en=1
    nvram commit
fi

if grep -q '= "release"' /etc/init.d/dropbear ; then
    sed -i 's/= "release"/= "XXXXXX"/g'  /etc/init.d/dropbear
fi

/etc/init.d/dropbear enable
/etc/init.d/dropbear restart

echo "ssh enabled" > /tmp/ssh_patch.log 
'''
with open(FN_patch, 'w', newline = '\n') as file:
    file.write(ssh_patch)

ssh_install = '''#!/bin/sh
DIR_PATCH=/etc/crontabs/patches

if [ ! -d $DIR_PATCH ]; then
    mkdir -p $DIR_PATCH
    chown root $DIR_PATCH
    chmod 0755 $DIR_PATCH
fi

mv -f /tmp/ssh_patch.sh $DIR_PATCH/
chmod +x $DIR_PATCH/ssh_patch.sh

nvram set ssh_en=1
nvram commit

uci set firewall.auto_ssh_patch=include
uci set firewall.auto_ssh_patch.type='script'
uci set firewall.auto_ssh_patch.path="$DIR_PATCH/ssh_patch.sh"
uci set firewall.auto_ssh_patch.enabled='1'
uci commit firewall

rm -f /tmp/ssh_patch.log
$DIR_PATCH/ssh_patch.sh

### bdata_patch ###
'''
with open(FN_install, 'w', newline = '\n') as file:
    file.write(ssh_install)
    
bdata_patch = '''
rm -f /tmp/bdata_patch.log
TELNET_EN=`bdata get telnet_en`
SSH_EN=`bdata get ssh_en`
UART_EN=`bdata get uart_en`
if [ "$TELNET_EN" != "1" -o "$SSH_EN" != "1" -o "$UART_EN" != "1" ]; then
    KMOD_FN=/tmp/xmir_patcher.ko
    if [ -f $KMOD_FN ]; then
        insmod $KMOD_FN
        if lsmod | grep -q xmir_patcher ; then
            echo 'set_mtd_rw|bdata' > /sys/module/xmir_patcher/parameters/cmd
            RESP=`cat /sys/module/xmir_patcher/parameters/cmd`
            if [ "${RESP::2}" != "0|" ]; then
                echo 'set_mtd_rw|Bdata' > /sys/module/xmir_patcher/parameters/cmd
                RESP=`cat /sys/module/xmir_patcher/parameters/cmd`
            fi
            if [ "${RESP::2}" = "0|" ]; then
                bdata set telnet_en=1
                bdata set ssh_en=1
                bdata set uart_en=1
                bdata commit
                echo OK > /tmp/bdata_patch.log
            fi
            [ ! -f /tmp/bdata_patch.log ] && echo error_3 > /tmp/bdata_patch.log
        fi
        [ ! -f /tmp/bdata_patch.log ] && echo error_2 > /tmp/bdata_patch.log
    fi
    [ ! -f /tmp/bdata_patch.log ] && echo error_1 > /tmp/bdata_patch.log
fi
'''

ssh_uninstall = '''#!/bin/sh
DIR_PATCH=/etc/crontabs/patches

if grep -q '/ssh_patch.sh' /etc/crontabs/root ; then
    # remove older version of patch
    grep -v "/ssh_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new
    mv /etc/crontabs/root.new /etc/crontabs/root
    /etc/init.d/cron restart
fi
if uci -q get firewall.auto_ssh_patch ; then
    uci delete firewall.auto_ssh_patch
    uci commit firewall
fi

rm -f $DIR_PATCH/ssh_patch.sh
rm -f /tmp/ssh_patch.log
'''
with open(FN_uninstall, 'w', newline = '\n') as file:
    file.write(ssh_uninstall)

# ---------------------------------------------------------------------------

FN_bdata_log = None
dev = read_info.DevInfo(gw, verbose = 0, infolevel = 1)
dev.get_env_list()
bdata = dev.env.bdata
if bdata and bdata.var:
    telnet_en = bdata.var["telnet_en"] if 'telnet_en' in bdata.var else None
    ssh_en = bdata.var["ssh_en"] if 'ssh_en' in bdata.var else None
    uart_en = bdata.var["uart_en"] if 'uart_en' in bdata.var else None    
    print(f'bdata: telnet_en = {telnet_en}, ssh_en = {ssh_en}, uart_en = {uart_en}')
    if telnet_en != '1' or ssh_en != '1' or uart_en != '1':
        print(f'CPU arch: {dev.info.cpu_arch}')
        print(f'Kernel: {dev.info.linux_stamp}')
        krn_version = dev.info.linux_ver.strip()
        krn_ver = krn_version.split('.')
        kver = krn_ver[0] + '.' + krn_ver[1]
        arch = dev.info.cpu_arch
        if kver in [ '4.4', '5.4' ] and arch in [ 'armv7', 'arm64' ]:
            print(f'Insert patch for bdata partition!')
            preempt = '-preempt' if 'PREEMPT' in dev.info.linux_stamp else ''
            FN_kmod = FN_kmod.format(kver = kver, arch = arch, preempt = preempt)
            if not os.path.exists(FN_kmod):
                die(f'File "{FN_kmod}" not found!')
            with open(FN_kmod, 'rb') as file:
                kmod = file.read()
            modmagic_pos = kmod.find(b'\x00vermagic=' + kver.encode())
            if modmagic_pos <= 0:
                die(f'Cannot found vermagic into file "{FN_kmod}"')
            modmagic_pos = kmod.find(kver.encode(), modmagic_pos)
            modmagic_end = kmod.find(b'\x00', modmagic_pos)
            if modmagic_end <= 0 or modmagic_end - modmagic_pos > 200:
                die(f'File "{FN_kmod}" contain incorrect vermagic (1)')
            modmagic = kmod[modmagic_pos:modmagic_end]
            fsp = modmagic.find(b' ')
            if fsp <= 0:
                die(f'File "{FN_kmod}" contain incorrect vermagic (2)')
            modmagic_ver = modmagic[0:fsp]
            modmagic_opt = modmagic[fsp:]
            if b'-XMiR-Patcher' not in modmagic_ver:
                die(f'File "{FN_kmod}" contain incorrect vermagic (3)')
            new_modmagic = krn_version.encode('latin1') + modmagic_opt
            xx = len(modmagic) - len(new_modmagic)
            new_modmagic += b'\x00' * xx
            kmod = kmod.replace(modmagic, new_modmagic)
            FN_kmod = 'tmp/xmir_patcher.ko'
            with open(FN_kmod, 'wb') as file:
                file.write(kmod)
            ssh_install = ssh_install.replace('### bdata_patch ###', bdata_patch)
            with open(FN_install, 'w', newline = '\n') as file:
                file.write(ssh_install)
            FN_bdata_log = f'tmp/bdata_patch.log'
            fn_bdata_log = '/tmp/bdata_patch.log'

# ---------------------------------------------------------------------------

action = 'install'
if len(sys.argv) > 1:
    if sys.argv[1].startswith('u') or sys.argv[1].startswith('r'):
        action = 'uninstall'

if action == 'install':
    if FN_bdata_log:
        gw.run_cmd(f"rm -f {fn_bdata_log}") 
        gw.upload(FN_kmod, fn_kmod)
    gw.upload(FN_patch, fn_patch)
    gw.upload(FN_install, fn_install)

gw.upload(FN_uninstall, fn_uninstall)

print("All files uploaded!")

print("Run scripts...")
run_script = fn_install if action == 'install' else fn_uninstall
gw.run_cmd(f"chmod +x {run_script} ; {run_script}", timeout = 17)

time.sleep(1.5)

gw.run_cmd(f"rm -f {fn_patch} ; rm -f {fn_install} ; rm -f {fn_uninstall}")

print("Ready! The Permanent SSH patch installed.")

if FN_bdata_log:
    gw.download(fn_bdata_log, FN_bdata_log, verbose = 0)
    if not os.path.exists(FN_bdata_log):
        print(f'WARN: Patch for bdata partition not executed!')
    else:
        with open(FN_bdata_log, 'r') as file:
            res = file.read()
        print(f'Patch for bdata result: {res}')
