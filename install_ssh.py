#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time

import xmir_base
from gateway import *

gw = Gateway()

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
'''
with open(FN_install, 'w', newline = '\n') as file:
    file.write(ssh_install)

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


action = 'install'
if len(sys.argv) > 1:
    if sys.argv[1].startswith('u') or sys.argv[1].startswith('r'):
        action = 'uninstall'

if action == 'install':
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
