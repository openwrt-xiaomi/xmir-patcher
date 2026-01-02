#!/bin/sh

INST_FLAG_FN=/tmp/lang_patch.log

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/lang_backup

TARGET1_DIR=/usr/share/xiaoqiang
MIRROR1_DIR=/tmp/_usr_share_xiaoqiang
SYNCOBJECT1=$MIRROR1_DIR.sync

TARGET2_DIR=/usr/lib/lua/luci
MIRROR2_DIR=/tmp/_usr_lib_lua_luci
SYNCOBJECT2=$MIRROR2_DIR.sync

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
rm -f $INST_FLAG_FN
rm -f $SYNCOBJECT1
rm -f $SYNCOBJECT2

luci-reload
rm -f /tmp/luci-indexcache
luci-reload

