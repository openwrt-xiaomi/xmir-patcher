# enable UART
nvram set bootdelay=5; nvram set uart_en=1; nvram commit

# change password for root
echo -e "root\nroot" | (passwd root) 

if [ -f /etc/init.d/dropbear ]; then
	# unlock autostart dropbear
	sed -i 's/"$flg_ssh" != "1" -o "$channel" = "release"/-n ""/g' /etc/init.d/dropbear
	if [ -f /usr/sbin/dropbear ]; then
		# restart dropbear
		/etc/init.d/dropbear stop
		/etc/init.d/dropbear start
	fi
fi

kill -9 `pgrep dropbearmulti`

cd /tmp
rm -f dropbearmulti
cat dropbearmulti_01 dropbearmulti_02 dropbearmulti_03 > dropbearmulti
chmod +x dropbearmulti

# start SSH server
./dropbearmulti -p 122

#kill -9 `pgrep taskmonitor`

# install dropbear for release firmware (not devel)
if [ ! -f /usr/sbin/dropbear ]; then
	if [ -f /etc/init.d/dropbear ]; then
		# stop dropbear
		/etc/init.d/dropbear stop
	fi
	rm -f /etc/dropbear/dropbear
	cp -f dropbearmulti /etc/dropbear/dropbear
	chmod +x /etc/dropbear/dropbear
	if [ -f /etc/init.d/dropbear ]; then
		sed -i 's/PROG=\/usr\/sbin\/dropbear/PROG=\/etc\/dropbear\/dropbear/g' /etc/init.d/dropbear
		# start dropbear
		/etc/init.d/dropbear start
	fi
fi
