#!/usr/bin/env python
#############################################################
# ubi_reader/ubi_io
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

from ubireader.debug import error, log, verbose_log
from ubireader.ubi.block import sort

class ubi_file(object):
    """UBI image file object

    Arguments:
    Str:path         -- Path to file to parse
    Int:block_size   -- Erase block size of NAND in bytes.
    Int:start_offset -- (optional) Where to start looking in the file for
                        UBI data.
    Int:end_offset   -- (optional) Where to stop looking in the file.
    
    Methods:
    seek            -- Put file head to specified byte offset.
        Int:offset
    read            -- Read specified bytes from file handle.
        Int:size
    tell            -- Returns byte offset of current file location.
    read_block      -- Returns complete PEB data of provided block
                       description.
        Obj:block
    read_block_data -- Returns LEB data only from provided block.
        Obj:block
    reader          -- Generator that returns data from file.
    reset           -- Reset file position to start_offset.
    is_valid        -- If the object intialized okay.

    Handles all the actual file interactions, read, seek,
    extract blocks, etc.
    """

    def __init__(self, path, block_size, start_offset=0, end_offset=None):
        self.__name__ = 'UBI_File'
        self.is_valid = False
        try:
            log(self, 'Open Path: %s' % path)
            self._fhandle = open(path, 'rb')
        except Exception as e:
            error(self, 'Fatal', 'Open file: %s' % e)

        self._fhandle.seek(0,2)
        file_size = self.tell()
        log(self, 'File Size: %s' % file_size)

        self._start_offset = start_offset
        log(self, 'Start Offset: %s' % (self._start_offset))

        if end_offset:
            self._end_offset = end_offset
        else:
            self._end_offset = file_size
        log(self, 'End Offset: %s' % (self._end_offset))

        self._block_size = block_size
        log(self, 'Block Size: %s' % block_size)

        if start_offset > self._end_offset:
            error(self, 'Fatal', 'Start offset larger than end offset.')

        if ( not end_offset is None ) and ( end_offset > file_size ):
            error(self, 'Fatal', 'End offset larger than file size.')

        remainder = (self._end_offset - start_offset) % block_size
        if remainder != 0:
            error(self, 'Warning', 'end_offset - start_offset length is not block aligned, could mean missing data.')

        self._fhandle.seek(self._start_offset)
        self._last_read_addr = self._fhandle.tell()
        self.is_valid = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _set_start(self, i):
        self._start_offset = i
    def _get_start(self):
        return self._start_offset
    start_offset = property(_get_start, _set_start)


    def _get_end(self):
        return self._end_offset
    end_offset = property(_get_end)


    def _get_block_size(self):
        return self._block_size
    block_size = property(_get_block_size)

    def close(self):
        self._fhandle.close()

    def seek(self, offset):
        self._fhandle.seek(offset)


    def read(self, size):
        self._last_read_addr = self.tell()
        verbose_log(self, 'read loc: %s, size: %s' % (self._last_read_addr, size))
        return self._fhandle.read(size)


    def tell(self):
        return self._fhandle.tell()


    def last_read_addr(self):
        return self._last_read_addr


    def reset(self):
        self._fhandle.seek(self.start_offset)


    def reader(self):
        self.reset()
        while True:
            cur_loc = self._fhandle.tell()
            if self.end_offset and cur_loc > self.end_offset:
                break            
            elif self.end_offset and self.end_offset - cur_loc < self.block_size:
                chunk_size = self.end_offset - cur_loc
            else:
                chunk_size = self.block_size

            buf = self.read(chunk_size)

            if not buf:
                break
            yield buf


    def read_block(self, block):
        """Read complete PEB data from file.
        
        Argument:
        Obj:block -- Block data is desired for.
        """
        self.seek(block.file_offset)
        return self._fhandle.read(block.size)


    def read_block_data(self, block):
        """Read LEB data from file
        
        Argument:
        Obj:block -- Block data is desired for.
        """
        self.seek(block.file_offset + block.ec_hdr.data_offset)
        buf = self._fhandle.read(block.size - block.ec_hdr.data_offset - block.vid_hdr.data_pad)
        return buf



class leb_virtual_file():
    def __init__(self, ubi, block_list):
        self.__name__ = 'leb_virtual_file'
        self.is_valid = False
        self._ubi = ubi
        self._last_read_addr = 0

        if not len(block_list):
            error(self, 'Info', 'Empty block list')
        else:
            self._blocks = sort.by_leb(block_list)
            self._seek = 0
            self._last_leb = -1
            self._last_buf = ''
            self.is_valid = True


    def read(self, size):
        buf = ''
        leb = int(self.tell() / self._ubi.leb_size)
        offset = self.tell() % self._ubi.leb_size

        try:
            if size < 0:
                raise Exception('Bad Read Offset Request')

            self._last_read_addr = self._ubi.blocks[self._blocks[leb]].file_offset + self._ubi.blocks[self._blocks[leb]].ec_hdr.data_offset + offset

        except Exception as e:
            error(self.read, 'Error', 'LEB: %s is corrupted or has no data.' % (leb))
            raise Exception('Bad Read Offset Request')

        verbose_log(self, 'read loc: %s, size: %s' % (self._last_read_addr, size))

        if leb == self._last_leb:
            self.seek(self.tell() + size)
            return self._last_buf[offset:offset+size]
        else:
            try:
                buf = self._ubi.file.read_block_data(self._ubi.blocks[self._blocks[leb]])
                self._last_buf = buf
                self._last_leb = leb
                self.seek(self.tell() + size)
                return buf[offset:offset+size]
            except Exception as e:
                error(self, 'Fatal', 'read loc: %s, size: %s, LEB: %s, offset: %s, error: %s' % (self._last_read_addr, size, leb, offset, e))


    def reset(self):
        self.seek(0)


    def seek(self, offset):
        self._seek = offset


    def tell(self):
        return self._seek


    def last_read_addr(self):
        """Start address of last physical file read"""
        return self._last_read_addr


    def reader(self):
        last_leb = 0
        for block in self._blocks:
            while 0 != (self._ubi.blocks[block].leb_num - last_leb):
                last_leb += 1
                yield b'\xff'*self._ubi.leb_size

            last_leb += 1
            yield self._ubi.file.read_block_data(self._ubi.blocks[block])
