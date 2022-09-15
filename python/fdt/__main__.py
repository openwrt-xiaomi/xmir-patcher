#!/usr/bin/env python

# Copyright 2017 Martin Olejar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import fdt
import argparse


########################################################################################################################
# Helper Functions
########################################################################################################################
def parse_fdt(file_path: str, file_type: str):
    """
    Parse *.dtb ot *.dts input file and return FDT object

    :param file_path: The path to input file
    :param file_type: File type 'dtb', 'dts' or 'auto'
    """

    if not os.path.exists(file_path):
        raise Exception('File doesnt exist: {}'.format(file_path))

    if file_type == 'auto':
        if file_path.endswith(".dtb"):
            file_type = 'dtb'
        elif file_path.endswith(".dts"):
            file_type = 'dts'
        else:
            raise Exception('Not supported file extension: {}'.format(file_path))

    if file_type == 'dtb':
        with open(file_path, 'rb') as f:
            obj = fdt.parse_dtb(f.read())
    else:
        with open(file_path, 'r') as f:
            obj = fdt.parse_dts(f.read(), os.path.dirname(file_path))

    return obj


########################################################################################################################
# Commands Functions
########################################################################################################################
def pack(in_file: str, out_file: str, version: int, lc_version: int, cpu_id: int, update_phandles: bool):
    """
    The implementation of pack command.

    :param in_file: Input File Path
    :param out_file: Output File Path
    :param version: DTB version
    :param lc_version: DTB Last Compatible Version
    :param cpu_id: Boot CPU ID
    :param update_phandles: If True phandles will be updated
    """

    if version is not None and version > fdt.Header.MAX_VERSION:
        raise Exception("DTB Version must be lover or equal {} !".format(fdt.Header.MAX_VERSION))

    fdt_obj = parse_fdt(in_file, 'dts')
    if update_phandles:
        fdt_obj.update_phandles()
    raw_data = fdt_obj.to_dtb(version, lc_version, cpu_id)

    with open(out_file, 'wb') as f:
        f.write(raw_data)

    print(" DTB saved as: {}".format(out_file))


def unpack(in_file: str, out_file: str, tab_size):
    """
    The implementation of unpack command.

    :param in_file: Input File Path
    :param out_file: Output File Path
    :param tab_size: Tabulator size in count of spaces
    """
    fdt_obj = parse_fdt(in_file, 'dtb')

    with open(out_file, 'w') as f:
        f.write(fdt_obj.to_dts(tab_size))

    print(" DTS saved as: {}".format(out_file))


def merge(out_file: str, in_files: list, file_type: str, tab_size: int):
    """
    The implementation of merge command.

    :param out_file: Output File Path
    :param in_files: Input Files Path
    :param file_type: The type of input files
    :param tab_size: Tabulator size in count of spaces
    """
    fdt_obj = None

    for file in in_files:
        obj = parse_fdt(file, file_type)
        if fdt_obj is None:
            fdt_obj = obj
        else:
            fdt_obj.merge(obj)

    with open(out_file, 'w') as f:
        f.write(fdt_obj.to_dts(tab_size))

    print(" Output saved as: {}".format(out_file))


def diff(in_file1: str, in_file2: str, file_type: str, out_dir: str):
    """
    The implementation of diff command.

    :param in_file1: Input File1 Path
    :param in_file2: Input File2 Path
    :param file_type: The type of input files
    :param out_dir: Path to output directory
    """
    # load input files
    fdt1 = parse_fdt(in_file1, file_type)
    fdt2 = parse_fdt(in_file2, file_type)

    # compare it
    diff = fdt.diff(fdt1, fdt2)
    if diff[0].empty:
        print(" Input files are completely different !")
        sys.exit()

    # create output directory
    os.makedirs(out_dir, exist_ok=True)

    # get names for output files
    file_name = (
        "same.dts",
        os.path.splitext(os.path.basename(in_file1))[0] + ".dts",
        os.path.splitext(os.path.basename(in_file2))[0] + ".dts")

    # save output files
    for index, obj in enumerate(diff):
        if not obj.empty:
            with open(os.path.join(out_dir, file_name[index]), 'w') as f:
                f.write(obj.to_dts())

    print(" Diff output saved into: {}".format(out_dir))


########################################################################################################################
# Main
########################################################################################################################
def main():
    # cli interface
    parser = argparse.ArgumentParser(
        prog="pydtc",
        description="Flat Device Tree (FDT) tool for manipulation with *.dtb and *.dts files")
    parser.add_argument('-v', '--version', action='version', version=fdt.__version__)
    subparsers = parser.add_subparsers(dest='command')

    # pack command
    pack_parser = subparsers.add_parser('pack', help='Pack *.dts into binary blob (*.dtb)')
    pack_parser.add_argument('dts_file', nargs=1, help='Path to *.dts file')
    pack_parser.add_argument('-v', dest='version', type=int, help='DTB Version')
    pack_parser.add_argument('-l', dest='lc_version', type=int, help='DTB Last Compatible Version')
    pack_parser.add_argument('-c', dest='cpu_id', type=int, help='Boot CPU ID')
    pack_parser.add_argument('-p', dest='phandles', action='store_true', help='Update phandles')
    pack_parser.add_argument('-o', dest='dtb_file', type=str, help='Output path with file name (*.dtb)')

    # unpack command
    unpack_parser = subparsers.add_parser('unpack', help='Unpack *.dtb into readable format (*.dts)')
    unpack_parser.add_argument('dtb_file', nargs=1, help='Path to *.dtb file')
    unpack_parser.add_argument('-s', dest='tab_size', type=int, default=4, help='Tabulator Size')
    unpack_parser.add_argument('-o', dest='dts_file', type=str, help='Output path with file name (*.dts)')

    # merge command
    merge_parser = subparsers.add_parser('merge', help='Merge more files in *.dtb or *.dts format')
    merge_parser.add_argument('out_file', nargs=1, help='Output path with file name (*.dts or *.dtb)')
    merge_parser.add_argument('in_files', nargs='+', help='Path to input files')
    merge_parser.add_argument('-t', dest='type', type=str, choices=['auto', 'dts', 'dtb'], help='Input file type')
    merge_parser.add_argument('-s', dest='tab_size', type=int, default=4, help='Tabulator Size for dts')

    # diff command
    diff_parser = subparsers.add_parser('diff', help='Compare two files in *.dtb or *.dts format')
    diff_parser.add_argument('in_file1', nargs=1, help='Path to dts or dtb file')
    diff_parser.add_argument('in_file2', nargs=1, help='Path to dts or dtb file')
    diff_parser.add_argument('-t', dest='type', type=str, choices=['auto', 'dts', 'dtb'], help='Input file type')
    diff_parser.add_argument('-o', dest='out_dir', type=str, help='Output directory')

    args = parser.parse_args()

    try:
        if args.command == 'pack':
            in_file = args.dts_file[0]
            if args.dtb_file is None:
                out_file = os.path.splitext(os.path.basename(in_file))[0] + ".dtb"
            else:
                out_file = args.dtb_file.lstrip()
            pack(in_file, out_file, args.version, args.lc_version, args.cpu_id, args.phandles)

        elif args.command == 'unpack':
            in_file = args.dtb_file[0]
            if args.dts_file is None:
                out_file = os.path.splitext(os.path.basename(in_file))[0] + ".dts"
            else:
                out_file = args.dts_file.lstrip()
            unpack(in_file, out_file, args.tab_size)

        elif args.command == 'merge':
            merge(args.out_file[0], args.in_files, args.type, args.tab_size)

        elif args.command == 'diff':
            out_dir = args.out_dir if args.out_dir else os.path.join(os.getcwd(), 'diff_out')
            diff(args.in_file1[0], args.in_file2[0], args.type, out_dir.lstrip())

        else:
            parser.print_help()

    except Exception as e:
        print("[pydtc] Execution Error !")
        print(str(e) if str(e) else "Unknown Error", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
