if [ "$(mount| grep '/usr/lib/lua/luci')" != "" ]; then
	umount -l /usr/lib/lua/luci
fi
rm -rf /tmp/_usr_lib_lua_luci

if [ "$(mount| grep '/usr/share/xiaoqiang')" != "" ]; then
	umount -l /usr/share/xiaoqiang
fi
rm -rf /tmp/_usr_share_xiaoqiang

rm -f /etc/rc.lang
rm -f /etc/lang_patch.sh
rm -f /etc/base.*.lmo

luci-reload & rm -f /tmp/luci-indexcache & luci-reload
