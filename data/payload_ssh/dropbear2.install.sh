#!/bin/sh

XDIR=/etc/crontabs/dropbearmulti

if [ ! -d /etc/dropbear ]; then
	mkdir -p /etc/dropbear
	chown root /etc/dropbear
	chmod 0700 /etc/dropbear
fi

kill -9 `pgrep dropbear` &>/dev/null
rm -f /etc/dropbear/dropbear_rsa_host_key
rm -f /etc/init.d/dropbear
rm -f /usr/sbin/dropbear

if [ ! -f /etc/config/dropbear ]; then
	cp -f $XDIR/uci.cfg /etc/config/dropbear
fi

cp -f $XDIR/init.d.sh /etc/init.d/dropbear
chmod +x /etc/init.d/dropbear

#rm -f /etc/rc.d/K??dropbear
#ln -s /etc/init.d/dropbear /etc/rc.d/K50dropbear &>/dev/null

#rm -f /etc/rc.d/S??dropbear
#ln -s /etc/init.d/dropbear /etc/rc.d/S19dropbear &>/dev/null

kill -9 `pgrep dropbear` &>/dev/null
/etc/init.d/dropbear enable
/etc/init.d/dropbear start
