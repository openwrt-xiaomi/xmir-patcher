#!/usr/bin/env python
#############################################################
# ubi_reader/scripts/ubireader_display_blocks
# (c) 2019 Jason Pruitt (jrspruitt@gmail.com)
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

#############################################################
# Search by block parameters and display information about
# matching blocks.
#############################################################

import os
import sys
import argparse
from ubireader.ubi import ubi_base
from ubireader.ubi_io import ubi_file
from ubireader import settings
from ubireader.ubi.defines import UBI_EC_HDR_MAGIC
from ubireader.ubifs.defines import UBIFS_NODE_MAGIC
from ubireader.utils import guess_filetype, guess_start_offset, guess_leb_size, guess_peb_size


def main():
    description = 'Search for specified blocks and display information.'
    usage = """
    ubireader_display_blocks "{'block.attr': value,...}" path/to/image
        Search for blocks by given parameters and display information about them.
        This is block only, no volume or image information is created, which can
        be used to debug file and image extraction.
    Example:
        "{'peb_num':[0, 1] + range(100, 102), 'ec_hdr.ec': 1, 'is_valid': True}"
        This matches block.peb_num 0, 1, 100, 101, and 102 
        with a block.ec_hdr.ec (erase count) of 1, that are valid PEB blocks.
        For a full list of parameters check ubireader.ubi.block.description.
    """
    parser = argparse.ArgumentParser(usage=usage, description=description)

    parser.add_argument('-l', '--log', action='store_true', dest='log',
                      help='Print extraction information to screen.')

    parser.add_argument('-v', '--verbose-log', action='store_true', dest='verbose',
                      help='Prints nearly everything about anything to screen.')
    
    parser.add_argument('-p', '--peb-size', type=int, dest='block_size',
                        help='Specify PEB size. (UBI Only)')
    
    parser.add_argument('-e', '--leb-size', type=int, dest='block_size',
                        help='Specify LEB size. (UBIFS Only)')

    parser.add_argument('-s', '--start-offset', type=int, dest='start_offset',
                        help='Specify offset of UBI/UBIFS data in file. (default: 0)')

    parser.add_argument('-n', '--end-offset', type=int, dest='end_offset',
                        help='Specify end offset of UBI/UBIFS data in file.')

    parser.add_argument('-g', '--guess-offset', type=int, dest='guess_offset',
                        help='Specify offset to start guessing where UBI data is in file. (default: 0)')

    parser.add_argument('-w', '--warn-only-block-read-errors', action='store_true', dest='warn_only_block_read_errors',
                      help='Attempts to continue extracting files even with bad block reads. Some data will be missing or corrupted! (default: False)')

    parser.add_argument('-i', '--ignore-block-header-errors', action='store_true', dest='ignore_block_header_errors',
                      help='Forces unused and error containing blocks to be included and also displayed with log/verbose. (default: False)')

    parser.add_argument('-f', '--u-boot-fix', action='store_true', dest='uboot_fix',
                      help='Assume blocks with image_seq 0 are because of older U-boot implementations and include them. (default: False)')

    parser.add_argument('block_search_params',
                      help="""
                      Double quoted Dict of ubi.block.description attributes, which is run through eval().
                      Ex. "{\'peb_num\':[0, 1], \'ec_hdr.ec\': 1, \'is_valid\': True}"
                      """)

    parser.add_argument('filepath', help='File with blocks of interest.')

    if len(sys.argv) == 1:
        parser.print_help()

    args = parser.parse_args()

    settings.logging_on = args.log

    settings.logging_on_verbose = args.verbose

    settings.warn_only_block_read_errors = args.warn_only_block_read_errors

    settings.ignore_block_header_errors = args.ignore_block_header_errors

    settings.uboot_fix = args.uboot_fix

    if args.filepath:
        path = args.filepath
        if not os.path.exists(path):
            parser.error("File path doesn't exist.")
    else:
        parser.error('File path must be provided.')
        sys.exit(1)

    if args.start_offset:
        start_offset = args.start_offset
    elif args.guess_offset:
        start_offset = guess_start_offset(path, args.guess_offset)
    else:
        start_offset = guess_start_offset(path)

    if args.end_offset:
        end_offset = args.end_offset
    else:
        end_offset = None

    filetype = guess_filetype(path, start_offset)
    if not filetype:
        parser.error('Could not determine file type.')

    if args.block_size:
        block_size = args.block_size
    else:
        if filetype == UBI_EC_HDR_MAGIC:
            block_size = guess_peb_size(path)
        elif filetype == UBIFS_NODE_MAGIC:
            block_size = guess_leb_size(path)

        if not block_size:
            parser.error('Block size could not be determined.')

    if args.block_search_params:
        try:
            search_params = eval(args.block_search_params)

            if not isinstance(search_params, dict):
                parser.error('Search Param Error: Params must be a Dict of block PEB object items:value pairs.')

        except NameError as e:
            parser.error('Search Param Error: Dict key block attrs must be single quoted.')

        except Exception as e:
            parser.error('Search Param Error: %s' % e)

    else:
        parser.error('No search parameters given, -b arg is required.')


    ufile_obj = ubi_file(path, block_size, start_offset, end_offset)
    ubi_obj = ubi_base(ufile_obj)
    blocks = []

    for block in ubi_obj.blocks:
        match = True

        for key in search_params:
            b = ubi_obj.blocks[block]

            for attr in key.split('.'):
                if hasattr(b, attr):
                    b = getattr(b, attr)

            if isinstance(search_params[key], list):
                if isinstance(b, list):
                    for value in b:
                        if value in search_params[key]:
                            break
                    else:
                        match = False
                elif b not in search_params[key]:
                    match = False

            elif b != search_params[key]:
                match = False
                break

        if match:                
            blocks.append(ubi_obj.blocks[block])

    ufile_obj.close()

    print('\nBlock matches: %s' % len(blocks))

    for block in blocks:
        print(block.display())

if __name__=='__main__':
    main()
