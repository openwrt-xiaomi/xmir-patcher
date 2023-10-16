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

import os
import sys
import time
import argparse

from ubireader import settings
from ubireader.ubi import ubi
from ubireader.ubi.defines import UBI_EC_HDR_MAGIC
from ubireader.ubi_io import ubi_file
from ubireader.debug import error, log
from ubireader.utils import guess_filetype, guess_start_offset, guess_peb_size

def create_output_dir(outpath):
    if not os.path.exists(outpath):
        try:
            os.makedirs(outpath)
            log(create_output_dir, 'Created output path: %s' % outpath)
        except Exception as e:
            error(create_output_dir, 'Fatal', '%s' % e)

def main():
    start = time.time()
    description = 'Extract UBI or UBIFS images from file containing UBI data in it.'
    usage = 'ubireader_extract_images [options] filepath'
    parser = argparse.ArgumentParser(usage=usage, description=description)

    parser.add_argument('-l', '--log', action='store_true', dest='log',
                      help='Print extraction information to screen.')

    parser.add_argument('-v', '--verbose-log', action='store_true', dest='verbose',
                      help='Prints nearly everything about anything to screen.')
    
    parser.add_argument('-p', '--peb-size', type=int, dest='block_size',
                        help='Specify PEB size.')
    
    parser.add_argument('-u', '--image-type', dest='image_type',
                        help='Specify image type to extract UBI or UBIFS. (default: UBIFS)')

    parser.add_argument('-s', '--start-offset', type=int, dest='start_offset',
                        help='Specify offset of UBI data in file. (default: 0)')

    parser.add_argument('-n', '--end-offset', type=int, dest='end_offset',
                        help='Specify end offset of UBI data in file.')

    parser.add_argument('-g', '--guess-offset', type=int, dest='guess_offset',
                        help='Specify offset to start guessing where UBI data is in file. (default: 0)')

    parser.add_argument('-w', '--warn-only-block-read-errors', action='store_true', dest='warn_only_block_read_errors',
                      help='Attempts to continue extracting files even with bad block reads. Some data will be missing or corrupted! (default: False)')

    parser.add_argument('-i', '--ignore-block-header-errors', action='store_true', dest='ignore_block_header_errors',
                      help='Forces unused and error containing blocks to be included and also displayed with log/verbose. (default: False)')

    parser.add_argument('-f', '--u-boot-fix', action='store_true', dest='uboot_fix',
                      help='Assume blocks with image_seq 0 are because of older U-boot implementations and include them. (default: False)')

    parser.add_argument('-o', '--output-dir', dest='outpath',
                        help='Specify output directory path.')

    parser.add_argument('filepath', help='File to extract contents of.')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

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
    if filetype != UBI_EC_HDR_MAGIC:
        parser.error('File does not look like UBI data.')

    img_name = os.path.basename(path)
    if args.outpath:
        outpath = os.path.abspath(os.path.join(args.outpath, img_name))
    else:
        outpath = os.path.join(settings.output_dir, img_name)

    if args.block_size:
        block_size = args.block_size
    else:
        block_size = guess_peb_size(path)

        if not block_size:
            parser.error('Block size could not be determined.')

    if args.image_type:
        image_type = args.image_type.upper()
    else:
        image_type = 'UBIFS'

    # Create file object.
    ufile_obj = ubi_file(path, block_size, start_offset, end_offset)

    # Create UBI object
    ubi_obj = ubi(ufile_obj)

    # Loop through found images in file.
    for image in ubi_obj.images:
        if image_type == 'UBI':
            # Create output path and open file.
            img_outpath = os.path.join(outpath, 'img-%s.ubi' % image.image_seq)
            create_output_dir(outpath)
            f = open(img_outpath, 'wb')

            # Loop through UBI image blocks
            for block in image.get_blocks(ubi_obj.blocks):
                if ubi_obj.blocks[block].is_valid:
                    # Write block (PEB) to file
                    f.write(ubi_obj.file.read_block(ubi_obj.blocks[block]))

        elif image_type == 'UBIFS':
            # Loop through image volumes
            for volume in image.volumes:
                # Create output path and open file.
                vol_outpath = os.path.join(outpath, 'img-%s_vol-%s.ubifs' % (image.image_seq, volume))
                create_output_dir(outpath)
                f = open(vol_outpath, 'wb')

                # Loop through and write volume block data (LEB) to file.
                for block in image.volumes[volume].reader(ubi_obj):
                    f.write(block)

    ufile_obj.close()


if __name__=='__main__':
    main()
