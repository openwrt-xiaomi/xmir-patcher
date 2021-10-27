#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import gateway
from gateway import die


gw = gateway.Gateway()

fn_dir      = 'data/'
fn_local    = 'data/lang_patch.sh'
fn_remote   = '/tmp/lang_patch.sh'
fn_local_i  = 'data/lang_install.sh'
fn_remote_i = '/tmp/lang_install.sh'
fn_local_u  = 'data/lang_uninstall.sh'
fn_remote_u = '/tmp/lang_uninstall.sh'

action = 'install'
if len(sys.argv) > 1:
  if sys.argv[1].startswith('u') or sys.argv[1].startswith('r'):
    action = 'uninstall'

if action == 'install':
  gw.upload(fn_local, fn_remote)
  gw.upload(fn_local_i, fn_remote_i)

gw.upload(fn_local_u, fn_remote_u)

if action == 'install':
  for filename in [fn for fn in os.listdir(fn_dir) if fn.split(".")[-1] in ['lmo']]:
    gw.upload(fn_dir + filename, '/tmp/' + filename)

print("All files uploaded!")

print("Run scripts...")
if action == 'install':
  gw.run_cmd("sh " + fn_remote_i)
else:
  gw.run_cmd("sh " + fn_remote_u)

gw.run_cmd("rm -f " + fn_remote)
gw.run_cmd("rm -f " + fn_remote_i)
gw.run_cmd("rm -f " + fn_remote_u)

print("Ready! The language files are installed.")
