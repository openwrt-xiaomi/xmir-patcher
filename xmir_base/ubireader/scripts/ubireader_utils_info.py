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
if (sys.version_info > (3, 0)):
    import configparser
else:
    import ConfigParser as configparser
from ubireader import settings
from ubireader.ubi import ubi
from ubireader.ubi.defines import UBI_EC_HDR_MAGIC, PRINT_VOL_TYPE_LIST, UBI_VTBL_AUTORESIZE_FLG
from ubireader.ubifs import ubifs
from ubireader.ubifs.defines import PRINT_UBIFS_KEY_HASH, PRINT_UBIFS_COMPR
from ubireader.ubi_io import ubi_file, leb_virtual_file
from ubireader.debug import error, log
from ubireader.utils import guess_filetype, guess_start_offset, guess_peb_size

def create_output_dir(outpath):
    if os.path.exists(outpath):
        if os.listdir(outpath):
            error(create_output_dir, 'Fatal', 'Output directory is not empty. %s' % outpath)
    else:
        try:
            os.makedirs(outpath)
            log(create_output_dir, 'Created output path: %s' % outpath)
        except Exception as e:
            error(create_output_dir, 'Fatal', '%s' % e)


def get_ubi_params(ubi_obj):
    """Get ubi_obj utils params

    Arguments:
    Obj:ubi    -- UBI object.

    Returns:
    Dict       -- Dict keyed to volume with Dict of args and flags.
    """
    ubi_flags = {'min_io_size':'-m',
                    'max_bud_bytes':'-j',
                    'leb_size':'-e',
                    'default_compr':'-x',
                    'sub_page_size':'-s',
                    'fanout':'-f',
                    'key_hash':'-k',
                    'orph_lebs':'-p',
                    'log_lebs':'-l',
                    'max_leb_cnt': '-c',
                    'peb_size':'-p',
                    'sub_page_size':'-s',
                    'vid_hdr_offset':'-O',
                    'version':'-x',
                    'image_seq':'-Q',
                    'alignment':'-a',
                    'vol_id':'-n',
                    'name':'-N'}

    ubi_params = {}
    ubi_args = {}
    ini_params = {}

    for image in ubi_obj.images:
        img_seq = image.image_seq
        ubi_params[img_seq] = {}
        ubi_args[img_seq] = {}
        ini_params[img_seq] = {}

        for volume in image.volumes:
            ubi_args[img_seq][volume] = {}
            ini_params[img_seq][volume] = {}

            # Get ubinize.ini settings
            ini_params[img_seq][volume]['vol_type'] = PRINT_VOL_TYPE_LIST[image.volumes[volume].vol_rec.vol_type]

            if image.volumes[volume].vol_rec.flags == UBI_VTBL_AUTORESIZE_FLG:
                ini_params[img_seq][volume]['vol_flags'] = 'autoresize'
            else:
                ini_params[img_seq][volume]['vol_flags'] = image.volumes[volume].vol_rec.flags

            ini_params[img_seq][volume]['vol_id'] = image.volumes[volume].vol_id
            ini_params[img_seq][volume]['vol_name'] = image.volumes[volume].name.rstrip(b'\x00').decode('utf-8')
            ini_params[img_seq][volume]['vol_alignment'] = image.volumes[volume].vol_rec.alignment

            ini_params[img_seq][volume]['vol_size'] = image.volumes[volume].vol_rec.reserved_pebs * ubi_obj.leb_size

            # Create file object backed by UBI blocks.
            lebv_file = leb_virtual_file(ubi_obj, image.volumes[volume].get_blocks(ubi_obj.blocks))
            # Create UBIFS object
            ubifs_obj = ubifs(lebv_file)

            for key, value in ubifs_obj.superblock_node:
                if key == 'key_hash':
                    value = PRINT_UBIFS_KEY_HASH[value]
                elif key == 'default_compr':
                    value = PRINT_UBIFS_COMPR[value]

                if key in ubi_flags:
                    ubi_args[img_seq][volume][key] = value
            
            for key, value in image.volumes[volume].vol_rec:
                if key == 'name':
                    value = value.rstrip(b'\x00').decode('utf-8')

                if key in ubi_flags:
                    ubi_args[img_seq][volume][key] = value

            ubi_args[img_seq][volume]['version'] = image.version
            ubi_args[img_seq][volume]['vid_hdr_offset'] = image.vid_hdr_offset
            ubi_args[img_seq][volume]['sub_page_size'] = ubi_args[img_seq][volume]['vid_hdr_offset']
            ubi_args[img_seq][volume]['sub_page_size'] = ubi_args[img_seq][volume]['vid_hdr_offset']
            ubi_args[img_seq][volume]['image_seq'] = image.image_seq
            ubi_args[img_seq][volume]['peb_size'] = ubi_obj.peb_size
            ubi_args[img_seq][volume]['vol_id'] = image.volumes[volume].vol_id

            ubi_params[img_seq][volume] = {'flags':ubi_flags, 'args':ubi_args[img_seq][volume], 'ini':ini_params[img_seq][volume]}

    return ubi_params


def print_ubi_params(ubi_obj):
    ubi_params = get_ubi_params(ubi_obj)
    for img_params in ubi_params:
        for volume in ubi_params[img_params]:
            ubi_flags = ubi_params[img_params][volume]['flags']
            ubi_args = ubi_params[img_params][volume]['args']
            ini_params = ubi_params[img_params][volume]['ini']
            sorted_keys = sorted(ubi_params[img_params][volume]['args'])
    
            print('\nVolume %s' % volume)
            for key in sorted_keys:
                if len(key)< 8:
                    name = '%s\t' % key
                else:
                    name = key
                print('\t%s\t%s %s' % (name, ubi_flags[key], ubi_args[key]))

            print('\n\t#ubinize.ini#')            
            print('\t[%s]' % ini_params['vol_name'])
            for key in ini_params:
                if key != 'name':
                    print('\t%s=%s' % (key, ini_params[key]))


def make_files(ubi, outpath):
    ubi_params = get_ubi_params(ubi)

    for img_params in ubi_params:
        config = configparser.ConfigParser()
        img_outpath = os.path.join(outpath, 'img-%s' % img_params)

        if not os.path.exists(img_outpath):
            os.mkdir(img_outpath)

        ini_path = os.path.join(img_outpath, 'img-%s.ini' % img_params)
        ubi_file = os.path.join('img-%s.ubi' % img_params)
        script_path = os.path.join(img_outpath, 'create_ubi_img-%s.sh' % img_params)
        ubifs_files =[]               
        buf = '#!/bin/sh\n'
        print('Writing to: %s' % script_path) 

        with open(script_path, 'w') as fscr:
            with open(ini_path, 'w') as fini:
                print('Writing to: %s' % ini_path)
                vol_idx = 0

                for volume in ubi_params[img_params]:
                    ubifs_files.append(os.path.join('img-%s_%s.ubifs' % (img_params, vol_idx)))
                    ini_params = ubi_params[img_params][volume]['ini']
                    ini_file = 'img-%s.ini' % img_params     
                    config.add_section(volume)
                    config.set(volume, 'mode', 'ubi')
                    config.set(volume, 'image', ubifs_files[vol_idx])
        
                    for i in ini_params:
                        config.set(volume, i, str(ini_params[i]))

                    ubi_flags = ubi_params[img_params][volume]['flags']
                    ubi_args = ubi_params[img_params][volume]['args']
                    mkfs_flags = ['min_io_size',
                                  'leb_size',
                                  'max_leb_cnt',
                                  'default_compr',
                                  'fanout',
                                  'key_hash',
                                  'orph_lebs',
                                  'log_lebs']

                    argstr = ''
                    for flag in mkfs_flags:
                        argstr += ' %s %s' % (ubi_flags[flag], ubi_args[flag])

                    #leb = '%s %s' % (ubi_flags['leb_size'], ubi_args['leb_size'])
                    peb = '%s %s' % (ubi_flags['peb_size'], ubi_args['peb_size'])
                    min_io = '%s %s' % (ubi_flags['min_io_size'], ubi_args['min_io_size'])
                    #leb_cnt = '%s %s' % (ubi_flags['max_leb_cnt'], ubi_args['max_leb_cnt'])
                    vid_hdr = '%s %s' % (ubi_flags['vid_hdr_offset'], ubi_args['vid_hdr_offset'])
                    sub_page = '%s %s' % (ubi_flags['sub_page_size'], ubi_args['sub_page_size'])

                    buf += '/usr/sbin/mkfs.ubifs%s -r $%s %s\n' % (argstr, (vol_idx+1), ubifs_files[vol_idx])

                    vol_idx += 1

                config.write(fini)

            ubinize_flags = ['peb_size',
                              'min_io_size',
                              'vid_hdr_offset',
                              'sub_page_size',
                              'version',
                              'image_seq']

            argstr = ''
            for flag in ubinize_flags:
                argstr += ' %s %s' % (ubi_flags[flag], ubi_args[flag])

            buf += '/usr/sbin/ubinize%s -o %s %s\n' % (argstr, ubi_file, ini_file)
            fscr.write(buf)
        os.chmod(script_path, 0o755)

def main():
    start = time.time()
    description = 'Determine settings for recreating UBI image.'
    usage = 'ubireader_utils_info [options] filepath'
    parser = argparse.ArgumentParser(usage=usage, description=description)

    parser.add_argument('-r', '--show-only', action='store_true', dest='show_only',
                      help='Print parameters to screen only. (default: false)')

    parser.add_argument('-l', '--log', action='store_true', dest='log',
                      help='Print extraction information to screen.')

    parser.add_argument('-v', '--verbose-log', action='store_true', dest='verbose',
                      help='Prints nearly everything about anything to screen.')
    
    parser.add_argument('-p', '--peb-size', type=int, dest='block_size',
                        help='Specify PEB size.')

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

    # Create file object.
    ufile_obj = ubi_file(path, block_size, start_offset, end_offset)

    # Create UBI object
    ubi_obj = ubi(ufile_obj)

    # Print info.
    print_ubi_params(ubi_obj)

    if not args.show_only:
        create_output_dir(outpath)
        # Create build scripts.
        make_files(ubi_obj, outpath)

    ufile_obj.close()


if __name__=='__main__':
    main()
