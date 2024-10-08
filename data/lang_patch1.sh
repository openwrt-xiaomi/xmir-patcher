#!/bin/sh
# ======= FILE: /usr/lib/lua/luci/view/web/index.htm ======= 
sed -i 's/>断开</><%:断开%></g' /usr/lib/lua/luci/view/web/index.htm
sed -i 's/'\''拨号成功'\''/'\''<%:拨号成功%>'\''/g' /usr/lib/lua/luci/view/web/index.htm
sed -i 's/"Mesh组网"/"<%:Mesh组网%>"/g' /usr/lib/lua/luci/view/web/index.htm
# ======= FILE: /usr/lib/lua/luci/view/web/apindex.htm ======= 
sed -i 's/"Mesh组网"/"<%:Mesh组网%>"/g' /usr/lib/lua/luci/view/web/apindex.htm
# ======= FILE: /usr/lib/lua/luci/view/web/inc/g.js.htm ======= 
sed -i 's/'\''此时5G网络已关闭'\''/'\''<%:此时5G网络已关闭%>'\''/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
sed -i 's/'\''此时5G网络已打开'\''/'\''<%:此时5G网络已打开%>'\''/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
sed -i 's/'\''请选择要添加的设备'\''/'\''<%:请选择要添加的设备%>'\''/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
sed -i 's/'\''搜索并添加Mesh节点'\''/'\''<%:搜索并添加Mesh节点%>'\''/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
sed -i 's/'\''没有搜索到可用的mesh节点'\''/'\''<%:没有搜索到可用的mesh节点%>'\''/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
sed -i 's/"地区简称"/"<%:地区简称%>"/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
sed -i 's/"家"/"<%:家%>"/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
sed -i 's/"客厅"/"<%:客厅%>"/g' /usr/lib/lua/luci/view/web/inc/g.js.htm
# ======= FILE: /usr/lib/lua/luci/view/web/inc/header.htm ======= 
# ======= FILE: /usr/lib/lua/luci/view/web/inc/sysinfo.htm ======= 
sed -i 's/>\*如需修改时区，请切换到主Mesh路由进行修改，会自动同步到子Mesh路由</><%:\*如需修改时区，请切换到主Mesh路由进行修改，会自动同步到子Mesh路由%></g' /usr/lib/lua/luci/view/web/inc/sysinfo.htm
