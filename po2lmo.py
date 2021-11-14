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
  x = int.from_bytes(data[offset:offset+1], byteorder='little')
  return x if x < 0x80 else x - 0x100

def sfh_uint16(data, offset = 0):
  return int.from_bytes(data[offset:offset+2], byteorder='little')

# SuperFastHash algorithm from Paul Hsieh (LGPLv2.1) http://www.azillionmonkeys.com/qed/hash.html
def sfh_hash(data):
  if data is None:
    return 0
  if isinstance(data, str):
    data = data.encode("utf-8")
  size = len(data)
  hash = u32_t(size)
  if size <= 0:
    return 0
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
    self.plural_num = -1
    self.ctxt = None
    self.id = None
    self.id_plural = None
    self.val = [ None ]  # list of string
    self.cur = MSG_UNSPEC
    self.key = None


class LmoEntry:
  def __init__(self, key_id = 0, val_id = 0, offset = 0, length = 0, val = None):
    self.key_id = key_id
    self.val_id = val_id
    self.offset = offset
    self.length = length
    self.val = val


class Lmo:
  entries = []  # list of LmoEntry

  def __init__(self, verbose = 0):
    self.verbose = verbose
    self.entries = []
    self.msg = Msg()

  def add_entry(self, key_id, val_id, val):
    entry = LmoEntry()
    entry.key_id = key_id
    entry.val_id = val_id
    entry.offset = len(self.entries)
    entry.length = len(val)
    entry.val = val
    self.entries.append(entry)

  def print_msg(self):
    msg = self.msg
    if msg.key is not None:
      val = msg.val[msg.plural_num]
      self.add_entry(msg.key, msg.plural_num + 1, val)
    elif msg.id and msg.val[0]:
      for i in range(msg.plural_num + 1):
        if i >= len(msg.val):
          continue
        val = msg.val[i]
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
          self.add_entry(key_id, msg.plural_num + 1, val)
    elif msg.val[0]:
      p = msg.val[0]
      prefix = b'\\nPlural-Forms: '
      x = p.find(prefix)
      if x > 0:
        x += len(prefix)
        x2 = p.find(b'\\n', x)
        if x2 > 0:
          field = p[x:x2]
          self.add_entry(0, 0, field)
    self.msg = None
    self.msg = Msg()
    #print('-------------')
    return self.msg

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

  def process_line(self, line, eof = False):
    msg = self.msg
    if line.startswith('msgctxt "'):
      if msg.id or msg.val[0]:
        msg = self.print_msg()
      msg.ctxt = ""
      msg.cur = MSG_CTXT
    elif eof or line.startswith('msgid "'):
      if msg.id or msg.val[0]:
        msg = self.print_msg()
      msg.id = ""
      msg.cur = MSG_ID
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
      if len(msg.val) <= msg.plural_num:
        x = msg.plural_num - len(msg.val) + 1
        for i in range(x):
          msg.val.append(None)
      msg.val[msg.plural_num] = b''
      msg.cur = MSG_STR
    elif line.startswith('msgkey 0x'):
      if msg.id or msg.val[0]:
        msg = self.print_msg()
      msg.id = '\x01'
      msg.plural_num = 0
      x = line.find('0x')
      msg.key = int(line[x:], 16)
      return
    if eof:
      return 
    if msg.cur != MSG_UNSPEC:
      tmp = self.extract_string(line)
      if tmp is not None and len(tmp) > 0:
        if msg.cur == MSG_CTXT:
          msg.ctxt += tmp
          #print('mctxt = "{}"'.format(msg.ctxt))
        if msg.cur == MSG_ID:
          msg.id += tmp
          #print('msgid = "{}"'.format(msg.id))
        if msg.cur == MSG_ID_PLURAL:
          msg.id_plural += tmp
        if msg.cur == MSG_STR:
          msg.val[msg.plural_num] += tmp.encode("utf-8")
          #print('msgstr[{}] = "{}"'.format(msg.plural_num, tmp))
    self.msg = msg

  def load_from_text(self, filename):
    self.entries = []
    self.msg = Msg()
    with open(filename, "r", encoding='UTF-8') as file:
      for line in file:
        self.process_line(line.rstrip())
      else:
        self.process_line("", eof=True)

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
      val_id = ent.val_id
      elst.append(LmoEntry(ent.key_id, val_id, offset, length, val))
      offset += length
      if offset & 3 != 0:
        offset += 4 - (offset & 3)
    elst = sorted(elst, key=lambda x: x.key_id)  
    #if offset & 0xF != 0:
    #  offset += 0x10 - (offset & 0xF)
    table_offset = offset
    for i, ent in enumerate(elst):
      buf[offset   :offset+4]  = ent.key_id.to_bytes(4, byteorder='big')
      buf[offset+4 :offset+8]  = ent.val_id.to_bytes(4, byteorder='big')
      buf[offset+8 :offset+12] = ent.offset.to_bytes(4, byteorder='big')
      buf[offset+12:offset+16] = ent.length.to_bytes(4, byteorder='big')
      if self.verbose:
        for k, ek in enumerate(elst):
          if ent.key_id == ek.key_id and ent.offset != ek.offset:
            val = "" if ent.val is None else ent.val.decode()
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
  fn_inp = sys.argv[1]
  fn_out = sys.argv[2]
  lmo = Lmo(verbose = 99)
  lmo.load_from_text(fn_inp)
  lmo.save_to_bin(fn_out)
  print('\nLMO-file saved to "{}"'.format(fn_out))




