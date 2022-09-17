#!/bin/sh

grep -v "/etc/crontabs/ssh_patch.sh" /etc/crontabs/root > /etc/crontabs/root.new; 
mv /etc/crontabs/root.new /etc/crontabs/root
/etc/init.d/cron restart

rm -f /etc/crontabs/ssh_patch.sh

