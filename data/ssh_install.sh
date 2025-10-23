#!/bin/sh

DIR_PATCH=/etc/crontabs/patches

if [ ! -d $DIR_PATCH ]; then
	mkdir -p $DIR_PATCH
	chown root $DIR_PATCH
	chmod 0755 $DIR_PATCH
fi

mv -f /tmp/ssh_patch.sh $DIR_PATCH/
chmod +x $DIR_PATCH/ssh_patch.sh

# Set nvram settings
nvram set ssh_en=1
nvram commit

# Method 1: UCI firewall hook (primary method)
uci set firewall.auto_ssh_patch=include
uci set firewall.auto_ssh_patch.type='script'
uci set firewall.auto_ssh_patch.path="$DIR_PATCH/ssh_patch.sh"
uci set firewall.auto_ssh_patch.enabled='1'
uci commit firewall

# Method 2: Cron job as backup (runs every 5 minutes)
FILE_CRON=/etc/crontabs/root
if [ -f "$FILE_CRON" ]; then
	# Remove any existing ssh_patch entries
	grep -v "/ssh_patch.sh" $FILE_CRON > $FILE_CRON.new || echo "" > $FILE_CRON.new
	# Add new entry that runs every 5 minutes
	echo "*/5 * * * * $DIR_PATCH/ssh_patch.sh >/dev/null 2>&1" >> $FILE_CRON.new
	mv $FILE_CRON.new $FILE_CRON
	/etc/init.d/cron restart
fi

# Method 3: Create an additional init script as backup
INIT_SCRIPT=/etc/init.d/ssh_persistent
cat > $INIT_SCRIPT << 'EOF'
#!/bin/sh /etc/rc.common

START=19
STOP=89

start() {
	DIR_PATCH=/etc/crontabs/patches
	if [ -x "$DIR_PATCH/ssh_patch.sh" ]; then
		$DIR_PATCH/ssh_patch.sh &
	fi
}

stop() {
	return 0
}
EOF

chmod +x $INIT_SCRIPT
$INIT_SCRIPT enable

# Run the patch immediately
$DIR_PATCH/ssh_patch.sh
