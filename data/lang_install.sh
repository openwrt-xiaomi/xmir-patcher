if [ `ls /tmp/base.*.lmo |wc -l` -eq 0 ]; then
	return 1
fi

if [ "$(mount| grep '/usr/lib/lua/luci')" != "" ]; then
	sh /tmp/lang_uninstall.sh
fi

# delete old patch
rm -f /etc/rc.lang

# global firmware may contain a file "base.en.lmo"
[ -f /usr/lib/lua/luci/i18n/base.en.lmo ] && rm -f /tmp/base.en.lmo

mv -f /tmp/base.*.lmo /etc/
mv -f /tmp/lang_patch.sh /etc/
chmod +x /etc/lang_patch.sh

FILE_FOR_EDIT=/etc/init.d/boot
NEW_CMD="\[ -f \/etc\/lang_patch.sh \] && sh \/etc\/lang_patch.sh"
FILE_PATCHED=1
HAVE_PATCH=$(grep 'lang_patch.sh' $FILE_FOR_EDIT)
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

# run patch
sh /etc/lang_patch.sh

# delete lang
uci -q delete luci.languages.ru
uci -q delete luci.languages.en

# add lang
uci set luci.languages.ru=Русский
uci set luci.languages.en=English

# set main lang
uci set luci.main.lang=en

# commit luci settings
uci commit luci

# reload luci
luci-reload & rm -f /tmp/luci-indexcache & luci-reload
