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

from ubireader.debug import error
from ubireader.ubi.block import sort, extract_blocks
from ubireader.ubi import display
from ubireader.ubi.image import description as image
from ubireader.ubi.block import layout, rm_old_blocks

class ubi_base(object):
    """UBI Base object

    Arguments:
    Obj:image       -- UBI image object 
    
    Attributes:
    ubi_file:file      -- ubi_file object
    Int:block_count    -- Number of blocks found.
    Int:first_peb_num  -- Number of the first UBI PEB in file.
    Int:leb_size       -- Size of Logical Erase Blocks.
    Int:peb_size       -- Size of Physical Erase Blocks.
    Int:min_io         -- Size of min I/O from vid_hdr_offset.
    Dict:blocks        -- Dict keyed by PEB number of all blocks.
    """

    def __init__(self, ubi_file):
        self.__name__ = 'UBI'
        self._file = ubi_file
        self._first_peb_num = 0
        self._blocks = extract_blocks(self)
        self._block_count = len(self.blocks)

        if self._block_count <= 0:
            error(self, 'Fatal', 'No blocks found.')

        arbitrary_block = next(iter(self.blocks.values()))
        self._min_io_size = arbitrary_block.ec_hdr.vid_hdr_offset
        self._leb_size = self.file.block_size - arbitrary_block.ec_hdr.data_offset


    def _get_file(self):
        """UBI File object

        Returns:
        Obj -- UBI File object.
        """
        return self._file
    file = property(_get_file)


    def _get_block_count(self):
        """Total amount of UBI blocks in file.

        Returns:
        Int -- Number of blocks
        """
        return self._block_count
    block_count = property(_get_block_count)


    def _set_first_peb_num(self, i):
        self._first_peb_num = i
    def _get_first_peb_num(self):
        """First Physical Erase Block with UBI data
        
        Returns:
        Int -- Number of the first PEB.
        """
        return self._first_peb_num
    first_peb_num = property(_get_first_peb_num, _set_first_peb_num)


    def _get_leb_size(self):
        """LEB size of UBI blocks in file.

        Returns:
        Int -- LEB Size.
        """
        return self._leb_size
    leb_size = property(_get_leb_size)


    def _get_peb_size(self):
        """PEB size of UBI blocks in file.

        Returns:
        Int -- PEB Size.
        """
        return self.file.block_size
    peb_size = property(_get_peb_size)


    def _get_min_io_size(self):
        """Min I/O Size

        Returns:
        Int -- Min I/O Size.
        """
        return self._min_io_size
    min_io_size = property(_get_min_io_size)


    def _get_blocks(self):
        """Main Dict of UBI Blocks

        Passed around for lists of indexes to be made or to be returned
        filtered through a list. So there isn't multiple copies of blocks,
        as there can be thousands.
        """
        return self._blocks
    blocks = property(_get_blocks)


class ubi(ubi_base):
    """UBI object

    Arguments:
    Obj:ubi_file             -- UBI file object.

    Attributes:
    Inherits:ubi_base         -- ubi_base attributes.
    List:images               -- List of UBI image objects.
    List:data_blocks_list     -- List of all data blocks in file.
    List:layout_blocks_list   -- List of all layout blocks in file.
    List:int_vol_blocks_list  -- List of internal volumes minus layout.
    List:unknown_blocks_list  -- List of blocks with unknown types. *
    """

    def __init__(self, ubi_file):
        super(ubi, self).__init__(ubi_file)

        layout_list, data_list, int_vol_list, unknown_list = sort.by_type(self.blocks)

        self._layout_blocks_list = layout_list
        self._data_blocks_list = data_list
        self._int_vol_blocks_list = int_vol_list
        self._unknown_blocks_list = unknown_list
        
        newest_layout_list = rm_old_blocks(self.blocks, self.layout_blocks_list)
        
        if len(newest_layout_list) < 2:
            error(self, 'Fatal', 'Less than 2 layout blocks found.')

        layout_pairs = layout.group_pairs(self.blocks, newest_layout_list)

        layout_infos = layout.associate_blocks(self.blocks, layout_pairs)

        self._images = []
        for i in range(0, len(layout_infos)):
            self._images.append(image(self.blocks, layout_infos[i]))


    def _get_images(self):
        """Get UBI images.

        Returns:
        List -- Of volume objects groupled by image.
        """
        return self._images
    images = property(_get_images)


    def _get_data_blocks_list(self):
        """Get all UBI blocks found in file that are data blocks.

        Returns:
        List -- List of block objects.
        """
        return self._data_blocks_list
    data_blocks_list = property(_get_data_blocks_list)


    def _get_layout_blocks_list(self):
        """Get all UBI blocks found in file that are layout volume blocks.

        Returns:
        List -- List of block objects.
        """
        return self._layout_blocks_list
    layout_blocks_list = property(_get_layout_blocks_list)


    def _get_int_vol_blocks_list(self):
        """Get all UBI blocks found in file that are internal volume blocks.

        Returns:
        List -- List of block objects.

        This does not include layout blocks.
        """
        return self._int_vol_blocks_list
    int_vol_blocks_list = property(_get_int_vol_blocks_list)


    def _get_unknown_blocks_list(self):
        """Get all UBI blocks found in file of unknown type..

        Returns:
        List -- List of block objects.
        """
        return self._unknown_blocks_list
    unknown_blocks_list = property(_get_unknown_blocks_list)
    
    def display(self, tab=''):
        """Print information about this object.
        
        Argument:
        Str:tab    -- '\t' for spacing this object.
        """
        return display.ubi(self, tab)
