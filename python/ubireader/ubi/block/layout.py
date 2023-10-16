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

from ubireader.debug import log
from ubireader.ubi.block import sort

def group_pairs(blocks, layout_blocks_list):
    """Sort a list of layout blocks into pairs

    Arguments:
    List:blocks        -- List of block objects
    List:layout_blocks -- List of layout block indexes

    Returns:
    List -- Layout block pair indexes grouped in a list
    """

    image_dict={}
    for block_id in layout_blocks_list:
        image_seq=blocks[block_id].ec_hdr.image_seq
        if image_seq not in image_dict:
            image_dict[image_seq]=[block_id]
        else:
            image_dict[image_seq].append(block_id)

    log(group_pairs, 'Layout blocks found at PEBs: %s' % list(image_dict.values()))

    return list(image_dict.values())


def associate_blocks(blocks, layout_pairs):
    """Group block indexes with appropriate layout pairs

    Arguments:
    List:blocks        -- List of block objects
    List:layout_pairs  -- List of grouped layout blocks

    Returns:
    List -- Layout block pairs grouped with associated block ranges.
    """

    seq_blocks = []
    for layout_pair in layout_pairs:
        seq_blocks = sort.by_image_seq(blocks, blocks[layout_pair[0]].ec_hdr.image_seq)
        seq_blocks = [b for b in seq_blocks if b not in layout_pair]
        layout_pair.append(seq_blocks)

    return layout_pairs
