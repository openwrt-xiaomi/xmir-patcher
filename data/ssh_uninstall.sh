#!/bin/sh

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

