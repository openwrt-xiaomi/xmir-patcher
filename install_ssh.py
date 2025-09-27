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

# Check if SSH is already working properly
if [ -f "/tmp/ssh_patch.log" ]; then
	# Verify SSH is still enabled and running
	SSH_EN=`nvram get ssh_en`
	if [ "$SSH_EN" = "1" ] && pgrep dropbear >/dev/null 2>&1; then
		return 0
	fi
	# If verification fails, continue with patching
	rm -f /tmp/ssh_patch.log
fi

# Ensure nvram SSH setting is enabled
SSH_EN=`nvram get ssh_en`
if [ "$SSH_EN" != "1" ]; then
	nvram set ssh_en=1
	nvram commit
fi

# Patch dropbear init script to bypass release channel check
if grep -q '= "release"' /etc/init.d/dropbear ; then
	sed -i 's/= "release"/= "XXXXXX"/g'  /etc/init.d/dropbear
fi

# Additional hardening: ensure dropbear service is enabled and configured
/etc/init.d/dropbear enable

# Ensure dropbear is running - restart if necessary
if ! pgrep dropbear >/dev/null 2>&1; then
	/etc/init.d/dropbear start
else
	/etc/init.d/dropbear restart
fi

# Wait a moment for service to start
sleep 2

# Verify SSH is actually working
if pgrep dropbear >/dev/null 2>&1; then
	echo "ssh enabled - $(date)" > /tmp/ssh_patch.log
else
	echo "ssh patch failed - $(date)" > /tmp/ssh_patch.log
	exit 1
fi
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

# Set nvram settings
nvram set ssh_en=1
nvram commit

# Method 1: UCI firewall hook (primary method)
uci set firewall.auto_ssh_patch=include
uci set firewall.auto_ssh_patch.type='script'
uci set firewall.auto_ssh_patch.path="$DIR_PATCH/ssh_patch.sh"
uci set firewall.auto_ssh_patch.enabled='1'
uci commit firewall

# Method 2: Cron job as backup (runs every 5 minutes)
FILE_CRON=/etc/crontabs/root
if [ -f "$FILE_CRON" ]; then
	# Remove any existing ssh_patch entries
	grep -v "/ssh_patch.sh" $FILE_CRON > $FILE_CRON.new || echo "" > $FILE_CRON.new
	# Add new entry that runs every 5 minutes
	echo "*/5 * * * * $DIR_PATCH/ssh_patch.sh >/dev/null 2>&1" >> $FILE_CRON.new
	mv $FILE_CRON.new $FILE_CRON
	/etc/init.d/cron restart
fi

# Method 3: Create an additional init script as backup
INIT_SCRIPT=/etc/init.d/ssh_persistent
cat > $INIT_SCRIPT << 'EOF'
#!/bin/sh /etc/rc.common

START=19
STOP=89

start() {
	DIR_PATCH=/etc/crontabs/patches
	if [ -x "$DIR_PATCH/ssh_patch.sh" ]; then
		$DIR_PATCH/ssh_patch.sh &
	fi
}

stop() {
	return 0
}
EOF

chmod +x $INIT_SCRIPT
$INIT_SCRIPT enable

# Run the patch immediately
$DIR_PATCH/ssh_patch.sh

### bdata_patch ###
'''
with open(FN_install, 'w', newline = '\n') as file:
    file.write(ssh_install)
    
bdata_patch = '''
# Enhanced bdata persistence patch
rm -f /tmp/bdata_patch.log
echo "Starting bdata patch..." > /tmp/bdata_patch.debug

# Check current bdata settings
TELNET_EN=`bdata get telnet_en 2>/dev/null || echo ""`
SSH_EN=`bdata get ssh_en 2>/dev/null || echo ""`
UART_EN=`bdata get uart_en 2>/dev/null || echo ""`

echo "Current bdata: telnet_en=$TELNET_EN ssh_en=$SSH_EN uart_en=$UART_EN" >> /tmp/bdata_patch.debug

# Always attempt to patch bdata for maximum persistence - don't skip if already set
KMOD_FN=/tmp/xmir_patcher.ko
if [ -f $KMOD_FN ]; then
    echo "Loading xmir_patcher module..." >> /tmp/bdata_patch.debug
    insmod $KMOD_FN
    sleep 1
    
    if lsmod | grep -q xmir_patcher ; then
        echo "Module loaded successfully" >> /tmp/bdata_patch.debug
        
        # Try bdata partition name (lowercase)
        echo 'set_mtd_rw|bdata' > /sys/module/xmir_patcher/parameters/cmd
        RESP=`cat /sys/module/xmir_patcher/parameters/cmd`
        echo "bdata partition response: $RESP" >> /tmp/bdata_patch.debug
        
        # If lowercase fails, try Bdata (uppercase)
        if [ "${RESP::2}" != "0|" ]; then
            echo 'set_mtd_rw|Bdata' > /sys/module/xmir_patcher/parameters/cmd
            RESP=`cat /sys/module/xmir_patcher/parameters/cmd`
            echo "Bdata partition response: $RESP" >> /tmp/bdata_patch.debug
        fi
        
        if [ "${RESP::2}" = "0|" ]; then
            echo "Partition writable, setting bdata values..." >> /tmp/bdata_patch.debug
            
            # Set all required values
            bdata set telnet_en=1 2>&1 >> /tmp/bdata_patch.debug
            bdata set ssh_en=1 2>&1 >> /tmp/bdata_patch.debug
            bdata set uart_en=1 2>&1 >> /tmp/bdata_patch.debug
            
            # Commit changes
            if bdata commit 2>&1 >> /tmp/bdata_patch.debug ; then
                echo "OK" > /tmp/bdata_patch.log
                echo "bdata commit successful" >> /tmp/bdata_patch.debug
            else
                echo "error_commit" > /tmp/bdata_patch.log
                echo "bdata commit failed" >> /tmp/bdata_patch.debug
            fi
        else
            echo "error_partition_not_writable" > /tmp/bdata_patch.log
            echo "Failed to make partition writable" >> /tmp/bdata_patch.debug
        fi
        
        # Clean up module
        rmmod xmir_patcher 2>/dev/null
    else
        echo "error_module_load" > /tmp/bdata_patch.log
        echo "Failed to load xmir_patcher module" >> /tmp/bdata_patch.debug
    fi
else
    echo "error_module_missing" > /tmp/bdata_patch.log
    echo "xmir_patcher module file not found" >> /tmp/bdata_patch.debug
fi

# Verify final state
TELNET_EN_FINAL=`bdata get telnet_en 2>/dev/null || echo ""`
SSH_EN_FINAL=`bdata get ssh_en 2>/dev/null || echo ""`
UART_EN_FINAL=`bdata get uart_en 2>/dev/null || echo ""`
echo "Final bdata: telnet_en=$TELNET_EN_FINAL ssh_en=$SSH_EN_FINAL uart_en=$UART_EN_FINAL" >> /tmp/bdata_patch.debug
'''

ssh_uninstall = '''#!/bin/sh
DIR_PATCH=/etc/crontabs/patches

# Method 1: Remove cron job entries
if grep -q '/ssh_patch.sh' /etc/crontabs/root ; then
    # remove older version of patch
    grep -v "/ssh_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new
    mv /etc/crontabs/root.new /etc/crontabs/root
    /etc/init.d/cron restart
fi

# Method 2: Remove UCI firewall hook
if uci -q get firewall.auto_ssh_patch ; then
    uci delete firewall.auto_ssh_patch
    uci commit firewall
fi

# Method 3: Remove init script
INIT_SCRIPT=/etc/init.d/ssh_persistent
if [ -f "$INIT_SCRIPT" ]; then
    $INIT_SCRIPT disable
    $INIT_SCRIPT stop
    rm -f $INIT_SCRIPT
fi

# Clean up files
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
    
    # Check if we have the capability to apply bdata patch
    print(f'CPU arch: {dev.info.cpu_arch}')
    print(f'Kernel: {dev.info.linux_stamp}')
    krn_version = dev.info.linux_ver.strip()
    krn_ver = krn_version.split('.')
    kver = krn_ver[0] + '.' + krn_ver[1]
    arch = dev.info.cpu_arch
    
    if kver in [ '4.4', '5.4' ] and arch in [ 'armv7', 'arm64' ]:
        # Always try to apply bdata patch for maximum persistence
        # Even if values appear correct, they might not persist across firmware updates
        print(f'Applying bdata partition patch for enhanced persistence!')
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
    fn_bdata_debug = '/tmp/bdata_patch.debug'
    FN_bdata_debug = 'tmp/bdata_patch.debug'
    
    # Download both log and debug files
    gw.download(fn_bdata_log, FN_bdata_log, verbose = 0)
    gw.download(fn_bdata_debug, FN_bdata_debug, verbose = 0)
    
    if not os.path.exists(FN_bdata_log):
        print(f'WARN: Patch for bdata partition not executed!')
    else:
        with open(FN_bdata_log, 'r') as file:
            res = file.read().strip()
        print(f'Patch for bdata result: {res}')
        
        if res == 'OK':
            print('SUCCESS: bdata partition patched successfully - SSH should persist across reboots')
        else:
            print(f'WARNING: bdata patch failed with result: {res}')
            if os.path.exists(FN_bdata_debug):
                print('Debug information:')
                with open(FN_bdata_debug, 'r') as file:
                    debug_info = file.read()
                    print(debug_info)
            print('SSH may still work but persistence across firmware updates is not guaranteed')

print("SSH persistence mechanisms installed:")
print("1. UCI firewall hook (primary)")
print("2. Cron job backup (every 5 minutes)")  
print("3. Init script backup (on boot)")
print("Multiple redundant mechanisms ensure maximum persistence!")
