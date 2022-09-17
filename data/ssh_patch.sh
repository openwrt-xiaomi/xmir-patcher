#!/bin/sh

[ -e "/tmp/ssh_patch.log" ] && return 0

HAVE_PATCH=$( grep '= "release"' /etc/init.d/dropbear )
if [ -z "$HAVE_PATCH" ]; then
	return 0
fi

sed -i 's/= "release"/= "XXXXXX"/g' /etc/init.d/dropbear

/etc/init.d/dropbear enable
/etc/init.d/dropbear restart

echo "ssh enabled" > /tmp/ssh_patch.log
