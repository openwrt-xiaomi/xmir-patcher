#!/bin/sh

DIR_PATCH=/etc/crontabs/patches

if [ "$(mount| grep '/usr/lib/lua/luci')" != "" ]; then
	umount -l /usr/lib/lua/luci
fi
rm -rf /tmp/_usr_lib_lua_luci

if [ "$(mount| grep '/usr/share/xiaoqiang')" != "" ]; then
	umount -l /usr/share/xiaoqiang
fi
rm -rf /tmp/_usr_share_xiaoqiang

grep -v "/lang_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new
mv /etc/crontabs/root.new /etc/crontabs/root
/etc/init.d/cron restart

rm -f /etc/rc.lang
rm -f /etc/lang_patch.sh
rm -f $DIR_PATCH/lang_patch.sh
rm -f $DIR_PATCH/base.*.lmo
rm -f /tmp/lang_patch.log

luci-reload & rm -f /tmp/luci-indexcache & luci-reload

