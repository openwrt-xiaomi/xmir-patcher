#!/usr/bin/env python
# -*- coding: utf-8 -*-
#############################################################
# Adapted in part from linux-source-3.2/drivers/mtd/ubi/ubi-media.h
# for use in Python.
# Oct. 2013 by Jason Pruitt
#
# Original copyright notice.
# --------------------------
#
# Copyright (c) International Business Machines Corp., 2006
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
# the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# Authors: Artem Bityutskiy (Битюцкий Артём)
#          Thomas Gleixner
#          Frank Haverkamp
#          Oliver Lohmann
#          Andreas Arnez
#
#############################################################

import struct

# Magic number
UBI_EC_HDR_MAGIC = b'\x55\x42\x49\x23'

# Initial CRC32 checksum value.
UBI_CRC32_INIT = 4294967295 #0xFFFFFFFF

# Max number of volumes allowed.
UBI_MAX_VOLUMES = 128

# Internal Volume ID start.
UBI_INTERNAL_VOL_START = 2147479551

# Error Count header.
EC_HDR_FORMAT = '>4sB3sQIII32sI'
EC_HDR_FIELDS = ['magic',           # Magic string UBI#
                 'version',         # UBI version meant to accept this image.
                 'padding',         # Reserved for future, zeros.
                 'ec',              # Erase counter
                 'vid_hdr_offset',  # Where the VID header starts.
                 'data_offset',     # Where user data starts.
                 'image_seq',       # Image sequence number
                 'padding2',        # Reserved for future, zeros.
                 'hdr_crc']         # EC header crc32 checksum.


UBI_EC_HDR_SZ = struct.calcsize(EC_HDR_FORMAT) # 64

# Volume ID header.
UBI_VID_HDR_MAGIC =b'\x55\x42\x49\x21' # UBI!
VID_HDR_FORMAT = '>4sBBBBII4sIIII4sQ12sI'
VID_HDR_FIELDS = ['magic',      # Magic string UBI!
                  'version',    # UBI version meant to accept this image.
                  'vol_type',   # Volume type, Dynamic/Static
                  'copy_flag',  # If this is a copied PEB b/c of wear leveling.
                  'compat',     # Compatibility of this volume UBI_COMPAT_*
                  'vol_id',     # ID of this volume.
                  'lnum',       # LEB number.
                  'padding',    # Reserved for future, zeros.
                  'data_size',  # How many bytes of data this contains.
                                # Used for static types only.
                  'used_ebs',   # Total num of used LEBs in this volume.
                  'data_pad',   # How many bytes at end of LEB are not used.
                  'data_crc',   # CRC32 checksum of data, static type only.
                  'padding2',   # Reserved for future, zeros.
                  'sqnum',      # Sequence number.
                  'padding3',   # Reserved for future, zeros.
                  'hdr_crc']    # VID header CRC32 checksum.


UBI_VID_HDR_SZ = struct.calcsize(VID_HDR_FORMAT) # 64

# Volume table records.
VTBL_REC_FORMAT = '>IIIBBH128sB23sI'
VTBL_REC_FIELDS = ['reserved_pebs', # How many PEBs reserved for this volume.
                   'alignment',     # Volume alignment.
                   'data_pad',      # Number of unused bytes at end of PEB.
                   'vol_type',      # Volume type, static/dynamic.
                   'upd_marker',    # If vol update started but not finished.
                   'name_len',      # Length of name.
                   'name',          # Volume name.
                   'flags',         # Volume flags
                   'padding',       # Reserved for future, zeros.
                   'crc']           # Vol record CRC32 checksum.


UBI_VTBL_REC_SZ = struct.calcsize(VTBL_REC_FORMAT) # 172

# Volume Identifier Header
UBI_VID_DYNAMIC = 1 # Volume can be resized.
UBI_VID_STATIC  = 2 # Volume can not be resized.
PRINT_VOL_TYPE_LIST = [0, 'dynamic', 'static']

# Volume table record
UBI_VTBL_AUTORESIZE_FLG = 1

UBI_COMPAT_DELETE   = 1 # Delete this internal volume before anything written.
UBI_COMPAT_RO       = 2 # Attach this device in read-only mode.
UBI_COMPAT_PRESERVE = 4 # Preserve this internal volume - touch nothing.
UBI_COMPAT_REJECT   = 5 # Reject this UBI image
PRINT_COMPAT_LIST = [0, 'Delete', 'Read Only', 0, 'Preserve', 'Reject']

# File chunk size for reads.
FILE_CHUNK_SZ = 5 * 1024 * 1024