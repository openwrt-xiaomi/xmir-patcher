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

cd /tmp
rm -f busybox_tiny
cat busybox_01 busybox_02 > busybox_tiny 
chmod +x busybox_tiny

# start telnet
./busybox_tiny telnetd

# start ftp
ln -s busybox_tiny ftpd
./busybox_tiny tcpsvd -vE 0.0.0.0 21 ./ftpd -Sw / >> /tmp/msg_ftpd 2>&1 &

#kill -9 `pgrep taskmonitor`
