#!/usr/bin/env python3

import os
import sys


def die(msg):
  print("ERROR:", msg)
  sys.exit(1)


class LmoEntry:
  def __init__(self, key_id = 0, plural = 0, offset = 0, length = 0, val = None):
    self.key_id = key_id
    self.plural = plural
    self.offset = offset
    self.length = length
    self.val = val
    self.dup = 0


class Lmo:
  options = ""
  entries = []  # list of LmoEntry

  def __init__(self):
    self.options = ""
    self.entries = []

  def load_from_bin(self, filename):
    self.entries = []
    use_plural_num = False
    with open(filename, "rb") as file:
      data = file.read()
    table_offset = int.from_bytes(data[-4:], byteorder='big')
    #print("table_offset = 0x%X" % table_offset)
    off = table_offset
    while True:
      if off + 16 >= len(data):
        break
      entry = LmoEntry()
      entry.key_id = int.from_bytes(data[off   :off+4] , byteorder='big')
      entry.plural = int.from_bytes(data[off+4 :off+8] , byteorder='big') - 1
      entry.offset = int.from_bytes(data[off+8 :off+12], byteorder='big')
      entry.length = int.from_bytes(data[off+12:off+16], byteorder='big')
      entry.val = data[entry.offset:entry.offset+entry.length]
      #print("%08X %d %08X %d" % (entry.key_id, entry.plural, entry.offset, entry.length))
      if off == table_offset:
        if entry.key_id == 0 and entry.plural == -1:
          use_plural_num = True
      if use_plural_num:
        if entry.plural >= 10 or (off != table_offset and entry.plural < 0):
          die("Too many plural forms")
      else:
        entry.plural = 0  # older version LMO-files contain hash of value
      self.entries.append(entry)
      off += 16
    self.entries = sorted(self.entries, key=lambda x: x.offset)
    #self.dup_search()

  def dup_search(self):
    count = 0
    for i, ent in enumerate(self.entries):
      for k, ek in enumerate(self.entries):
        if ent.key_id == ek.key_id and ent.offset != ek.offset:
          ent.dup = 1
          count += 1
          break
    return count

  def dup_search2(self):
    count = 0
    for i, ent in enumerate(self.entries):
      if ent.dup != 1:
        continue    # skip unique entry
      val = ent.val.decode('utf-8')
      for k, ek in enumerate(self.entries):
        if ek.key_id != ent.key_id:
          continue
        if ek.offset == ent.offset:
          continue  # skip self
        if ek.dup == 1:
          vk = ek.val.decode('utf-8')
          if vk == val:
            ek.dup = 2
            count += 1
    return count

  def save_to_text(self, filename = None):
    txt = ""    
    if 'k' in self.options:
      entries = sorted(self.entries, key=lambda x: x.key_id)
    else:
      entries = sorted(self.entries, key=lambda x: x.offset)
    for i, ent in enumerate(self.entries):
      ent.dup = 0
    self.dup_search()
    if 'z' in self.options:
      self.dup_search2()
    for i, ent in enumerate(entries):
      if ent.dup == 2:
        continue  # skip dup2
      val = ent.val.decode('utf-8')
      val = val.replace('\\', '\\\\')
      val = val.replace('"', r'\"')      
      if ent.key_id == 0 and ent.plural == -1:
        val = val.replace('\n', r'\n')
        txt += 'msgid ""' + '\n'
        txt += 'msgstr ""' + '\n'
        txt += '"Project-Id-Version: LuCI: {}\\n"'.format("base") + '\n'
        txt += '"Language: {}\\n"'.format("en") + '\n'
        txt += '"MIME-Version: 1.0\\n"' + '\n'
        txt += '"Content-Type: text/plain; charset=UTF-8\\n"' + '\n'
        txt += '"Content-Transfer-Encoding: 8bit\\n"' + '\n'
        txt += '"Plural-Forms: {}\\n"'.format(val) + '\n'
        txt += '"X-Generator: Weblate 4.8.1-dev\\n"' + '\n'
        txt += '\n'
        continue
      prefix = ''
      #if ent.plural != 0:
      #  prefix = '[%d]' % ent.plural
      if ent.dup:
        txt += '# DUP' + '\n'
      txt += 'msgid 0x{}'.format("%08X" % ent.key_id) + '\n' 
      line_limit = 77
      val = val.replace('\r', '')
      if val.find('\n') >= 0:
        txt += 'msgstr{} ""'.format(prefix) + '\n'
        vlist = val.split('\n')
        for i, v in enumerate(vlist):          
          v = v + r'\n' if i+1 < len(vlist) else v
          if len(v) > 0:
            txt += '"{}"'.format(v) + '\n'
      elif val.find(r'\n') >= 0:
        txt += 'msgstr{} ""'.format(prefix) + '\n'
        vlist = val.split(r'\n')
        for i, v in enumerate(vlist):
          if len(v) > 0:
            txt += '"{}"'.format(v) + '\n'
      elif len(val) > line_limit - 10 and val.find(' ') > 0:
        txt += 'msgstr{} ""'.format(prefix) + '\n'
        wlist = val.split(' ')
        v = ""
        for i, word in enumerate(wlist):
          if i > 0:
            word = ' ' + word
          if len(v) + len(word) < line_limit or len(v) == 0:
            v += word
            continue
          txt += '"{}"'.format(v) + '\n'
          v = word
        if len(v) > 0:
          txt += '"{}"'.format(v) + '\n'
      else:
        txt += 'msgstr{} "{}"'.format(prefix, val) + '\n'
      txt += '\n'
    if filename:
      with open(filename, "wt", encoding='UTF-8', newline = "\n") as file:
        file.write(txt)
    return txt


if __name__ == "__main__":
  fn_inp = sys.argv[1]
  fn_out = sys.argv[2]
  lmo = Lmo()
  if len(sys.argv) > 3:
    lmo.options = sys.argv[3]
  lmo.load_from_bin(fn_inp)
  if not ('m' in lmo.options):
    lmo.save_to_text(fn_out)
    print('\nPO-file saved to "{}"'.format(fn_out))
    sys.exit(0)

  # Merge 2 lmo-files
  fn_inp2 = sys.argv[4]
  lmo2 = Lmo()
  lmo2.load_from_bin(fn_inp2)
  for i, ent in enumerate(lmo2.entries):
    dup = False
    for k, ek in enumerate(lmo.entries):
      if ek.key_id == ent.key_id:
        dup = True
        break
    if not dup:
      lmo.entries.append(ent)
  lmo.options = 'kz'
  lmo.save_to_text(fn_out)
  print('\nMerged PO-file saved to "{}"'.format(fn_out))
  
  '''
  fn_out = fn_inp
  import po2lmo
  lmo3 = po2lmo.Lmo(verbose = 0)
  lmo3.load_from_list(lmo.entries)
  lmo3.save_to_bin(fn_out)
  print('\nMerged LMO-file saved to "{}"'.format(fn_out))
  '''


