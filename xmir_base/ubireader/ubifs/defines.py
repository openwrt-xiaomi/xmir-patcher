#!/usr/bin/env python
# -*- coding: utf-8 -*-
#############################################################
# Adapted in part from linux-source-3.2/fs/ubi/ubi-media.h
# for use in Python.
# Oct. 2013 by Jason Pruitt
#
# Original copyright notice.
# --------------------------
#
# This file is part of UBIFS.
#
# Copyright (C) 2006-2008 Nokia Corporation.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# Authors: Artem Bityutskiy (Битюцкий Артём)
#          Adrian Hunter
#
#############################################################

import struct

# Constant defines

# Common Header.
UBIFS_NODE_MAGIC = b'\x31\x18\x10\x06' # Set to LSB

# Initial CRC32 value.
UBIFS_CRC32_INIT = 0xFFFFFFFF

# Do not compress data smaller than this.
UBIFS_MIN_COMPR_LEN = 128

# If difference between compressed data length and compressed data
# length, is less than this, do not compress data.
UBIFS_MIN_COMPRESS_DIFF = 64

# Root inode number
UBIFS_ROOT_INO = 1

# Lowest inode number for regular inodes, non-internal inodes.
UBIFS_FIRST_INO = 64

# Max file name and extended attr length (muptple of 8 minus 1.
UBIFS_MAX_NLEN = 255

# Max number of data journal heads.
UBIFS_MAX_JHEADS = 1

# Max data node data length/amount attached to inode node.
UBIFS_BLOCK_SIZE = 4096
UBIFS_BLOCK_SHIFT = 12

# UBIFS padding byte pattern.
UBIFS_PADDING_BYTE = b'\xCE'

# Max key length
UBIFS_MAX_KEY_LEN = 16

# Key length of simple format.
UBIFS_SK_LEN = 8

# Min index tree fanout.
UBIFS_MIN_FANOUT = 3

# Max number of levels in UBIFS indexing B-tree.
UBIFS_MAX_LEVELS = 512

# Max amount of data attached to inode in bytes.
UBIFS_MAX_INO_DATA = UBIFS_BLOCK_SIZE

# LEB Properties Tree fanout (power of 2) and fanout.
UBIFS_LPT_FANOUT = 4
UBIFS_LPT_FANOUT_SHIFT = 2

# LEB Properties Tree bit field sizes.
UBIFS_LPT_CRC_BITS  = 16
UBIFS_LPT_CRC_BYTES = 2
UBIFS_LPT_TYPE_BITS = 4

# LEB Properties Tree node types.
UBIFS_LPT_PNODE         = 0 # LPT leaf node (contains LEB Properties)
UBIFS_LPT_NNODE         = 1 # LPT internal node
UBIFS_LPT_LTAB          = 2 # LPT's own lprops table
UBIFS_LPT_LSAVE         = 3 # LPT's save table (big model only)
UBIFS_LPT_NODE_CNT      = 4 # count of LPT node types
UBIFS_LPT_NOT_A_NODE = (1 << UBIFS_LPT_TYPE_BITS) - 1 # 4 bits of 1

# Inode types
UBIFS_ITYPE_REG  = 0 # Regular file
UBIFS_ITYPE_DIR  = 1 # Directory
UBIFS_ITYPE_LNK  = 2 # Soft link
UBIFS_ITYPE_BLK  = 3 # Block device node
UBIFS_ITYPE_CHR  = 4 # Char device node
UBIFS_ITYPE_FIFO = 5 # FIFO
UBIFS_ITYPE_SOCK = 6 # Socket
UBIFS_ITYPES_CNT = 7 # Support file type count

# Supported key has functions
UBIFS_KEY_HASH_R5   = 0 # R5 hash
UBIFS_KEY_HASH_TEST = 1 # Test hash, returns first 4 bytes of name
PRINT_UBIFS_KEY_HASH = ['r5', 'test']

# Supported key formats
UBIFS_SIMPLE_KEY_FMT = 0

# Simple key format uses 29 bits for storing UBIFS name and hash.
UBIFS_S_KEY_BLOCK_BITS = 29
UBIFS_S_KEY_BLOCK_MASK = 0x1FFFFFFF
UBIFS_S_KEY_HASH_BITS  = UBIFS_S_KEY_BLOCK_BITS
UBIFS_S_KEY_HASH_MASK  = UBIFS_S_KEY_BLOCK_MASK

# Key types
UBIFS_INO_KEY       = 0 # Inode node key
UBIFS_DATA_KEY      = 1 # Data node key
UBIFS_DENT_KEY      = 2 # Directory node key
UBIFS_XENT_KEY      = 3 # Extended attribute entry key
UBIFS_KEY_TYPES_CNT = 4 # Supported key count

# Number of reserved LEBs for Superblock area
UBIFS_SB_LEBS = 1

# Number of reserved LEBs for master area
UBIFS_MST_LEBS = 2

# First LEB of the Superblock area
UBIFS_SB_LNUM = 0

# First LEB of the master area
UBIFS_MST_LNUM = (UBIFS_SB_LNUM + UBIFS_SB_LEBS)

# First LEB of log area
UBIFS_LOG_LNUM = (UBIFS_MST_LNUM + UBIFS_MST_LEBS)

# On-flash inode flags
UBIFS_COMPR_FL     = 1  # Use compression for this inode
UBIFS_SYNC_FL      = 2  # Has to be synchronous I/O
UBIFS_IMMUTABLE_FL = 4  # Inode is immutable
UBIFS_APPEND_FL    = 8  # Writes may only append data
UBIFS_DIRSYNC_FL   = 16 # I/O on this directory inode must be synchronous
UBIFS_XATTR_FL     = 32 # This inode is inode for extended attributes

# Inode flag bits used by UBIFS
UBIFS_FL_MASK = 0x0000001F

# Compression alogrithms.
UBIFS_COMPR_NONE            = 0 # No compression
UBIFS_COMPR_LZO             = 1 # LZO compression
UBIFS_COMPR_ZLIB            = 2 # ZLIB compression
UBIFS_COMPR_ZSTD            = 3 # ZSTD compression
UBIFS_COMPR_TYPES_CNT       = 4 # Count of supported compression types
PRINT_UBIFS_COMPR = ['none','lzo','zlib', 'zstd']

# UBIFS node types
UBIFS_INO_NODE              = 0  # Inode node
UBIFS_DATA_NODE             = 1  # Data node
UBIFS_DENT_NODE             = 2  # Directory entry node
UBIFS_XENT_NODE             = 3  # Extended attribute node
UBIFS_TRUN_NODE             = 4  # Truncation node
UBIFS_PAD_NODE              = 5  # Padding node
UBIFS_SB_NODE               = 6  # Superblock node
UBIFS_MST_NODE              = 7  # Master node
UBIFS_REF_NODE              = 8  # LEB reference node
UBIFS_IDX_NODE              = 9  # Index node
UBIFS_CS_NODE               = 10 # Commit start node
UBIFS_ORPH_NODE             = 11 # Orphan node
UBIFS_AUTH_NODE             = 12 # Authentication node
UBIFS_SIG_NODE              = 13 # Signature node
UBIFS_NODE_TYPES_CNT        = 14 # Count of supported node types

# Master node flags
UBIFS_MST_DIRTY             = 1 # Rebooted uncleanly
UBIFS_MST_NO_ORPHS          = 2 # No orphans present
UBIFS_MST_RCVRY             = 4 # Written by recovery
PRINT_UBIFS_MST = [[UBIFS_MST_DIRTY, 'Dirty'],
                   [UBIFS_MST_NO_ORPHS, 'No orphans'],
                   [UBIFS_MST_RCVRY, 'Recovery write'],
                  ]

# Node group type
UBIFS_NO_NODE_GROUP         = 0 # This node is not part of a group
UBIFS_IN_NODE_GROUP         = 1 # This node is part of a group
UBIFS_LAST_OF_NODE_GROUP    = 2 # This node is the last in a group

# Superblock flags
UBIFS_FLG_BIGLPT            = 2     # If 'big' LPT model is used if set.
UBIFS_FLG_SPACE_FIXUP       = 4     # First-mount 'fixup' of free space within.
UBIFS_FLG_DOUBLE_HASH       = 8     # Store 32bit cookie for 64bit support.
UBIFS_FLG_ENCRYPTION        = 16    # If filesystem contains encrypted files.
UBIFS_FLG_AUTHENTICATION    = 32    # If contains hashes for authentication.
PRINT_UBIFS_FLGS = [[UBIFS_FLG_BIGLPT,       'Big LPT'],
                    [UBIFS_FLG_SPACE_FIXUP,   'Space fixup'],
                    [UBIFS_FLG_DOUBLE_HASH,   'Double hash'],
                    [UBIFS_FLG_ENCRYPTION,    'Encryption'],
                    [UBIFS_FLG_AUTHENTICATION,'Authentication'],
                   ]

# Struct defines

# Common header node
UBIFS_COMMON_HDR_FORMAT = '<IIQIBB2s'
UBIFS_COMMON_HDR_FIELDS = ['magic',         # UBIFS node magic number.
                           'crc',           # CRC32 checksum of header.
                           'sqnum',         # Sequence number.
                           'len',           # Full node length.
                           'node_type',     # Node type.
                           'group_type',    # Node group type.
                           'padding',       # Reserved for future, zeros.
                           ]
UBIFS_COMMON_HDR_SZ = struct.calcsize(UBIFS_COMMON_HDR_FORMAT)
                            # LEBs needed.
# Key offset in key nodes
# out of place because of ordering issues.
UBIFS_KEY_OFFSET = UBIFS_COMMON_HDR_SZ

# Device node descriptor
UBIFS_DEV_DESC_FORMAT = '<IQ'
UBIFS_DEV_DESC_FIELDS = ['new',  # New type device descriptor.
                         'huge', # huge type device descriptor.
                         ]
UBIFS_DEV_DESC_SZ = struct.calcsize(UBIFS_DEV_DESC_FORMAT)

# Inode node
UBIFS_INO_NODE_FORMAT = '<%ssQQQQQIIIIIIIIIII4sIH26s' % (UBIFS_MAX_KEY_LEN)
UBIFS_INO_NODE_FIELDS = ['key',         # Node key.
                         'creat_sqnum', # Sequence number at time of creation.
                         'size',        # Inode size in bytes (uncompressed).
                         'atime_sec',   # Access time in seconds.
                         'ctime_sec',   # Creation time seconds.
                         'mtime_sec',   # Modification time in seconds.
                         'atime_nsec',  # Access time in nanoseconds.
                         'ctime_nsec',  # Creation time in nanoseconds.
                         'mtime_nsec',  # Modification time in nanoseconds.
                         'nlink',       # Number of hard links.
                         'uid',         # Owner ID.
                         'gid',         # Group ID.
                         'mode',        # Access flags.
                         'flags',       # Per-inode flags.
                         'data_len',    # Inode data length.
                         'xattr_cnt',   # Count of extended attr this inode has.
                         'xattr_size',  # Summarized size of all extended
                                        # attributes in bytes.
                         'padding1',    # Reserved for future, zeros.
                         'xattr_names', # Sum of lengths of all extended
                                        # attribute names belonging to this
                                        # inode.
                         'compr_type',  # Compression type used for this inode.
                         'padding2',    # Reserved for future, zeros.
                         ]
                                        # 'data', no size.
UBIFS_INO_NODE_SZ = struct.calcsize(UBIFS_INO_NODE_FORMAT)


# Directory entry node
UBIFS_DENT_NODE_FORMAT = '<%ssQBBHI' % (UBIFS_MAX_KEY_LEN)
UBIFS_DENT_NODE_FIELDS = ['key',        # Node key.
                          'inum',       # Target inode number.
                          'padding1',   # Reserved for future, zeros.
                          'type',       # Type of target inode.
                          'nlen',       # Name length.
                          'cookie',     # 32bit random number, used to
                                        # construct a 64bit identifier.
                          ]
                                        # 'name', no size.
UBIFS_DENT_NODE_SZ = struct.calcsize(UBIFS_DENT_NODE_FORMAT)


# Data node
UBIFS_DATA_NODE_FORMAT = '<%ssIHH' % (UBIFS_MAX_KEY_LEN)
UBIFS_DATA_NODE_FIELDS = ['key',            # Node key.
                          'size',           # Uncompressed data size.
                          'compr_type',     # Compression type UBIFS_COMPR_*.
                          'compr_size',     # Compressed data size in bytes
                                            # only valid when data is encrypted.
                          ]
                                            # 'data', no size.
UBIFS_DATA_NODE_SZ = struct.calcsize(UBIFS_DATA_NODE_FORMAT)

# Truncation node
UBIFS_TRUN_NODE_FORMAT = '<I12sQQ'
UBIFS_TRUN_NODE_FIELDS = ['inum',           # Truncated inode number.
                          'padding',        # Reserved for future, zeros.
                          'old_size',       # size before truncation.
                          'new_size',       # Size after truncation.
                          ]
UBIFS_TRUN_NODE_SZ = struct.calcsize(UBIFS_TRUN_NODE_FORMAT)

# Padding node
UBIFS_PAD_NODE_FORMAT = '<I'
UBIFS_PAD_NODE_FIELDS = ['pad_len'] # Number of bytes after this inode unused.
UBIFS_PAD_NODE_SZ = struct.calcsize(UBIFS_PAD_NODE_FORMAT)


# The maxmimum size of a hash, enough for sha512
UBIFS_MAX_HASH_LEN = 64

# The maxmimum size of a hmac, enough for hmac(sha512)
UBIFS_MAX_HMAC_LEN = 64


# Superblock node
UBIFS_SB_NODE_FORMAT = '<2sBBIIIIIQIIIIIIIH2sIIQI16sI%ss%ssH%ss3774s' % (UBIFS_MAX_HMAC_LEN, UBIFS_MAX_HMAC_LEN, UBIFS_MAX_HASH_LEN)
UBIFS_SB_NODE_FIELDS = ['padding',          # Reserved for future, zeros.
                        'key_hash',         # Type of hash func used in keys.
                        'key_fmt',          # Format of the key.
                        'flags',            # File system flags.
                        'min_io_size',      # Min I/O unit size.
                        'leb_size',         # LEB size in bytes.
                        'leb_cnt',          # LEB count used by FS.
                        'max_leb_cnt',      # Max count of LEBS used by FS.
                        'max_bud_bytes',    # Max amount of data stored in buds.
                        'log_lebs',         # Log size in LEBs.
                        'lpt_lebs',         # Number of LEBS used for lprops
                                            # table.
                        'orph_lebs',        # Number of LEBS used for
                                            # recording orphans.
                        'jhead_cnt',        # Count of journal heads.
                        'fanout',           # Tree fanout, max number of links
                                            # per indexing node.
                        'lsave_cnt',        # Number of LEB numbers in LPT's
                                            # save table.
                        'fmt_version',      # UBIFS on-flash format version.
                        'default_compr',    # Default compression used.
                        'padding1',         # Reserved for future, zeros.
                        'rp_uid',           # Reserve pool UID.
                        'rp_gid',           # Reserve pool GID.
                        'rp_size',          # Reserve pool size in bytes.
                        'time_gran',        # Time granularity in nanoseconds.
                        'uuid',             # UUID generated when the FS image
                                            # was created.
                        'ro_compat_version',# UBIFS R/O Compatibility version.
                        'hmac',             # HAMC to authenticate the superblock node.
                        'hmac_wkm',         # HMAC of a well known message (the string "UBIFS").
                                            # as a convenience to the user to chek if the correct
                                            # key is past.
                        'hash_algo',        # The has algo used for this feilseystem.
                                            # (one of enum hash_algo).
                        'hash_mst',         # Hash of the master node, only valid for
                                            # signed images in which the master node
                                            # does not contain a hmac.
                        'padding2'          # Reserved for future, zeros.
                        ]
UBIFS_SB_NODE_SZ = struct.calcsize(UBIFS_SB_NODE_FORMAT)

# Master node
UBIFS_MST_NODE_FORMAT = '<QQIIIIIIIIQQQQQQIIIIIIIIIIII%ss%ss%ss152s' % (UBIFS_MAX_HASH_LEN, UBIFS_MAX_HASH_LEN, UBIFS_MAX_HMAC_LEN)
UBIFS_MST_NODE_FIELDS = ['highest_inum',    # Highest inode number in the
                                            # committed index.
                         'cmt_no',          # Commit Number.
                         'flags',           # Various flags.
                         'log_lnum',        # LEB num start of log.
                         'root_lnum',       # LEB num of root indexing node.
                         'root_offs',       # Offset within root_lnum
                         'root_len',        # Root indexing node length.
                         'gc_lnum',         # LEB reserved for garbage collection.
                         'ihead_lnum',      # LEB num of index head.
                         'ihead_offs',      # Offset of index head.
                         'index_size',      # Size of index on flash.
                         'total_free',      # Total free space in bytes.
                         'total_dirty',     # Total dirty space in bytes.
                         'total_used',      # Total used space in bytes (data LEBs)
                         'total_dead',      # Total dead space in bytes (data LEBs)
                         'total_dark',      # Total dark space in bytes (data LEBs)
                         'lpt_lnum',        # LEB num of LPT root nnode.
                         'lpt_offs',        # Offset of LPT root nnode.
                         'nhead_lnum',      # LEB num of LPT head.
                         'nhead_offs',      # Offset of LPT head.
                         'ltab_lnum',       # LEB num of LPT's own lprop table.
                         'ltab_offs',       # Offset of LPT's own lprop table.
                         'lsave_lnum',      # LEB num of LPT's save table.
                         'lsave_offs',      # Offset of LPT's save table.
                         'lscan_lnum',      # LEB num of last LPT scan.
                         'empty_lebs',      # Number of empty LEBs.
                         'idx_lebs',        # Number of indexing LEBs.
                         'leb_cnt',         # Count of LEBs used by FS.
                         'hash_root_idx',   # The hash of the root index node.
                         'hash_lpt',        # The has of the LPT.
                         'hmac',            # HMAC to athenticate the master node.
                         'padding',         # Reserved for future, zeros.
                         ]
UBIFS_MST_NODE_SZ = struct.calcsize(UBIFS_MST_NODE_FORMAT)

# LEB Reference node
UBIFS_REF_NODE_FORMAT = '<III28s'
UBIFS_REF_NODE_FIELDS = ['lnum',            # Referred LEB number.
                         'offs',            # Start offset of referred LEB.
                         'jhead',           # Journal head number.
                         'padding',         # Reserved for future, zeros.
                         ]
UBIFS_REF_NODE_SZ = struct.calcsize(UBIFS_REF_NODE_FORMAT)

# Signature node
UBIFS_SIG_NODE_FORMAT = '<II32s'
UBIFS_SIG_NODE_FIELDS = ['type',            # Type of the signature.
                         'len',             # Length of signature data.
                         'padding',         # Reserved for future, zeros.
                         ]
                                            # 'sig', no size.

UBIFS_SIG_NODE_SZ = struct.calcsize(UBIFS_SIG_NODE_FORMAT)

# key/reference/length branch
UBIFS_BRANCH_FORMAT = '<III%ss' % (UBIFS_SK_LEN)
UBIFS_BRANCH_FIELDS = ['lnum',              # LEB number of target node.
                       'offs',              # Offset within lnum.
                       'len',               # Target node length.
                       'key',               # Using UBIFS_SK_LEN as size.
                       ]
UBIFS_BRANCH_SZ = struct.calcsize(UBIFS_BRANCH_FORMAT)

# Indexing node
UBIFS_IDX_NODE_FORMAT = '<HH'
UBIFS_IDX_NODE_FIELDS = ['child_cnt',       # Number of child index nodes.
                         'level',           # Tree level.
                         ]
                                            # 'branches', no size.
UBIFS_IDX_NODE_SZ = struct.calcsize(UBIFS_IDX_NODE_FORMAT)

# File chunk size for reads.
FILE_CHUNK_SZ = 5 * 1024 *1024
