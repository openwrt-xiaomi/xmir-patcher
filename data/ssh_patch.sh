#!/bin/sh

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
