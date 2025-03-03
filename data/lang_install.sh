#!/bin/sh

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/lang_backup

if [ `find /tmp -maxdepth 1 -name 'base.*.lmo' | wc -l` -eq 0 ]; then
	return 1
fi

if [ ! -d $DIR_PATCH ]; then
	mkdir -p $DIR_PATCH
	chown root $DIR_PATCH
	chmod 0755 $DIR_PATCH
fi

CLEAN_INSTALL=0
if [ ! -d $DIR_BACKUP ]; then
	CLEAN_INSTALL=1
	mkdir -p $DIR_BACKUP
	MAIN_LANG=`uci get luci.main.lang`
	echo "$MAIN_LANG" > $DIR_BACKUP/main_lang
fi

if [ $CLEAN_INSTALL = 1 ]; then
	NEED_RESTORE_MNT=0
	if mount | grep -q ' on /usr/lib/lua/luci' ; then
		umount -l /usr/lib/lua/luci
		NEED_RESTORE_MNT=1
	fi
	if [ -f /usr/lib/lua/luci/i18n/base.en.lmo ]; then
		# INT firmware may contain a file "base.en.lmo"
		echo "1" > $DIR_BACKUP/skip_base_en
	fi
	cp -f /usr/lib/lua/luci/view/web/inc/sysinfo.htm $DIR_BACKUP/
	cp -f /usr/lib/lua/luci/i18n/base.*.lmo $DIR_BACKUP/
	[ $NEED_RESTORE_MNT = 1 ] && mount --bind /tmp/_usr_lib_lua_luci /usr/lib/lua/luci
fi
if [ $CLEAN_INSTALL = 1 ]; then
	NEED_RESTORE_MNT=0
	if mount | grep -q ' on /usr/share/xiaoqiang' ; then
		umount -l /usr/share/xiaoqiang
		NEED_RESTORE_MNT=1
	fi
	if grep -q "option CHANNEL 'stable'" /usr/share/xiaoqiang/xiaoqiang_version ; then
		echo '1' > $DIR_BACKUP/fw_stable
	fi
	[ $NEED_RESTORE_MNT = 1 ] && mount --bind /tmp/_usr_share_xiaoqiang /usr/share/xiaoqiang
fi

if [ -f $DIR_BACKUP/skip_base_en ]; then
	# INT firmware may contain a file "base.en.lmo"
	rm -f /tmp/base.en.lmo
fi
mv -f /tmp/base.*.lmo $DIR_PATCH/
mv -f /tmp/lang_patch.sh $DIR_PATCH/
chmod +x $DIR_PATCH/lang_patch.sh

INSTALL_METHOD=2
if [ ! -e "/usr/lib/os-release" ]; then
	# older routers
	INSTALL_METHOD=0
fi

FILE_PATCHED=0

if [ $INSTALL_METHOD = 0 ]; then
	FILE_PATCHED=1
	FILE_FOR_EDIT=/etc/init.d/boot
	NEW_CMD="\[ -f \/etc\/crontabs\/patches\/lang_patch.sh \] && sh \/etc\/crontabs\/patches\/lang_patch.sh"
	HAVE_PATCH=$(grep '/lang_patch.sh' $FILE_FOR_EDIT)
	if [ -z "$HAVE_PATCH" ]; then
		FILE_PATCHED=0
		UCI_CFG=$(grep 'apply_uci_config' $FILE_FOR_EDIT)
		if [ -n "$UCI_CFG" ]; then
			sed -i "/apply_uci_config$/i$NEW_CMD" $FILE_FOR_EDIT
			FILE_PATCHED=2
		fi
		UCI_DEF=$(grep 'uci_apply_defaults' $FILE_FOR_EDIT)
		if [ -n "$UCI_DEF" -a $FILE_PATCHED == 0 ]; then
			sed -i "/uci_apply_defaults$/i$NEW_CMD" $FILE_FOR_EDIT
			FILE_PATCHED=3
		fi
	fi
fi

if [ $INSTALL_METHOD = 1 ]; then
	FILE_FOR_EDIT=/etc/crontabs/root
	grep -v "/lang_patch.sh" $FILE_FOR_EDIT > $FILE_FOR_EDIT.new
	echo "*/1 * * * * $DIR_PATCH/lang_patch.sh >/dev/null 2>&1" >> $FILE_FOR_EDIT.new
	mv $FILE_FOR_EDIT.new $FILE_FOR_EDIT
	/etc/init.d/cron restart
	FILE_PATCHED=10
fi

if [ $INSTALL_METHOD = 2 ]; then
	uci set firewall.auto_lang_patch=include
	uci set firewall.auto_lang_patch.type='script'
	uci set firewall.auto_lang_patch.path="$DIR_PATCH/lang_patch.sh"
	uci set firewall.auto_lang_patch.enabled='1'
	uci commit firewall
	FILE_PATCHED=20
fi

# set main lang
uci set luci.main.lang=en
#uci commit luci

# run patch
$DIR_PATCH/lang_patch.sh

