#!/usr/bin/env python
#############################################################
# ubi_reader/ubifs
# (c) 2013 Jason Pruitt (jrspruitt@gmail.com)
#
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
import struct

from ubireader import settings
from ubireader.ubifs.defines import *
from ubireader.ubifs import walk
from ubireader.ubifs.misc import decompress
from ubireader.debug import error, log, verbose_log

def is_safe_path(basedir, path):
    basedir = os.path.realpath(basedir)
    path = os.path.realpath(os.path.join(basedir, path))
    return True if path.startswith(basedir) else False


def extract_files(ubifs, out_path, perms=False):
    """Extract UBIFS contents to_path/

    Arguments:
    Obj:ubifs    -- UBIFS object.
    Str:out_path  -- Path to extract contents to.
    """
    try:
        inodes = {}
        bad_blocks = []

        walk.index(ubifs, ubifs.master_node.root_lnum, ubifs.master_node.root_offs, inodes, bad_blocks)

        if len(inodes) < 2:
            raise Exception('No inodes found')

        for dent in inodes[1]['dent']:
            extract_dents(ubifs, inodes, dent, out_path, perms)

        if len(bad_blocks):
            error(extract_files, 'Warn', 'Data may be missing or corrupted, bad blocks, LEB [%s]' % ','.join(map(str, bad_blocks)))

    except Exception as e:
        error(extract_files, 'Error', '%s' % e)


def extract_dents(ubifs, inodes, dent_node, path='', perms=False):
    if dent_node.inum not in inodes:
        error(extract_dents, 'Error', 'inum: %s not found in inodes' % (dent_node.inum))
        return

    inode = inodes[dent_node.inum]

    if not is_safe_path(path, dent_node.name):
        error(extract_dents, 'Warn', 'Path traversal attempt: %s, discarding.' % (dent_node.name))
        return
    dent_path = os.path.realpath(os.path.join(path, dent_node.name))

    if dent_node.type == UBIFS_ITYPE_DIR:
        try:
            if not os.path.exists(dent_path):
                os.mkdir(dent_path)
                log(extract_dents, 'Make Dir: %s' % (dent_path))

                if perms:
                    _set_file_perms(dent_path, inode)
        except Exception as e:
            error(extract_dents, 'Warn', 'DIR Fail: %s' % e)

        if 'dent' in inode:
            for dnode in inode['dent']:
                extract_dents(ubifs, inodes, dnode, dent_path, perms)

        _set_file_timestamps(dent_path, inode)

    elif dent_node.type == UBIFS_ITYPE_REG:
        try:
            if inode['ino'].nlink > 1:
                if 'hlink' not in inode:
                    inode['hlink'] = dent_path
                    buf = _process_reg_file(ubifs, inode, dent_path)
                    _write_reg_file(dent_path, buf)
                else:
                    os.link(inode['hlink'], dent_path)
                    log(extract_dents, 'Make Link: %s > %s' % (dent_path, inode['hlink']))
            else:
                buf = _process_reg_file(ubifs, inode, dent_path)
                _write_reg_file(dent_path, buf)

            _set_file_timestamps(dent_path, inode)

            if perms:
                _set_file_perms(dent_path, inode)

        except Exception as e:
            error(extract_dents, 'Warn', 'FILE Fail: %s' % e)

    elif dent_node.type == UBIFS_ITYPE_LNK:
        try:
            # probably will need to decompress ino data if > UBIFS_MIN_COMPR_LEN
            os.symlink('%s' % inode['ino'].data.decode('utf-8'), dent_path)
            log(extract_dents, 'Make Symlink: %s > %s' % (dent_path, inode['ino'].data))

        except Exception as e:
            error(extract_dents, 'Warn', 'SYMLINK Fail: %s' % e) 

    elif dent_node.type in [UBIFS_ITYPE_BLK, UBIFS_ITYPE_CHR]:
        try:
            dev = struct.unpack('<II', inode['ino'].data)[0]
            if not settings.use_dummy_devices:
                os.mknod(dent_path, inode['ino'].mode, dev)
                log(extract_dents, 'Make Device Node: %s' % (dent_path))

                if perms:
                    _set_file_perms(dent_path, inode)
            else:
                log(extract_dents, 'Create dummy device.')
                _write_reg_file(dent_path, str(dev))

                if perms:
                    _set_file_perms(dent_path, inode)
                
        except Exception as e:
            error(extract_dents, 'Warn', 'DEV Fail: %s' % e)

    elif dent_node.type == UBIFS_ITYPE_FIFO:
        try:
            os.mkfifo(dent_path, inode['ino'].mode)
            log(extract_dents, 'Make FIFO: %s' % (path))

            if perms:
                _set_file_perms(dent_path, inode)
        except Exception as e:
            error(extract_dents, 'Warn', 'FIFO Fail: %s : %s' % (dent_path, e))

    elif dent_node.type == UBIFS_ITYPE_SOCK:
        try:
            if settings.use_dummy_socket_file:
                _write_reg_file(dent_path, '')
                if perms:
                    _set_file_perms(dent_path, inode)
        except Exception as e:
            error(extract_dents, 'Warn', 'SOCK Fail: %s : %s' % (dent_path, e))


def _set_file_perms(path, inode):
    os.chown(path, inode['ino'].uid, inode['ino'].gid)
    os.chmod(path, inode['ino'].mode)
    verbose_log(_set_file_perms, 'perms:%s, owner: %s.%s, path: %s' % (inode['ino'].mode, inode['ino'].uid, inode['ino'].gid, path))

def _set_file_timestamps(path, inode):
    os.utime(path, (inode['ino'].atime_sec, inode['ino'].mtime_sec))
    verbose_log(_set_file_timestamps, 'timestamps: access: %s, modify: %s, path: %s' % (inode['ino'].atime_sec, inode['ino'].mtime_sec, path))

def _write_reg_file(path, data):
    with open(path, 'wb') as f:
        f.write(data)
    log(_write_reg_file, 'Make File: %s' % (path))


def _process_reg_file(ubifs, inode, path):
    try:
        buf = bytearray()
        start_key = 0x00 | (UBIFS_DATA_KEY << UBIFS_S_KEY_BLOCK_BITS)
        if 'data' in inode:
            compr_type = 0
            sorted_data = sorted(inode['data'], key=lambda x: x.key['khash'])
            last_khash = start_key - 1 

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
        error(_process_reg_file, 'Warn', 'inode num:%s path:%s :%s' % (inode['ino'].key['ino_num'], path, e))
    
    # Pad end of file with \x00 if needed.
    if inode['ino'].size > len(buf):
        buf += b'\x00' * (inode['ino'].size - len(buf))
        
    return bytes(buf)
