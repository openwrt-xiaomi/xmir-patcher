#!/bin/sh

DIR_PATCH=/etc/crontabs/patches

if [ "$( grep 'ssh_patch.sh' /etc/crontabs/root )" != "" ]; then
	if [ -e "/tmp/ssh_uninstall.sh" ]; then
		sh /tmp/ssh_uninstall.sh
	fi
fi

if [ ! -d $DIR_PATCH ]; then
	mkdir $DIR_PATCH
	chown root $DIR_PATCH
	chmod 0755 $DIR_PATCH
fi

mv -f /tmp/ssh_patch.sh $DIR_PATCH/
chmod +x $DIR_PATCH/ssh_patch.sh

nvram set ssh_en=1
nvram commit

grep -v "/ssh_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new
echo "*/1 * * * * /etc/crontabs/patches/ssh_patch.sh >/dev/null 2>&1" >> /etc/crontabs/root.new
mv /etc/crontabs/root.new /etc/crontabs/root
/etc/init.d/cron restart
