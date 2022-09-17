#!/usr/bin/env python3

import os
import sys
import io


def die(msg):
  print("ERROR:", msg)
  sys.exit(1)


class u32_t(int):
  def __rshift__(self, other):
    return u32_t(int.__rshift__(self, other) & 0xFFFFFFFF)

  def __lshift__(self, other):
    return u32_t(int.__lshift__(self, other) & 0xFFFFFFFF)

  def __add__(self, other):
    return u32_t(int.__add__(self, other) & 0xFFFFFFFF)

  def __xor__(self, other):
    return u32_t(int.__xor__(self, other) & 0xFFFFFFFF)

def sfh_int8(data, offset = 0):
  return int.from_bytes(data[offset:offset+1], byteorder='little', signed=True)

def sfh_uint16(data, offset = 0):
  return int.from_bytes(data[offset:offset+2], byteorder='little')

# SuperFastHash algorithm from Paul Hsieh (LGPLv2.1) http://www.azillionmonkeys.com/qed/hash.html
def sfh_hash(data):
  if data is None:
    return 0
  if isinstance(data, str):
    data = data.encode("utf-8")
  size = len(data)
  if size <= 0:
    return 0
  hash = u32_t(size)
  rem = size & 3
  length = size // 4
  for i in range(length):
    hash += sfh_uint16(data, i*4)
    tmp   = sfh_uint16(data, i*4 + 2) << 11
    tmp  ^= hash
    hash  = (hash << 16) ^ tmp
    hash += hash >> 11
  i = length * 4
  if rem == 3:
    hash += sfh_uint16(data, i)
    hash ^= hash << 16
    hash ^= sfh_int8(data, i + 2) << 18
    hash += hash >> 11
  if rem == 2:
    hash += sfh_uint16(data, i)
    hash ^= hash << 11
    hash += hash >> 17
  if rem == 1:
    hash += sfh_int8(data, i)
    hash ^= hash << 10
    hash += hash >> 1
  hash ^= hash << 3
  hash += hash >> 5
  hash ^= hash << 4
  hash += hash >> 17
  hash ^= hash << 25
  hash += hash >> 6
  return hash & 0xFFFFFFFF


MSG_UNSPEC    = 0
MSG_CTXT      = 1
MSG_ID        = 2
MSG_ID_PLURAL = 3
MSG_STR       = 4

class Msg:
  def __init__(self):
    self.init()
    
  def init(self, plural_num = 0):
    self.plural_num = plural_num
    self.ctxt = None
    self.id = None
    self.id_plural = None
    self.val = [ None ] * 10  # list of string
    self.cur = MSG_UNSPEC
    self.key = None


class LmoEntry:
  def __init__(self, key_id = 0, plural = 0, offset = 0, length = 0, val = None):
    self.key_id = key_id
    self.plural = plural
    self.offset = offset
    self.length = length
    self.val = val
    self.dup = 0


class Lmo:
  entries = []  # list of LmoEntry

  def __init__(self, verbose = 0):
    self.verbose = verbose
    self.skip_dup = False
    self.entries = []
    self.msg = Msg()

  def add_entry(self, key_id, plural, val):
    entry = LmoEntry()
    entry.key_id = key_id
    entry.plural = plural
    entry.offset = len(self.entries)
    entry.length = len(val)
    entry.val = val
    ent = next((ent for ent in self.entries if ent.key_id == key_id), None)
    if ent:
      if self.skip_dup:
        return None  # skip duplicate
      entry.dup = 1
      ent.dup = 1
    self.entries.append(entry)
    return entry

  def print_msg(self):
    msg = self.msg
    if not msg.id and not msg.val[0]:
      return
    if not msg.val[0]:
      self.msg.init()
      return
    if msg.key is not None:
      val = msg.val[0]
      self.add_entry(msg.key, 0, val)
    elif msg.id and msg.plural_num >= 0:
      for i, val in enumerate(msg.val):
        if val is None:
          continue
        if (msg.ctxt and msg.id_plural):
          key = "%s\1%s\2%d" % (msg.ctxt, msg.id, i)
        elif (msg.ctxt):
          key = "%s\1%s" % (msg.ctxt, msg.id)
        elif (msg.id_plural):
          key = "%s\2%d" % (msg.id, i)
        else:
          key = msg.id
        key_id = sfh_hash(key)
        val_id = sfh_hash(val)
        if key_id != val_id:
          self.add_entry(key_id, msg.plural_num, val)
    else:
      val = msg.val[0]
      prefix = b'\\nPlural-Forms: '
      x = val.find(prefix)
      if x > 0:
        x += len(prefix)
        x2 = val.find(b'\\n', x)
        if x2 > 0:
          self.add_entry(0, -1, val[x:x2])
    # reinit object msg
    self.msg.init()

  def extract_string(self, line):
    if line.startswith('#'):
      return None
    x = line.find('"')
    if x < 0:
      return None
    line = line[x+1:]
    line = line.replace(r'\\', '\x02')
    line = line.replace(r'\"', '\x01')
    x = line.find('"')
    if x >= 0:
      line = line[:x]
    line = line.replace('\x01', '"')
    line = line.replace('\x02', '\\')
    return line

  def process_line(self, line):
    msg = self.msg
    if line.startswith('msgctxt "'):
      self.print_msg()
      msg.ctxt = ""
      msg.cur = MSG_CTXT
    elif line.startswith('msgid "'):
      self.print_msg()
      msg.id = ""
      msg.cur = MSG_ID
    elif line.startswith('msgid 0x') or line.startswith('msgkey 0x'):
      self.print_msg()
      msg.id = '\x01'
      msg.plural_num = 0
      x = line.find('0x')
      msg.key = int(line[x:], 16)
      msg.cur = MSG_UNSPEC  # without text data
    elif line.startswith('msgid_plural "'):
      msg.id_plural = ""
      msg.cur = MSG_ID_PLURAL
    elif line.startswith('msgstr "') or line.startswith('msgstr['):
      msg.plural_num = 0
      if line.startswith('msgstr['):
        x1 = line.find('[')
        x2 = line.find(']')
        msg.plural_num = int(line[x1+1:x2])
      if msg.plural_num >= 10:
        die("Too many plural forms")
      msg.val[msg.plural_num] = b''
      msg.cur = MSG_STR
    # read text data
    if msg.cur != MSG_UNSPEC:
      tmp = self.extract_string(line)
      if tmp:
        if msg.cur == MSG_CTXT:
          msg.ctxt += tmp
        if msg.cur == MSG_ID:
          msg.id += tmp
        if msg.cur == MSG_ID_PLURAL:
          msg.id_plural += tmp
        if msg.cur == MSG_STR:
          msg.val[msg.plural_num] += tmp.encode("utf-8")

  def load_from_text(self, filename):
    self.entries = []
    self.msg.init(-1)
    with open(filename, "r", encoding='UTF-8') as file:
      for line in file:
        self.process_line(line.rstrip())
      else:      
        self.print_msg()  # EOF

  def load_from_list(self, entries):
    self.entries = entries

  def save_to_bin(self, filename = None):
    buf = bytearray(b'\x00' * 0x400000)  # 4MiB
    offset = 0
    elst = []  # new list of LmoEntry()
    for i, ent in enumerate(self.entries):
      val = ent.val
      if isinstance(val, str):
        val = val.encode('utf-8')
      length = len(val)
      buf[offset:offset+length] = val
      ek = LmoEntry(ent.key_id, ent.plural, offset, length, val)
      ek.dup = ent.dup
      elst.append(ek)
      offset += length
      if offset & 3 != 0:
        offset += 4 - (offset & 3)
    elst = sorted(elst, key=lambda x: x.key_id)  
    #if offset & 0xF != 0:
    #  offset += 0x10 - (offset & 0xF)
    table_offset = offset
    for i, ent in enumerate(elst):
      buf[offset   :offset+4]  = ent.key_id.to_bytes(4, byteorder='big')
      buf[offset+4 :offset+8]  = (ent.plural + 1).to_bytes(4, byteorder='big')
      buf[offset+8 :offset+12] = ent.offset.to_bytes(4, byteorder='big')
      buf[offset+12:offset+16] = ent.length.to_bytes(4, byteorder='big')
      if self.verbose and ent.dup:
        val = ent.val.decode() if ent.val is not None else ""
        print('DUP: 0x%08X (0x%05X) "%s"' % (ent.key_id, ent.offset, val))
      offset += 16
    if offset > 0:
      buf[offset:offset+4] = table_offset.to_bytes(4, byteorder='big')
      offset += 4
    buf = buf[:offset]
    if filename:
      with open(filename, "wb") as file:
        file.write(buf)
    return buf


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding='utf-8')
  fn_inp = sys.argv[1]
  fn_out = sys.argv[2]
  lmo = Lmo(verbose = 99)
  lmo.skip_dup = False
  lmo.load_from_text(fn_inp)
  lmo.save_to_bin(fn_out)
  print('\nLMO-file saved to "{}"'.format(fn_out))




