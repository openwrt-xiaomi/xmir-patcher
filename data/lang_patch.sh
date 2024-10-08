#!/bin/sh

[ -e "/tmp/lang_patch.log" ] && return 0

DIR_PATCH=/etc/crontabs/patches

if [ `ls $DIR_PATCH/base.*.lmo |wc -l` -eq 0 ]; then
	return 0
fi

#if [ -e "/etc/xiaoqiang_version" ]; then
#	return 0
#fi

if [ -e "/usr/lib/lua/luci/i18n/base.en.lmo" ]; then
	return 0
fi

mkdir -p /tmp/_usr_lib_lua_luci
cp -rf /usr/lib/lua/luci/* /tmp/_usr_lib_lua_luci/
mount --bind /tmp/_usr_lib_lua_luci /usr/lib/lua/luci

cp $DIR_PATCH/base.*.lmo /usr/lib/lua/luci/i18n

# save original file
cp -f /usr/share/xiaoqiang/xiaoqiang_version /etc/xiaoqiang_version

mkdir -p /tmp/_usr_share_xiaoqiang
cp -rf /usr/share/xiaoqiang/* /tmp/_usr_share_xiaoqiang/
mount --bind /tmp/_usr_share_xiaoqiang /usr/share/xiaoqiang

# unlock WEB lang menu
sed -i 's/ and features\["system"\]\["i18n"\] == "1" //' /usr/lib/lua/luci/view/web/inc/sysinfo.htm

# unlock change luci.main.lang
sed -i "s/option CHANNEL 'stable'/option CHANNEL 'release'/g" /usr/share/xiaoqiang/xiaoqiang_version

if [ -e "$DIR_PATCH/lang_patch1.sh" ]; then
	sh $DIR_PATCH/lang_patch1.sh
fi

echo "lang patched" > /tmp/lang_patch.log

MAIN_LANG=$( uci -q get luci.main.lang )
[ "$MAIN_LANG" == "" ] && uci set luci.main.lang=en
uci set luci.languages.ru=Русский
uci set luci.languages.en=English
uci set luci.languages.es=Español
uci commit luci

# reload luci
luci-reload & rm -f /tmp/luci-indexcache & luci-reload

