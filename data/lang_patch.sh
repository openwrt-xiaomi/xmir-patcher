#!/bin/sh

[ -e "/tmp/lang_patch.log" ] && return 0

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/lang_backup
SYNC_OBJ=/tmp/_patch_sync

if [ `find $DIR_PATCH -maxdepth 1 -name 'base.*.lmo' | wc -l` -eq 0 ]; then
	return 0
fi

while true; do
	STATE=`mkdir $SYNC_OBJ 2>&1`
	if [[ "$STATE" != *"can't create"* ]]; then
		break
	fi
	sleep 1
done

if ! mount | grep -q ' on /usr/lib/lua/luci' ; then
	mkdir -p /tmp/_usr_lib_lua_luci
	cp -rf /usr/lib/lua/luci/* /tmp/_usr_lib_lua_luci/
	mount --bind /tmp/_usr_lib_lua_luci /usr/lib/lua/luci
fi
if ! mount | grep -q ' on /usr/lib/lua/luci' ; then
	rm -rf $SYNC_OBJ
	return 1  # error
fi
if [ ! -f /tmp/_usr_lib_lua_luci/i18n.lua ]; then
	rm -rf $SYNC_OBJ
	return 1  # error
fi

if ! mount | grep -q ' on /usr/share/xiaoqiang' ; then
	mkdir -p /tmp/_usr_share_xiaoqiang
	cp -rf /usr/share/xiaoqiang/* /tmp/_usr_share_xiaoqiang/
	mount --bind /tmp/_usr_share_xiaoqiang /usr/share/xiaoqiang
fi
if ! mount | grep -q ' on /usr/share/xiaoqiang' ; then
	rm -rf $SYNC_OBJ
	return 1  # error
fi
if [ ! -f /tmp/_usr_share_xiaoqiang/xiaoqiang_version ]; then
	rm -rf $SYNC_OBJ
	return 1  # error
fi

cp -f $DIR_PATCH/base.*.lmo /usr/lib/lua/luci/i18n/

# unlock WEB lang menu
sed -i 's/ and features\["system"\]\["i18n"\] == "1" //' /usr/lib/lua/luci/view/web/inc/sysinfo.htm

# unlock change luci.main.lang
sed -i "s/option CHANNEL 'stable'/option CHANNEL 'release'/g" /usr/share/xiaoqiang/xiaoqiang_version

echo "lang patched" > /tmp/lang_patch.log
rm -rf $SYNC_OBJ

MAIN_LANG=$( uci -q get luci.main.lang )
[ "$MAIN_LANG" == "" ] && uci set luci.main.lang=en
uci set luci.languages.ru=Русский
uci set luci.languages.en=English
uci commit luci

# reload luci
luci-reload
rm -f /tmp/luci-indexcache
luci-reload

