#!/bin/sh

INST_FLAG_FN=/tmp/lang_patch.log

[ -e "$INST_FLAG_FN" ] && return 0

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/lang_backup

TARGET1_DIR=/usr/share/xiaoqiang
MIRROR1_DIR=/tmp/_usr_share_xiaoqiang
SYNCOBJECT1=$MIRROR1_DIR.sync

TARGET2_DIR=/usr/lib/lua/luci
MIRROR2_DIR=/tmp/_usr_lib_lua_luci
SYNCOBJECT2=$MIRROR2_DIR.sync


if [ `find $DIR_PATCH -maxdepth 1 -name 'base.*.lmo' | wc -l` -eq 0 ]; then
	return 0
fi

for i in $(seq 1 45); do
	mkdir $SYNCOBJECT1 &> /dev/null && break
	sleep 1
done
if ! mount | grep -q " on $TARGET1_DIR" ; then
	mkdir -p $MIRROR1_DIR
	cp -rf $TARGET1_DIR/* $MIRROR1_DIR/
	mount --bind $MIRROR1_DIR $TARGET1_DIR
fi
if ! mount | grep -q " on $TARGET1_DIR" ; then
	rm -rf $SYNCOBJECT1
	return 1  # error
fi
if [ ! -f $MIRROR1_DIR/xiaoqiang_version ]; then
	rm -rf $SYNCOBJECT1
	return 1  # error
fi

# unlock change luci.main.lang
sed -i "s/option CHANNEL 'stable'/option CHANNEL 'release'/g" $TARGET1_DIR/xiaoqiang_version

rm -rf $SYNCOBJECT1


for i in $(seq 1 45); do
	mkdir $SYNCOBJECT2 &> /dev/null && break
	sleep 1
done
if ! mount | grep -q " on $TARGET2_DIR" ; then
	mkdir -p $MIRROR2_DIR
	cp -rf $TARGET2_DIR/* $MIRROR2_DIR/
	mount --bind $MIRROR2_DIR $TARGET2_DIR
fi
if ! mount | grep -q " on $TARGET2_DIR" ; then
	rm -rf $SYNCOBJECT2
	return 1  # error
fi
if [ ! -f $MIRROR2_DIR/i18n.lua ]; then
	rm -rf $SYNCOBJECT2
	return 1  # error
fi

cp -f $DIR_PATCH/base.*.lmo /usr/lib/lua/luci/i18n/

# unlock WEB lang menu
sed -i 's/ and features\["system"\]\["i18n"\] == "1" //' /usr/lib/lua/luci/view/web/inc/sysinfo.htm

rm -rf $SYNCOBJECT2


echo "lang patched" > $INST_FLAG_FN

MAIN_LANG=$( uci -q get luci.main.lang )
[ "$MAIN_LANG" == "" ] && uci set luci.main.lang=en
uci set luci.languages.ru=Русский
uci set luci.languages.en=English
uci commit luci

# reload luci
luci-reload
rm -f /tmp/luci-indexcache
luci-reload

