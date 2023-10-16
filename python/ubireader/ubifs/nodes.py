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

from ubireader.ubifs.misc import parse_key
from ubireader.ubifs.defines import *
from ubireader.ubifs import display

class common_hdr(object):
    """Get common header at given LEB number + offset.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.

    See ubifs/defines.py for object attributes.
    """
    def __init__(self, buf):

        fields = dict(list(zip(UBIFS_COMMON_HDR_FIELDS, struct.unpack(UBIFS_COMMON_HDR_FORMAT, buf))))
        for key in fields:
            setattr(self, key, fields[key])

        setattr(self, 'errors', [])
        
    def __repr__(self):
        return 'UBIFS Common Header'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.common_hdr(self, tab)


class ino_node(object):
    """Get inode node at given LEB number + offset.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.

    See ubifs/defines.py for object attributes.
    """
    def __init__(self, buf):

        fields = dict(list(zip(UBIFS_INO_NODE_FIELDS, struct.unpack(UBIFS_INO_NODE_FORMAT, buf[0:UBIFS_INO_NODE_SZ]))))
        for key in fields:
            if key == 'key':
                setattr(self, key, parse_key(fields[key]))
            else:
                setattr(self, key, fields[key])

        setattr(self, 'data', buf[UBIFS_INO_NODE_SZ:])
        setattr(self, 'errors', [])

    def __repr__(self):
        return 'UBIFS Ino Node'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.ino_node(self, tab)


class dent_node(object):
    """Get dir entry node at given LEB number + offset.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.

    See ubifs/defines.py for object attributes.
    """
    def __init__(self, buf):
        fields = dict(list(zip(UBIFS_DENT_NODE_FIELDS, struct.unpack(UBIFS_DENT_NODE_FORMAT, buf[0:UBIFS_DENT_NODE_SZ]))))
        for key in fields:
            if key == 'key':
                setattr(self, key, parse_key(fields[key]))
            else:
                setattr(self, key, fields[key])

        setattr(self, 'name', '%s' % buf[-self.nlen-1:-1].decode('utf-8'))
        setattr(self, 'errors', [])

    def __repr__(self):
        return 'UBIFS Directory Entry Node'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.dent_node(self, tab)


class data_node(object):
    """Get data node at given LEB number + offset.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.
    Int:offset  -- Offset in LEB of data node.

    See ubifs/defines.py for object attributes.
    """
    def __init__(self, buf, file_offset):

        fields = dict(list(zip(UBIFS_DATA_NODE_FIELDS, struct.unpack(UBIFS_DATA_NODE_FORMAT, buf[0:UBIFS_DATA_NODE_SZ]))))
        for key in fields:
            if key == 'key':
                setattr(self, key, parse_key(fields[key]))
            else:
                setattr(self, key, fields[key])

        setattr(self, 'offset', file_offset)
        setattr(self, 'compr_len', (len(buf) - UBIFS_DATA_NODE_SZ))
        setattr(self, 'errors', [])

    def __repr__(self):
        return 'UBIFS Data Node'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.data_node(self, tab)


class idx_node(object):
    """Get index node at given LEB number + offset.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.

    See ubifs/defines.py for object attributes.
    """
    def __init__(self, buf):
        fields = dict(list(zip(UBIFS_IDX_NODE_FIELDS, struct.unpack(UBIFS_IDX_NODE_FORMAT, buf[0:UBIFS_IDX_NODE_SZ]))))
        for key in fields:
            setattr(self, key, fields[key])

        idxs = UBIFS_IDX_NODE_SZ
        brs = UBIFS_BRANCH_SZ
        setattr(self, 'branches', [branch(buf[idxs+(brs*i):idxs+(brs*i)+brs]) for i in range(0, self.child_cnt)])
        setattr(self, 'errors', [])

    def __repr__(self):
        return 'UBIFS Index Node'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.idx_node(self, tab)


class branch(object):
    """ Create branch from given idx_node data buf.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.
    """
    def __init__(self, buf):
        fields = dict(list(zip(UBIFS_BRANCH_FIELDS, struct.unpack(UBIFS_BRANCH_FORMAT, buf))))
        for key in fields:
            if key == 'key':
                setattr(self, key, parse_key(fields[key]))
            else:
                setattr(self, key, fields[key])

        setattr(self, 'errors', [])

    def __repr__(self):
        return 'UBIFS Branch'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.branch(self, tab)
    

class sb_node(object):
    """Get superblock node at given LEB number + offset.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.
    Int:offset  -- Offset in LEB of data node.

    See ubifs/defines.py for object attributes.
    """
    def __init__(self, buf, file_offset=-1):
        self.file_offset = file_offset
        fields = dict(list(zip(UBIFS_SB_NODE_FIELDS, struct.unpack(UBIFS_SB_NODE_FORMAT, buf))))
        for key in fields:
            setattr(self, key, fields[key])

        setattr(self, 'errors', [])

    def __repr__(self):
        return 'UBIFS Super Block Node'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.sb_node(self, tab)


class mst_node(object):
    """Get master node at given LEB number + offset.

    Arguments:
    Bin:buf     -- Raw data to extract header information from.
    Int:offset  -- Offset in LEB of data node.

    See ubifs/defines.py for object attributes.
    """
    def __init__(self, buf, file_offset=-1):
        self.file_offset = file_offset
        fields = dict(list(zip(UBIFS_MST_NODE_FIELDS, struct.unpack(UBIFS_MST_NODE_FORMAT, buf))))
        for key in fields:
            setattr(self, key, fields[key])

        setattr(self, 'errors', [])

    def __repr__(self):
        return 'UBIFS Master Block Node'

    def __iter__(self):
        for key in dir(self):
            if not key.startswith('_'):
                yield key, getattr(self, key)

    def display(self, tab=''):
        return display.mst_node(self, tab)
