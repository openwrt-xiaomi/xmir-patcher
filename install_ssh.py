#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import xmir_base
import gateway
from gateway import die


gw = gateway.Gateway()

fn_dir      = 'data/'
fn_local    = 'data/ssh_patch.sh'
fn_remote   = '/tmp/ssh_patch.sh'
fn_local_i  = 'data/ssh_install.sh'
fn_remote_i = '/tmp/ssh_install.sh'
fn_local_u  = 'data/ssh_uninstall.sh'
fn_remote_u = '/tmp/ssh_uninstall.sh'

action = 'install'
if len(sys.argv) > 1:
  if sys.argv[1].startswith('u') or sys.argv[1].startswith('r'):
    action = 'uninstall'

if action == 'install':
  gw.upload(fn_local, fn_remote)
  gw.upload(fn_local_i, fn_remote_i)

gw.upload(fn_local_u, fn_remote_u)

print("All files uploaded!")
'''
if action == 'install':
  gw.ssh_close()
  import passw
  gw = gateway.Gateway()
  if not gw.ping():
    die('SSH not active!')
'''

print("Run scripts...")
if action == 'install':
  gw.run_cmd("sh " + fn_remote_i)
else:
  gw.run_cmd("sh " + fn_remote_u)

gw.run_cmd("rm -f " + fn_remote)
gw.run_cmd("rm -f " + fn_remote_i)
gw.run_cmd("rm -f " + fn_remote_u)

print("Ready! The SSH patch installed.")
