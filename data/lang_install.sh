#!/bin/sh

DIR_PATCH=/etc/crontabs/patches

if [ `ls /tmp/base.*.lmo |wc -l` -eq 0 ]; then
	return 1
fi

if [ "$(mount| grep '/usr/lib/lua/luci')" != "" ]; then
	if [ -e "/tmp/lang_uninstall.sh" ]; then
		sh /tmp/lang_uninstall.sh
	fi
fi

# delete old patch
rm -f /etc/rc.lang
rm -f /etc/lang_patch.sh

# global firmware may contain a file "base.en.lmo"
[ -f /usr/lib/lua/luci/i18n/base.en.lmo ] && rm -f /tmp/base.en.lmo

if [ ! -d $DIR_PATCH ]; then
	mkdir $DIR_PATCH
	chown root $DIR_PATCH
	chmod 0755 $DIR_PATCH
fi

mv -f /tmp/base.*.lmo $DIR_PATCH/
mv -f /tmp/lang_patch.sh $DIR_PATCH/
chmod +x $DIR_PATCH/lang_patch.sh
if [ -e "/tmp/lang_patch1.sh" ]; then
	mv -f /tmp/lang_patch1.sh $DIR_PATCH/
	chmod +x $DIR_PATCH/lang_patch1.sh
fi

INSTALL_METHOD=1
if [ -e "/usr/lib/os-release" ]; then
	INSTALL_METHOD=2
fi

FILE_PATCHED=0

if [ $INSTALL_METHOD == 1 ]; then
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

if [ $INSTALL_METHOD == 2 ]; then
	FILE_FOR_EDIT=/etc/crontabs/root
	grep -v "/lang_patch.sh" $FILE_FOR_EDIT > $FILE_FOR_EDIT.new
	echo "*/1 * * * * $DIR_PATCH/lang_patch.sh >/dev/null 2>&1" >> $FILE_FOR_EDIT.new
	mv $FILE_FOR_EDIT.new $FILE_FOR_EDIT
	/etc/init.d/cron restart
	FILE_PATCHED=4
fi

# set main lang
uci set luci.main.lang=en
#uci commit luci

# run patch
sh $DIR_PATCH/lang_patch.sh

