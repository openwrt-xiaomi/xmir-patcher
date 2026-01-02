#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import types
import re

import xmir_base
import ssh2
from gateway import *


class www_lmo():
  fn_local = None
  fn_remote = None
  data = None
  out = []
  
  def __init__(w, fn_local = None, fn_remote = None):
    w.fn_local = fn_local
    w.fn_remote = fn_remote
    w.data = None
    w.out = []    

  def load_file(w):
    with open(w.fn_local, "r", encoding="utf-8") as file:
      w.data = file.read()
  
  def parse(w):
    if not w.data:
      w.load_file()
    p = re.compile(r'[^%][>]([^><]*?[\u4e00-\u9fff][^><]*?)[<][^%]')
    w.parse1(p)
    p = re.compile(r'[\']([^><\n\']*?[\u4e00-\u9fff][^><\n\']*?)[\']')
    w.parse1(p)
    p = re.compile(r'["]([^><\n"]*?[\u4e00-\u9fff][^><\n"]*?)["]')
    w.parse1(p)

  def parse1(w, template):
    for m in template.finditer(w.data):
      txt = m.group()
      if txt.find('<%') > 0 or txt.find('%>') > 0:
        continue
      if txt.find('// ') > 0:  # skip comments
        continue
      if txt.find('if ') > 0:  # skip code
        continue
      if txt.find('{') > 0:    # skip code
        continue
      if txt.find(' = ') > 0:  # skip code
        continue
      b = m.start()
      t1 = m.start(1)
      t2 = m.end(1)
      e = m.end()
      #print(b, t1, t2, e)
      prefix = w.data[b:t1]
      string = w.data[t1:t2]
      postfix = w.data[t2:e]
      if len(prefix) == 2 and prefix[1] == '>':
        prefix = prefix[1]
        txt = txt[1:]
      if len(postfix) == 2 and postfix[0] == '<':
        postfix = postfix[0]
        txt = txt[:-1]
      #print('"{}" "{}" "{}"'.format(prefix, string, postfix))
      s = string.strip()
      if s == string:
        out = prefix + '<%:' + string + '%>' + postfix
        msg = string
      else:
        p = string.find(s)
        if p < 0:
          continue  # fixme
        out = prefix + string[:p] + '<%:' + s + '%>' + string[p+len(s):] + postfix
        msg = s
      #print(b, out)
      # check for dup
      dup = 0
      for i, v in enumerate(w.out):
        if v.txt_orig == txt:
          dup = 1
          break
      if dup == 0:
        v = types.SimpleNamespace()
        v.pos = b
        v.txt_orig = txt
        v.txt_new = out
        v.sed = ""
        v.msg = msg
        w.out.append(v)

  def sed_escape(w, txt):
    txt = txt.replace('\\', '\\\\')
    txt = txt.replace('\n', r'\n')
    txt = txt.replace('\r', r'\r')
    txt = txt.replace('\t', r'\t')
    txt = txt.replace("'", r"'\''")
    txt = txt.replace('[', r'\[')
    txt = txt.replace(']', r'\]')
    txt = txt.replace('$', r'\$')
    txt = txt.replace('*', r'\*')
    txt = txt.replace('.', r'\.')
    txt = txt.replace('$', r'\$')
    txt = txt.replace('^', r'\^')
    txt = txt.replace('/', r'\/')
    return txt

  def gen_sed(w):
    for i, v in enumerate(w.out):
      #print(v.pos, v.txt_new)
      orig = w.sed_escape(v.txt_orig)
      new  = w.sed_escape(v.txt_new)
      prefix = ''
      if v.txt_orig.find('\n') > 0:
        prefix = ':a;N;$!ba;'  # see: https://stackoverflow.com/questions/1251999/how-can-i-replace-each-newline-n-with-a-space-using-sed
      v.sed = "sed -i '{}s/{}/{}/g' {}".format(prefix, orig, new, w.fn_remote) 


gw = Gateway()

fn_dir      = 'data/'
fn_local    = 'data/lang_patch.sh'
fn_remote   = '/tmp/lang_patch.sh'
fn_local_i  = 'data/lang_install.sh'
fn_remote_i = '/tmp/lang_install.sh'
fn_local_u  = 'data/lang_uninstall.sh'
fn_remote_u = '/tmp/lang_uninstall.sh'
fn_www_local  = f'tmp/lang_patch_www.sh'
fn_www_remote = '/tmp/lang_patch_www.sh'

os.makedirs('tmp', exist_ok = True)

full_install = False
action = 'install'
if len(sys.argv) > 1:
  if sys.argv[1] == 'full':
    full_install = True
  if sys.argv[1].startswith('u') or sys.argv[1].startswith('r'):
    action = 'uninstall'

if action == 'install':
  gw.upload(fn_local, fn_remote)
  gw.upload(fn_local_i, fn_remote_i)

gw.upload(fn_local_u, fn_remote_u)

if action == 'install':
  patch_installed = 0
  fn = 'tmp/lang_patch.log'
  if os.path.exists(fn):
    os.remove(fn)
  try:
    gw.download('/tmp/lang_patch.log', fn, verbose = 0)
  except ssh2.exceptions.SCPProtocolError:
    patch_installed = 0
  txt = ''
  if os.path.exists(fn):
    with open(fn, 'r') as file:
      txt = file.read()
  if txt:
    patch_installed = 2 if 'www_patch' in txt else 1
  if patch_installed >= 2:
    die("Full lang patch already installed!")
  #if patch_installed:
  #  print("Uninstall lang_patch...")
  #  gw.run_cmd(f"chmod +x {fn_remote_u} ; {fn_remote_u}")

if action == 'install':
  import po2lmo
  for filename in [fn for fn in os.listdir(fn_dir) if fn.split(".")[-1] in ['po']]:
    fname = fn_dir + filename
    print('Convert file "{}" to LMO ...'.format(fname))
    lmo = po2lmo.Lmo()
    lmo.skip_dup = True
    lmo.load_from_text(fname)
    lmo_fname = os.path.splitext(filename)[0] + '.lmo'
    lmo.save_to_bin(fn_dir + lmo_fname)
    gw.upload(fn_dir + lmo_fname, '/tmp/' + lmo_fname)

if action == 'install' and full_install:
  dn_www = "tmp/www"
  os.makedirs(dn_www, exist_ok = True)
  wwwlst = [ "/usr/lib/lua/luci/view/web/index.htm",
             "/usr/lib/lua/luci/view/web/apindex.htm",
             "/usr/lib/lua/luci/view/web/inc/g.js.htm",
             "/usr/lib/lua/luci/view/web/inc/header.htm",
             "/usr/lib/lua/luci/view/web/inc/sysinfo.htm",
             "/usr/lib/lua/luci/view/web/inc/wanCheck.js.htm",
             "/usr/lib/lua/luci/view/web/setting/iptv.htm",
           ]  
  www = []
  for i, www_remote in enumerate(wwwlst):
    www_local = dn_www + '/' + www_remote.replace('/', '_')
    try:
      gw.download(www_remote, www_local, verbose = 0)
    except ssh2.exceptions.SCPProtocolError:
      print('WARN: file "{}" not found'.format(www_remote))
      continue
    w = www_lmo(www_local, www_remote)
    www.append(w)
  if os.path.exists(fn_www_local):
    os.remove(fn_www_local)  
  file = open(fn_www_local, "wt", encoding='UTF-8', newline = "\n")
  file.write('#!/bin/sh\n')
  for i, w in enumerate(www):
    #print("===== FILE:", w.fn_remote)
    w.parse()
    w.gen_sed()
    file.write('# ======= FILE: {} ======= \n'.format(w.fn_remote))
    for i, v in enumerate(w.out):
      if v.sed:
        file.write(v.sed + '\n')
  file.close()
  gw.upload(fn_www_local, fn_www_remote)
  
print("All files uploaded!")

print("Run scripts...")
run_script = fn_remote_i if action == 'install' else fn_remote_u
gw.run_cmd(f"chmod +x {run_script} ; {run_script}", timeout = 17)

time.sleep(1.5)

gw.run_cmd(f"rm -f {fn_remote} ; rm -f {fn_remote_i} ; rm -f {fn_remote_u}")
if full_install:
    gw.run_cmd(f"rm -f {fn_www_remote}")

prefix = '' if action == 'install' else 'un'
print(f"Ready! The language files are {prefix}installed.")
