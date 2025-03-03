#!/bin/sh

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/lang_backup

if [ -d $DIR_BACKUP ]; then
	if [ -f $DIR_BACKUP/fw_stable ]; then
		sed -i "s/option CHANNEL 'release'/option CHANNEL 'stable'/g" /usr/share/xiaoqiang/xiaoqiang_version
	fi
	if [ -f $DIR_BACKUP/main_lang ]; then
		MAIN_LANG=`cat $DIR_BACKUP/main_lang`
		uci set luci.main.lang="$MAIN_LANG"
		uci commit luci
	fi
	cp -f $DIR_BACKUP/base.*.lmo /usr/lib/lua/luci/i18n/
	cp -f $DIR_BACKUP/sysinfo.htm /usr/lib/lua/luci/view/web/inc/
fi

if grep -q '/lang_patch.sh' /etc/crontabs/root ; then
	# remove older version of patch
	grep -v "/lang_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new
	mv /etc/crontabs/root.new /etc/crontabs/root
	/etc/init.d/cron restart
fi
uci delete firewall.auto_lang_patch
uci commit firewall

rm -rf $DIR_BACKUP
rm -f $DIR_PATCH/lang_patch.sh
rm -f $DIR_PATCH/base.*.lmo
rm -f /tmp/lang_patch.log

luci-reload
rm -f /tmp/luci-indexcache
luci-reload

