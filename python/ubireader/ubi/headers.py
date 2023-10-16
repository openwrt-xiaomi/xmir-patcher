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

import struct
from zlib import crc32

from ubireader.debug import log
from ubireader.ubi.defines import *

class ec_hdr(object):
    def __init__(self, buf):
        fields = dict(list(zip(EC_HDR_FIELDS, struct.unpack(EC_HDR_FORMAT,buf))))
        for key in fields:
            setattr(self, key, fields[key])
        setattr(self, 'errors', [])

        self._check_errors(buf[:-4])
        
    def __repr__(self):
        return 'Erase Count Header'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def _check_errors(self, buf_crc):
        crc_chk = (~crc32(buf_crc) & UBI_CRC32_INIT)
        if self.hdr_crc != crc_chk:
            log(vid_hdr, 'CRC Failed: expected 0x%x got 0x%x' % (crc_chk, self.hdr_crc))
            self.errors.append('crc')


class vid_hdr(object):
    def __init__(self, buf):
        fields = dict(list(zip(VID_HDR_FIELDS, struct.unpack(VID_HDR_FORMAT,buf))))
        for key in fields:
            setattr(self, key, fields[key])
        setattr(self, 'errors', [])

        self._check_errors(buf[:-4])

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def __repr__(self):
        return 'VID Header'

    def _check_errors(self, buf_crc):
        crc_chk = (~crc32(buf_crc) & UBI_CRC32_INIT)
        if self.hdr_crc != crc_chk:
            log(vid_hdr, 'CRC Failed: expected 0x%x got 0x%x' % (crc_chk, self.hdr_crc))
            self.errors.append('crc')


def vtbl_recs(buf):
    data_buf = buf
    vtbl_recs = []
    vtbl_rec_ret = ''

    for i in range(0, UBI_MAX_VOLUMES):    
        offset = i*UBI_VTBL_REC_SZ
        vtbl_rec_buf = data_buf[offset:offset+UBI_VTBL_REC_SZ]
        
        if len(vtbl_rec_buf) == UBI_VTBL_REC_SZ:
            vtbl_rec_ret = _vtbl_rec(vtbl_rec_buf)

            if len(vtbl_rec_ret.errors) == 0 and vtbl_rec_ret.name_len:
                vtbl_rec_ret.rec_index = i
                vtbl_recs.append(vtbl_rec_ret)

    return vtbl_recs


class _vtbl_rec(object):
    def __init__(self, buf):
        fields = dict(list(zip(VTBL_REC_FIELDS, struct.unpack(VTBL_REC_FORMAT,buf))))
        for key in fields:
            setattr(self, key, fields[key])
        setattr(self, 'errors', [])
        setattr(self, 'rec_index', -1)

        self.name = self.name[0: self.name_len]
        self._check_errors(buf[:-4])

    def __repr__(self):
        return 'Volume Table Record: %s' % getattr(self, 'name')

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def _check_errors(self, buf_crc):
        if self.crc != (~crc32(buf_crc) & 0xFFFFFFFF):
            self.errors.append('crc')
