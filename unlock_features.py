#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time

import xmir_base
from gateway import *

cwd = os.path.dirname(os.path.abspath(__file__))

gw = Gateway()

FN_lua       = f'tmp/XQFeatures.lua'
fn_lua       = '/tmp/XQFeatures.lua'
FN_patch     = f'tmp/unlockf_patch.sh'
fn_patch     = '/tmp/unlockf_patch.sh'
FN_install   = f'tmp/unlockf_install.sh'
fn_install   = '/tmp/unlockf_install.sh'
FN_uninstall = f'tmp/unlockf_uninstall.sh'
fn_uninstall = '/tmp/unlockf_uninstall.sh'

os.makedirs('tmp', exist_ok = True)

DEF_FEATURES = {
    "system": {
        "shutdown":               "0",
        "downloadlogs":           "0",
        "i18n":                   "0",
        "infileupload":           "1",
        "task":                   "0",
        "upnp":                   "1",
        "new_update":             "1",
        "multiwan":               "0", # def: 0   # misc.features.multiwan
        "support_1000_dhcp":      "1",
        "ipv6_wired":             "0",
        "ipv6_wired_v2":          "1",
        "plugin_install":         "0", # def: 0
        "GdprPrivacy":            "1",
        "international":          "1",
        "ipv6oversea":            "0",
        "set_router_location":    "0",
        "upgraded_light_color":   "1",
        "change_time":            "0", # def: 0
        "newRouterPwd":           "1",
        "https":                  "1",
        "ipv6_passthrough_relay": "1",
        "vpn_init":               "1",
        "mesh_bhtype_mode":       "0",
        "ipmaccheck":             "0",
        "map_e":                  "1",
        "dslite":                 "1",
        "map_e_ocn":              "1",
    },
    "wifi": {
        "wifi24":          "1",
        "wifi50":          "1",
        "wifiguest":       "1",
        "wifimerge":       "1",
        "wifi_mu_mimo":    "0",
        "twt":             "1",
        "mlo":             "1",
        "mlo_vap":         "1",
        "split5g":         "0",
        "silence_switch":  "0",
        "wifi_access_ctl": "0",    # misc.features.supportWifiAccessCtl # wifiaccess.cfg.enable
        "iot_dev":         "0",    # misc.features.iot_dev
        "easymesh_switch": "0",
    },
    "apmode": {
        "wifiapmode": "1",     # misc.features.supportWifiAp
        "lanapmode":  "1",
    },
    "netmode": {
        "elink":      "1",
        "net2.5G":    "0",
        "net10G":     "0",
    },
    "apps": {
        "apptc":             "0",
        "qos":               "1",
        "dhcpMsg":           "1",
        "upnp":              "1",
        "nfc":               "0",
        "wanLan":            "1",
        "mipctlv2":          "0",
        "lanPort":           "1",
        "xqdatacenter":      "1",
        "baidupan":          "0",
        "timemachine":       "0",
        "storage":           "0",
        "samba":             "0",
        "docker":            "0",
        "swapmask":          "3", # 0..7
        "ports_custom":      "1",
        "LED_control":       "1", # 0..7
        "firewall":          "0",
        "local_gw_security": "0",
        "download":          "0",
        "temp_control":      "0",
        "sec_center":        "0", # 0..2
        "sfp":               "0",
        "game_port":         "0", # def: 0   # misc.features.game   # misc.wireless.wl_if_count=3
        "lan_lag":           "1",
        "telnet":            "0",
    },
    "hardware": {
        "usb":        "0",
        "usb_deploy": "0",
        "disk":       "0",
    }
}

FEATURES = DEF_FEATURES.copy()
patched_features = { }

def patch_feature(node_name, fname, value, cfg_patch = None):
    FEATURES[node_name][fname] = value
    pname = f'{node_name}.{fname}'
    if pname not in patched_features:
        patched_features[pname] = [ ]
    if cfg_patch:
        patched_features[pname].extend(cfg_patch)

####################################################################################
# Edit me please
patch_feature('system', 'i18n', "1")
patch_feature('system', 'multiwan', "1", [ "misc.features.multiwan=1" ] )
patch_feature('system', 'plugin_install', "1")
patch_feature('system', 'change_time', "1")
patch_feature('wifi', 'wifi_access_ctl', "1", [ "misc.features.supportWifiAccessCtl=1", "wifiaccess.cfg.enable=1" ] )
# patch_feature('apps', 'game_port', "1", [ "misc.features.game=1" ] )
# patch_feature('apps', '__w3__', "1", [ "misc.wireless.wl_if_count=3" ] )
patch_feature('apps', 'baidupan', "1")
#
####################################################################################

lua_table = [ ]
lua_table.append('FEATURES = {')

def parse_feature(depth, elem_dict):
    prefix = '    ' * depth if depth >= 1 else ''
    for key, elem in elem_dict.items():
        if isinstance(elem, dict):
            lua_table.append(prefix + f'["{key}"] = ' + '{')
            parse_feature(depth + 1, elem)
        else:    
            if isinstance(elem, int) or isinstance(elem, float):
                value = f'{elem}'
            else:
                value = f'"{elem}"'
            lua_table.append(prefix + f'["{key}"] = {value},')
            if key == list(elem_dict)[-1]:
                lua_table.append(prefix + f'["__end__"] = "0"')
                prefix_new = '    ' * (depth - 1) if depth >= 2 else ''
                lua_table.append(prefix_new + '},')

parse_feature(1, FEATURES)
lua_table[-1] = '    }'
lua_table.append('}')

XQFeatures = '''#!/usr/bin/lua
module "xiaoqiang.XQFeatures"
'''
XQFeatures += '\n' + '\n'.join(lua_table) + '\n'
with open(FN_lua, 'w', newline = '\n') as file:
    file.write(XQFeatures)

unlockf_patch = '''#!/bin/sh
INST_FLAG_FN=/tmp/unlockf_patch.log

[ -e "$INST_FLAG_FN" ] && return 0

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/unlockf_backup

TARGET_DIR=/usr/lib/lua/xiaoqiang
MIRROR_DIR=/tmp/_usr_lib_lua_xiaoqiang
SYNCOBJECT=$MIRROR_DIR.sync

if [ ! -f $DIR_PATCH/XQFeatures.lua ; then
	return 0
fi

for i in $(seq 1 45); do
	mkdir $SYNCOBJECT &> /dev/null && break
	sleep 1
done
if ! mount | grep -q " on $TARGET_DIR" ; then
	mkdir -p $MIRROR_DIR
	cp -rf $TARGET_DIR/* $MIRROR_DIR/
	mount --bind $MIRROR_DIR $TARGET_DIR
fi

if [ ! -f $MIRROR_DIR/XQFeatures.lua ]; then
    rm -rf $SYNCOBJECT
    return 1  # error
fi

# replace XQFeatures.lua
cp -f $DIR_PATCH/XQFeatures.lua $MIRROR_DIR/XQFeatures.lua

rm -rf $SYNCOBJECT

### patch misc config ###

uci set misc.features.xmir_unlockf=1
uci commit misc

echo "unlockf enabled" > /tmp/unlockf_patch.log
'''
misc_patch = ''
for keyname, value in patched_features.items():
    vlist = value if isinstance(value, list) else [ value ]
    for val in vlist:
        if val:
            cfg_fn = val.split('.')[0]
            misc_patch += f'uci set {val}' + '\n'
            misc_patch += f'uci commit {cfg_fn}' + '\n'

unlockf_patch = unlockf_patch.replace('### patch misc config ###', misc_patch)

with open(FN_patch, 'w', newline = '\n') as file:
    file.write(unlockf_patch)

unlockf_install = '''#!/bin/sh
INST_FLAG_FN=/tmp/unlockf_patch.log

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/unlockf_backup

TARGET_DIR=/usr/lib/lua/xiaoqiang
MIRROR_DIR=/tmp/_usr_lib_lua_xiaoqiang
SYNCOBJECT=$MIRROR_DIR.sync

if [ ! -f /tmp/XQFeatures.lua ]; then
    return 1
fi

if [ ! -d $DIR_PATCH ]; then
    mkdir -p $DIR_PATCH
    chown root $DIR_PATCH
    chmod 0755 $DIR_PATCH
fi

CLEAN_INSTALL=0
if [ ! -d $DIR_BACKUP ]; then
    CLEAN_INSTALL=1
    mkdir -p $DIR_BACKUP
    if [ -f $DIR_BACKUP/misc ]; then
        cp -f /etc/config/misc $DIR_BACKUP/misc
    fi
fi
if [ $CLEAN_INSTALL = 1 ]; then
	NEED_RESTORE_MNT=0
	if mount | grep -q " on $TARGET_DIR" ; then
		umount -l $TARGET_DIR
		NEED_RESTORE_MNT=1
	fi
	if [ ! -f $DIR_BACKUP/XQFeatures.lua ]; then
        cp -f $TARGET_DIR/XQFeatures.lua $DIR_BACKUP/XQFeatures.lua
    fi
	[ $NEED_RESTORE_MNT = 1 ] && mount --bind $MIRROR_DIR $TARGET_DIR
fi 

mv -f /tmp/XQFeatures.lua $DIR_PATCH/
mv -f /tmp/unlockf_patch.sh $DIR_PATCH/
chmod +x $DIR_PATCH/unlockf_patch.sh

uci set firewall.auto_unlockf_patch=include
uci set firewall.auto_unlockf_patch.type='script'
uci set firewall.auto_unlockf_patch.path="$DIR_PATCH/unlockf_patch.sh"
uci set firewall.auto_unlockf_patch.enabled='1'
uci commit firewall

rm -f $INST_FLAG_FN

# run patch
$DIR_PATCH/unlockf_patch.sh

luci-reload
rm -f /tmp/luci-indexcache
luci-reload
'''
with open(FN_install, 'w', newline = '\n') as file:
    file.write(unlockf_install)

unlockf_uninstall = '''#!/bin/sh
INST_FLAG_FN=/tmp/unlockf_patch.log

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/unlockf_backup

TARGET_DIR=/usr/lib/lua/xiaoqiang
MIRROR_DIR=/tmp/_usr_lib_lua_xiaoqiang
SYNCOBJECT=$MIRROR_DIR.sync

if [ -d $DIR_BACKUP ]; then
    if [ -d $MIRROR_DIR ]; then
        cp -f $DIR_BACKUP/XQFeatures.lua $MIRROR_DIR/XQFeatures.lua
    fi
    cp -f $DIR_BACKUP/misc /etc/config/misc
fi

uci delete firewall.auto_unlockf_patch
uci commit firewall

rm -rf $DIR_BACKUP
rm -f $DIR_PATCH/unlockf_patch.sh
rm -f $DIR_PATCH/XQFeatures.lua
rm -f $INST_FLAG_FN
rm -rf $SYNCOBJECT

luci-reload
rm -f /tmp/luci-indexcache
luci-reload
'''
with open(FN_uninstall, 'w', newline = '\n') as file:
    file.write(unlockf_uninstall)

action = 'install'
if len(sys.argv) > 1:
    if sys.argv[1].startswith('u') or sys.argv[1].startswith('r'):
        action = 'uninstall'

if action == 'install':
    gw.upload(FN_lua, fn_lua)
    gw.upload(FN_patch, fn_patch)
    gw.upload(FN_install, fn_install)

gw.upload(FN_uninstall, fn_uninstall)

print("All files uploaded!")

print("Run scripts...")
run_script = fn_install if action == 'install' else fn_uninstall
gw.run_cmd(f"chmod +x {run_script} ; {run_script}", timeout = 17)

time.sleep(1.5)

gw.run_cmd(f"rm -f {fn_lua} ; rm -f {fn_patch} ; rm -f {fn_install} ; rm -f {fn_uninstall}")

print("Ready! The UnlockFeatures patch installed.")
