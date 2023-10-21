#!/usr/bin/env python
#############################################################
# ubi_reader/ubifs/display
# (c) 2014 Jason Pruitt (jrspruitt@gmail.com)
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

from ubireader.ubifs.defines import PRINT_UBIFS_FLGS, PRINT_UBIFS_MST

def ubifs(ubifs, tab=''):
    buf = '%sUBIFS Image\n' % (tab)
    buf += '%s---------------------\n' % (tab)
    buf += '%sMin I/O: %s\n' % (tab, ubifs.min_io_size)
    buf += '%sLEB Size: %s\n' % (tab, ubifs.leb_size)
    return buf

def common_hdr(chdr, tab=''):
    buf = '%s%s\n' % (tab, chdr)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in chdr:
        if key == 'display':
            continue
        elif key == 'crc':
            buf += '%s%s: 0x%x\n' % (tab, key, value)
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf

def sb_node(node, tab=''):
    buf = '%s%s\n' % (tab, node)
    buf += '%sFile offset: %s\n' % (tab, node.file_offset)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in node:
        if key == 'display':
            continue
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        elif key == 'uuid':
            buf += '%s%s: %r\n' % (tab, key, value)
        elif key == 'flags':
            flags = ''
            for flag in PRINT_UBIFS_FLGS:
                if value & flag[0]:
                    flags += '%s, ' % flag[1]

            if flags.endswith(', '):
                flags = flags[0:-2]

            buf += '%s%s: %s\n' % (tab, key, flags)

        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def mst_node(node, tab=''):
    buf = '%s%s\n' % (tab, node)
    buf += '%sFile offset: %s\n' % (tab, node.file_offset)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in node:
        if key == 'display':
            continue
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        elif key == 'flags':
            flags = ''
            for flag in PRINT_UBIFS_MST:
                if value & flag[0]:
                    flags += '%s, ' % flag[1]

            if flags.endswith(', '):
                flags = flags[0:-2]

            buf += '%s%s: %s\n' % (tab, key, flags)
        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def dent_node(node, tab=''):
    buf = '%s%s\n' % (tab, node)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in node:
        if key == 'display':
            continue
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def data_node(node, tab=''):
    buf = '%s%s\n' % (tab, node)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in node:
        if key in ['display', 'data']:
            continue
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def idx_node(node, tab=''):
    buf = '%s%s\n' % (tab, node)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in node:
        if key == 'display':
            continue
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def ino_node(node, tab=''):
    buf = '%s%s\n' % (tab, node)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in node:
        if key == 'display':
            continue
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def branch(node, tab=''):
    buf = '%s%s\n' % (tab, node)
    buf += '%s---------------------\n' % (tab)
    tab += '\t'
    for key, value in node:
        if key == 'display':
            continue
        elif key == 'errors':
            buf += '%s%s: %s\n' % (tab, key, ','.join(value))
        else:
            buf += '%s%s: %r\n' % (tab, key, value)
    return buf

