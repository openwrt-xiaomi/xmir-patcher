#!/usr/bin/env python
#############################################################
# ubi_reader/ubifs
# (C) Collin Mulliner based on Jason Pruitt's output.py

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#############################################################

import os
import time
from ubireader.ubifs.defines import *
from ubireader.ubifs import walk
from ubireader.ubifs.misc import decompress
from ubireader.debug import error, log, verbose_log


def list_files(ubifs, list_path):
    pathnames = list_path.split("/")
    pnames = []
    for i in pathnames:
        if len(i) > 0:
            pnames.append(i)
    try:
        inodes = {}
        bad_blocks = []

        walk.index(ubifs, ubifs.master_node.root_lnum, ubifs.master_node.root_offs, inodes, bad_blocks)

        if len(inodes) < 2:
            raise Exception('No inodes found')

        inum = find_dir(inodes, 1, pnames, 0)

        if inum == None:
            return

        if not 'dent' in inodes[inum]:
            return

        for dent in inodes[inum]['dent']:
            print_dent(ubifs, inodes, dent, longts=False)
        
        if len(bad_blocks):
            error(list_files, 'Warn', 'Data may be missing or corrupted, bad blocks, LEB [%s]' % ','.join(map(str, bad_blocks)))

    except Exception as e:
        error(list_files, 'Error', '%s' % e)


def copy_file(ubifs, filepath, destpath):
    pathnames = filepath.split("/")
    pnames = []
    for i in pathnames:
        if len(i) > 0:
            pnames.append(i)

    filename = pnames[len(pnames)-1]
    del pnames[-1]

    inodes = {}
    bad_blocks = []

    walk.index(ubifs, ubifs.master_node.root_lnum, ubifs.master_node.root_offs, inodes, bad_blocks)

    if len(inodes) < 2:
        return False

    inum = find_dir(inodes, 1, pnames, 0)

    if inum == None:
        return False

    if not 'dent' in inodes[inum]:
        return False

    for dent in inodes[inum]['dent']:
        if dent.name == filename:
            filedata = _process_reg_file(ubifs, inodes[dent.inum], filepath)
            if os.path.isdir(destpath):
                destpath = os.path.join(destpath, filename)
            with open(destpath, 'wb') as f:
                f.write(filedata)
            return True
    return False


def find_dir(inodes, inum, names, idx):
    if len(names) == 0:
        return 1
    for dent in inodes[inum]['dent']:
        if dent.name == names[idx]:
            if len(names) == idx+1:
                return dent.inum
            else:
                return find_dir(inodes, dent.inum, names, idx+1)
    return None


def print_dent(ubifs, inodes, dent_node, long=True, longts=False):
    inode = inodes[dent_node.inum]
    if long:
        fl = file_leng(ubifs, inode)

        lnk = ""
        if dent_node.type == UBIFS_ITYPE_LNK:
            lnk = " -> " + inode['ino'].data.decode('utf-8')

        if longts:
            mtime = inode['ino'].mtime_sec
        else:
            mtime = time.strftime("%b %d %H:%M", time.gmtime(inode['ino'].mtime_sec))

        print('%6o %2d %s %s %7d %s %s%s' % (inode['ino'].mode, inode['ino'].nlink, inode['ino'].uid, inode['ino'].gid, fl, mtime, dent_node.name, lnk))
    else:
        print(dent_node.name)


def file_leng(ubifs, inode):
    fl = 0
    if 'data' in inode:
        compr_type = 0
        sorted_data = sorted(inode['data'], key=lambda x: x.key['khash'])
        last_khash = sorted_data[0].key['khash']-1

        for data in sorted_data:
            if data.key['khash'] - last_khash != 1:
                while 1 != (data.key['khash'] - last_khash):
                    last_khash += 1
                    fl = fl + UBIFS_BLOCK_SIZE
            fl = fl + data.size
        return fl
    return 0


def _process_reg_file(ubifs, inode, path):
    try:
        buf = bytearray()
        if 'data' in inode:
            compr_type = 0
            sorted_data = sorted(inode['data'], key=lambda x: x.key['khash'])
            last_khash = sorted_data[0].key['khash']-1

            for data in sorted_data:
                
                # If data nodes are missing in sequence, fill in blanks
                # with \x00 * UBIFS_BLOCK_SIZE
                if data.key['khash'] - last_khash != 1:
                    while 1 != (data.key['khash'] - last_khash):
                        buf += b'\x00'*UBIFS_BLOCK_SIZE
                        last_khash += 1

                compr_type = data.compr_type
                ubifs.file.seek(data.offset)
                d = ubifs.file.read(data.compr_len)
                buf += decompress(compr_type, data.size, d)
                last_khash = data.key['khash']
                verbose_log(_process_reg_file, 'ino num: %s, compression: %s, path: %s' % (inode['ino'].key['ino_num'], compr_type, path))

    except Exception as e:
        error(_process_reg_file, 'Warn', 'inode num:%s :%s' % (inode['ino'].key['ino_num'], e))
    
    # Pad end of file with \x00 if needed.
    if inode['ino'].size > len(buf):
        buf += b'\x00' * (inode['ino'].size - len(buf))
        
    return bytes(buf)
