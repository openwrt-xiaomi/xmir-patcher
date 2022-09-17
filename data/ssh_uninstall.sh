#!/bin/sh

grep -v "/ssh_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new
mv /etc/crontabs/root.new /etc/crontabs/root
/etc/init.d/cron restart

rm -f /etc/crontabs/patches/ssh_patch.sh
rm -f /tmp/ssh_patch.log

