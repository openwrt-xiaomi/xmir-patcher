#!/usr/bin/env python
#############################################################
# ubi_reader/ubi
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

from ubireader import settings
from ubireader.ubi.defines import PRINT_COMPAT_LIST, PRINT_VOL_TYPE_LIST, UBI_VTBL_AUTORESIZE_FLG

def ubi(ubi, tab=''):
    buf = '%sUBI File\n' % (tab) 
    buf += '%s---------------------\n' % (tab)
    buf += '\t%sMin I/O: %s\n' % (tab, ubi.min_io_size)
    buf += '\t%sLEB Size: %s\n' % (tab, ubi.leb_size)
    buf += '\t%sPEB Size: %s\n' % (tab, ubi.peb_size)
    buf += '\t%sTotal Block Count: %s\n' % (tab, ubi.block_count)
    buf += '\t%sData Block Count: %s\n' % (tab, len(ubi.data_blocks_list))
    buf += '\t%sLayout Block Count: %s\n' % (tab, len(ubi.layout_blocks_list))
    buf += '\t%sInternal Volume Block Count: %s\n' % (tab, len(ubi.int_vol_blocks_list))
    buf += '\t%sUnknown Block Count: %s\n' % (tab, len(ubi.unknown_blocks_list))
    buf += '\t%sFirst UBI PEB Number: %s\n' % (tab, ubi.first_peb_num)
    return buf


def image(image, tab=''):
    buf = '%s%s\n' % (tab, image)
    buf += '%s---------------------\n' % (tab)
    buf += '\t%sImage Sequence Num: %s\n' % (tab, image.image_seq)
    for volume in image.volumes:
        buf += '\t%sVolume Name:%s\n' % (tab, volume)
    buf += '\t%sPEB Range: %s - %s\n' % (tab, image.peb_range[0], image.peb_range[1])
    return buf


def volume(volume, tab=''):
    buf = '%s%s\n' % (tab, volume)
    buf += '%s---------------------\n' % (tab)
    buf += '\t%sVol ID: %s\n' % (tab, volume.vol_id)
    buf += '\t%sName: %s\n' % (tab, volume.name.decode('utf-8'))
    buf += '\t%sBlock Count: %s\n' % (tab, volume.block_count)

    buf += '\n'
    buf += '\t%sVolume Record\n' % (tab) 
    buf += '\t%s---------------------\n' % (tab)
    buf += vol_rec(volume.vol_rec, '\t\t%s' % tab)

    buf += '\n'
    return buf


def block(block, tab='\t'):
    buf = '%s%s\n' % (tab, block)
    buf += '%s---------------------\n' % (tab)
    buf += '\t%sFile Offset: %s\n' %  (tab, block.file_offset)
    buf += '\t%sPEB #: %s\n' % (tab, block.peb_num)
    buf += '\t%sLEB #: %s\n' % (tab, block.leb_num)
    buf += '\t%sBlock Size: %s\n' % (tab, block.size)
    buf += '\t%sInternal Volume: %s\n' % (tab, block.is_internal_vol)
    buf += '\t%sIs Volume Table: %s\n' % (tab, block.is_vtbl)
    buf += '\t%sIs Valid: %s\n' % (tab, block.is_valid)

    if not block.ec_hdr.errors or settings.ignore_block_header_errors:
        buf += '\n'
        buf += '\t%sErase Count Header\n' % (tab)
        buf += '\t%s---------------------\n' % (tab)
        buf += ec_hdr(block.ec_hdr, '\t\t%s' % tab)

    if (block.vid_hdr and not block.vid_hdr.errors) or settings.ignore_block_header_errors:
        buf += '\n'        
        buf += '\t%sVID Header\n' % (tab)
        buf += '\t%s---------------------\n' % (tab)
        buf += vid_hdr(block.vid_hdr, '\t\t%s' % tab)

    if block.vtbl_recs:
        buf += '\n'
        buf += '\t%sVolume Records\n' % (tab) 
        buf += '\t%s---------------------\n' % (tab)
        for vol in block.vtbl_recs:
            buf += vol_rec(vol, '\t\t%s' % tab)

    buf += '\n'
    return buf


def ec_hdr(ec_hdr, tab=''):
    buf = ''
    for key, value in ec_hdr:
        if key == 'errors':
            value = ','.join(value)

        elif key == 'hdr_crc':
            value = hex(value)

        buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def vid_hdr(vid_hdr, tab=''):
    buf = ''
    for key, value in vid_hdr:
        if key == 'errors':
            value = ','.join(value)

        elif key == 'hdr_crc':
            value = hex(value)

        elif key == 'compat':
            if value in PRINT_COMPAT_LIST:
                value = PRINT_COMPAT_LIST[value]
            else:
                value = -1

        elif key == 'vol_type':
            if value  < len(PRINT_VOL_TYPE_LIST):
                value = PRINT_VOL_TYPE_LIST[value]
            else:
                value = -1

        buf += '%s%s: %r\n' % (tab, key, value)
    return buf


def vol_rec(vol_rec, tab=''):
    buf = ''
    for key, value in vol_rec:
        if key == 'errors':
            value = ','.join(value)

        elif key == 'crc':
            value = hex(value)

        elif key == 'vol_type':
            if value < len(PRINT_VOL_TYPE_LIST):
                value = PRINT_VOL_TYPE_LIST[value]
            else:
                value = -1

        elif key == 'flags' and value == UBI_VTBL_AUTORESIZE_FLG:
            value = 'autoresize'

        elif key == 'name':
            value = value.strip(b'\x00').decode('utf-8')

        elif key == 'padding':
            value = value.decode('utf-8')

        buf += '%s%s: %r\n' % (tab, key, value)
    return buf
