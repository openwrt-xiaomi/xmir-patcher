#!/bin/sh

INST_FLAG_FN=/tmp/lang_patch.log

[ -e "$INST_FLAG_FN" ] && exit 0

DIR_PATCH=/etc/crontabs/patches
DIR_BACKUP=$DIR_PATCH/lang_backup

TARGET1_DIR=/usr/share/xiaoqiang
MIRROR1_DIR=/tmp/_usr_share_xiaoqiang
SYNCOBJECT1=$MIRROR1_DIR.sync

TARGET2_DIR=/usr/lib/lua/luci
MIRROR2_DIR=/tmp/_usr_lib_lua_luci
SYNCOBJECT2=$MIRROR2_DIR.sync

TARGET2_I18N_DIR=$TARGET2_DIR/i18n
TARGET2_SYSINFO_FN=$TARGET2_DIR/view/web/inc/sysinfo.htm

DATA_LANG_ROOT=/data/lang/usr/lib/lua/luci
DATA_I18N_DIR=$DATA_LANG_ROOT/i18n
DATA_VIEW_INC_DIR=$DATA_LANG_ROOT/view/web/inc
DATA_SYSINFO_FN=$DATA_VIEW_INC_DIR/sysinfo.htm


if [ `find $DIR_PATCH -maxdepth 1 -name 'base.*.lmo' | wc -l` -eq 0 ] && [ ! -d $DATA_I18N_DIR ]; then
	exit 0
fi

for i in $(seq 1 20); do
	mount | grep -q " on /data " && break
	sleep 1
done
if ! mount | grep -q " on /data " ; then
	echo "ERROR: /data is not mounted" > $INST_FLAG_FN
	exit 1
fi

for i in $(seq 1 45); do
	mkdir $SYNCOBJECT1 >/dev/null 2>&1 && break
	sleep 1
done
if ! mount | grep -q " on $TARGET1_DIR" ; then
	mkdir -p $MIRROR1_DIR
	cp -rf $TARGET1_DIR/* $MIRROR1_DIR/
	mount --bind $MIRROR1_DIR $TARGET1_DIR
fi
if ! mount | grep -q " on $TARGET1_DIR" ; then
	rm -rf $SYNCOBJECT1
	echo "ERROR: cannot mount bind for $TARGET1_DIR" > $INST_FLAG_FN
	exit 1
fi
if [ ! -f $MIRROR1_DIR/xiaoqiang_version ]; then
	rm -rf $SYNCOBJECT1
	echo "ERROR: file $MIRROR1_DIR/xiaoqiang_version not found" > $INST_FLAG_FN
	exit 1
fi

# unlock change luci.main.lang
sed -i "s/option CHANNEL 'stable'/option CHANNEL 'release'/g" $TARGET1_DIR/xiaoqiang_version

rm -rf $SYNCOBJECT1

mkdir -p $DATA_I18N_DIR
cp -f $DIR_PATCH/base.*.lmo $DATA_I18N_DIR/ >/dev/null 2>&1

if [ `find $DATA_I18N_DIR -maxdepth 1 -name 'base.*.lmo' | wc -l` -eq 0 ]; then
	echo "ERROR: language files not found in $DATA_I18N_DIR" > $INST_FLAG_FN
	exit 1
fi

if mount | grep -q " on $TARGET2_I18N_DIR" ; then
	if ! mount | grep -q "$DATA_I18N_DIR on $TARGET2_I18N_DIR" ; then
		umount -l $TARGET2_I18N_DIR
	fi
fi
if ! mount | grep -q "$DATA_I18N_DIR on $TARGET2_I18N_DIR" ; then
	mount --bind $DATA_I18N_DIR $TARGET2_I18N_DIR
fi
if ! mount | grep -q "$DATA_I18N_DIR on $TARGET2_I18N_DIR" ; then
	echo "ERROR: cannot mount bind for $TARGET2_I18N_DIR" > $INST_FLAG_FN
	exit 1
fi

mkdir -p $DATA_VIEW_INC_DIR
if [ ! -f $DATA_SYSINFO_FN ]; then
	cp -f $TARGET2_SYSINFO_FN $DATA_SYSINFO_FN
fi

# unlock WEB lang menu in persistent copy
sed -i 's/ and features\["system"\]\["i18n"\] == "1" //' $DATA_SYSINFO_FN

if mount | grep -q " on $TARGET2_SYSINFO_FN" ; then
	if ! mount | grep -q "$DATA_SYSINFO_FN on $TARGET2_SYSINFO_FN" ; then
		umount -l $TARGET2_SYSINFO_FN
	fi
fi
if ! mount | grep -q "$DATA_SYSINFO_FN on $TARGET2_SYSINFO_FN" ; then
	mount --bind $DATA_SYSINFO_FN $TARGET2_SYSINFO_FN
fi


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

