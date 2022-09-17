#!/bin/sh

if [ "$( grep 'ssh_patch.sh' /etc/crontabs/root )" != "" ]; then
	sh /tmp/ssh_uninstall.sh
fi

mv -f /tmp/ssh_patch.sh /etc/crontabs/
chmod +x /etc/crontabs/ssh_patch.sh

nvram set ssh_en=1
nvram commit

grep -v "/etc/crontabs/ssh_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new; 
echo "*/1 * * * * /etc/crontabs/ssh_patch.sh >/dev/null 2>&1" >> /etc/crontabs/root.new
mv /etc/crontabs/root.new /etc/crontabs/root
/etc/init.d/cron restart
