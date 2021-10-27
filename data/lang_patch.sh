if [ `ls /etc/base.*.lmo |wc -l` -eq 0 ]; then
	return 0
fi

mkdir -p /tmp/_usr_lib_lua_luci
cp -rf /usr/lib/lua/luci/* /tmp/_usr_lib_lua_luci/
mount --bind /tmp/_usr_lib_lua_luci /usr/lib/lua/luci

cp /etc/base.*.lmo /usr/lib/lua/luci/i18n

# save original file
cp -f /usr/share/xiaoqiang/xiaoqiang_version /etc/xiaoqiang_version

mkdir -p /tmp/_usr_share_xiaoqiang
cp -rf /usr/share/xiaoqiang/* /tmp/_usr_share_xiaoqiang/
mount --bind /tmp/_usr_share_xiaoqiang /usr/share/xiaoqiang

# unlock WEB lang menu
sed -i 's/ and features\["system"\]\["i18n"\] == "1" //' /usr/lib/lua/luci/view/web/inc/sysinfo.htm

# unlock change luci.main.lang
sed -i "s/option CHANNEL 'stable'/option CHANNEL 'release'/g" /usr/share/xiaoqiang/xiaoqiang_version
