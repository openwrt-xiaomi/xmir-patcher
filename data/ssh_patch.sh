#!/bin/sh

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
