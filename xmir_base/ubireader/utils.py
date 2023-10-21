#!/usr/bin/env python
#############################################################
# ubi_reader
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

import re
from ubireader.debug import error, log
from ubireader.ubi.defines import UBI_EC_HDR_MAGIC, FILE_CHUNK_SZ
from ubireader.ubifs.defines import UBIFS_NODE_MAGIC, UBIFS_SB_NODE_SZ, UBIFS_SB_NODE, UBIFS_COMMON_HDR_SZ
from ubireader.ubifs import nodes

def guess_start_offset(path, guess_offset=0):
    file_offset = guess_offset

    f = open(path, 'rb')
    f.seek(0,2)
    file_size = f.tell()+1
    f.seek(guess_offset)

    for _ in range(0, file_size, FILE_CHUNK_SZ):
        buf = f.read(FILE_CHUNK_SZ)
        ubi_loc = buf.find(UBI_EC_HDR_MAGIC)
        ubifs_loc = buf.find(UBIFS_NODE_MAGIC)

        if ubi_loc == -1 and ubifs_loc == -1:
            file_offset += FILE_CHUNK_SZ
            continue
        else:
            if ubi_loc == -1:
                ubi_loc = file_size + 1
            elif ubifs_loc == -1:
                ubifs_loc = file_size + 1

            if ubi_loc < ubifs_loc:
                log(guess_start_offset, 'Found UBI magic number at %s' % (file_offset + ubi_loc))
                return  file_offset + ubi_loc

            elif ubifs_loc < ubi_loc:
                log(guess_start_offset, 'Found UBIFS magic number at %s' % (file_offset + ubifs_loc))
                return file_offset + ubifs_loc
            else:
                error(guess_start_offset, 'Fatal', 'Could not determine start offset.')
    else:
        error(guess_start_offset, 'Fatal', 'Could not determine start offset.')

    f.close()


def guess_filetype(path, start_offset=0):
    log(guess_filetype, 'Looking for file type at %s' % start_offset)

    with open(path, 'rb') as f:
        f.seek(start_offset)
        buf = f.read(4)

        if buf == UBI_EC_HDR_MAGIC:
            ftype = UBI_EC_HDR_MAGIC
            log(guess_filetype, 'File looks like a UBI image.')

        elif buf == UBIFS_NODE_MAGIC:
            ftype = UBIFS_NODE_MAGIC
            log(guess_filetype, 'File looks like a UBIFS image.')
        else:
            ftype = None
            error(guess_filetype, 'Fatal', 'Could not determine file type.')
    
    return ftype


def guess_leb_size(path):
    """Get LEB size from superblock

    Arguments:
    Str:path    -- Path to file.
    
    Returns:
    Int         -- LEB size.
    
    Searches file for superblock and retrieves leb size.
    """

    f = open(path, 'rb')
    f.seek(0,2)
    file_size = f.tell()+1
    f.seek(0)
    block_size = None

    for _ in range(0, file_size, FILE_CHUNK_SZ):
        buf = f.read(FILE_CHUNK_SZ)

        for m in re.finditer(UBIFS_NODE_MAGIC, buf):
            start = m.start()
            chdr = nodes.common_hdr(buf[start:start+UBIFS_COMMON_HDR_SZ])

            if chdr and chdr.node_type == UBIFS_SB_NODE:
                sb_start = start + UBIFS_COMMON_HDR_SZ
                sb_end = sb_start + UBIFS_SB_NODE_SZ

                if chdr.len != len(buf[sb_start:sb_end]):
                    f.seek(sb_start)
                    buf = f.read(UBIFS_SB_NODE_SZ)
                else:
                    buf = buf[sb_start:sb_end]

                sbn = nodes.sb_node(buf)
                block_size = sbn.leb_size
                f.close()
                return block_size

    f.close()
    return block_size


def guess_peb_size(path):
    """Determine the most likely block size

    Arguments:
    Str:path    -- Path to file.
    
    Returns:
    Int         -- PEB size.
    
    Searches file for Magic Number, picks most 
        common length between them.
    """
    file_offset = 0
    offsets = []
    f = open(path, 'rb')
    f.seek(0,2)
    file_size = f.tell()+1
    f.seek(0)

    for _ in range(0, file_size, FILE_CHUNK_SZ):
        buf = f.read(FILE_CHUNK_SZ)
        for m in re.finditer(UBI_EC_HDR_MAGIC, buf):
            start = m.start()

            if not file_offset:
                file_offset = start
                idx = start
            else:
                idx = start+file_offset

            offsets.append(idx)

        file_offset += FILE_CHUNK_SZ
    f.close()

    occurrences = {}
    for i in range(0, len(offsets)):
        try:
            diff = offsets[i] - offsets[i-1]
        except:
            diff = offsets[i]

        if diff not in occurrences:
            occurrences[diff] = 0

        occurrences[diff] += 1

    most_frequent = 0
    block_size = None

    for offset in occurrences:
        if occurrences[offset] > most_frequent:
            most_frequent = occurrences[offset]
            block_size = offset

    return block_size