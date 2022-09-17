#!/bin/sh

if [ "$( grep 'ssh_patch.sh' /etc/crontabs/root )" != "" ]; then
	if [ -e "/tmp/ssh_uninstall.sh" ]; then
		sh /tmp/ssh_uninstall.sh
	fi
fi

if [ ! -d /etc/crontabs/patches/ ]; then
	mkdir /etc/crontabs/patches/
	chown root /etc/crontabs/patches/
	chmod 0755 /etc/crontabs/patches/
fi

mv -f /tmp/ssh_patch.sh /etc/crontabs/patches/
chmod +x /etc/crontabs/patches/ssh_patch.sh

nvram set ssh_en=1
nvram commit

grep -v "/ssh_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new
echo "*/1 * * * * /etc/crontabs/patches/ssh_patch.sh >/dev/null 2>&1" >> /etc/crontabs/root.new
mv /etc/crontabs/root.new /etc/crontabs/root
/etc/init.d/cron restart
