#!/bin/sh

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

INSTALL_METHOD=2

if [ $INSTALL_METHOD = 1 ]; then
	FILE_FOR_EDIT=/etc/crontabs/root
	grep -v "/ssh_patch.sh" $FILE_FOR_EDIT > $FILE_FOR_EDIT.new
	echo "*/1 * * * * /etc/crontabs/patches/ssh_patch.sh >/dev/null 2>&1" >> $FILE_FOR_EDIT.new
	mv $FILE_FOR_EDIT.new $FILE_FOR_EDIT
	/etc/init.d/cron restart
fi

if [ $INSTALL_METHOD = 2 ]; then
	uci set firewall.auto_ssh_patch=include
	uci set firewall.auto_ssh_patch.type='script'
	uci set firewall.auto_ssh_patch.path="$DIR_PATCH/ssh_patch.sh"
	uci set firewall.auto_ssh_patch.enabled='1'
	uci commit firewall
fi
