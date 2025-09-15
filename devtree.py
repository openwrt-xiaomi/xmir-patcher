#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import ctypes

FDT_MAGIC = b"\xD0\x0D\xFE\xED"

class fdt_header(ctypes.BigEndianStructure):
    _fields_ = [("magic",             ctypes.c_uint),
                ("totalsize",         ctypes.c_uint),
                ("off_dt_struct",     ctypes.c_uint),
                ("off_dt_strings",    ctypes.c_uint),
                ("off_mem_rsvmap",    ctypes.c_uint),
                ("version",           ctypes.c_uint),
                ("last_comp_version", ctypes.c_uint),
                ("boot_cpuid_phys",   ctypes.c_uint),
                ("size_dt_strings",   ctypes.c_uint),
                ("size_dt_struct",    ctypes.c_uint)]

class fdt_reserve_entry(ctypes.BigEndianStructure):
    _fields_ = [("address", ctypes.c_uint64),
                ("size",    ctypes.c_uint64)]

class fdt_node_header(ctypes.BigEndianStructure):
    _fields_ = [("tag",     ctypes.c_uint),
                ("name",    ctypes.c_char * 128)]

class fdt_property(ctypes.BigEndianStructure):
    _fields_ = [("tag",     ctypes.c_uint),
                ("size",    ctypes.c_uint),
                ("nameoff", ctypes.c_uint),
                ("data",    ctypes.c_char)]

FDT_TAGSIZE = 4

FDT_BEGIN_NODE = 1    # Start node: full name
FDT_END_NODE   = 2    # End node
FDT_PROP       = 3    # Property: name off, size, content
FDT_NOP        = 4
FDT_END        = 9

FDT_V1_SIZE	 = 7 * 4
FDT_V2_SIZE	 = FDT_V1_SIZE + 4
FDT_V3_SIZE  = FDT_V2_SIZE + 4
FDT_V16_SIZE = FDT_V3_SIZE
FDT_V17_SIZE = FDT_V16_SIZE + 4


def get_dtb_totalsize(img, pos = 0, check = True):
    if img[pos:pos+4] != FDT_MAGIC:
        return -1
    hdrsize = ctypes.sizeof(fdt_header)
    dt = fdt_header.from_buffer_copy(img[pos:pos+hdrsize])
    if not check and dt.totalsize > hdrsize + 128:
        return dt.totalsize
    if dt.totalsize > hdrsize + 128:
        if dt.off_dt_struct > hdrsize and dt.off_dt_struct < dt.totalsize:
            if dt.off_dt_strings > hdrsize and dt.off_dt_strings < dt.totalsize:
                if dt.version == 17 and dt.last_comp_version == 16:
                    if dt.boot_cpuid_phys == 0:
                        if dt.size_dt_strings < dt.totalsize and dt.size_dt_struct < dt.totalsize:
                            return dt.totalsize
    return -1

def find_dtb(img, pos = 0, maxsize = 256000):
    while True:
        k = img.find(FDT_MAGIC, pos)
        if k < 0:
            break
        pos = k + 4
        totalsize = get_dtb_totalsize(img, k, check = True)
        if maxsize and totalsize > maxsize:
            continue
        if totalsize > 0:
            return k, totalsize
    return None, None

def get_dtb(img, pos = 0, maxsize = 256000):
    pos, size = find_dtb(img, pos, maxsize)
    return img[pos:pos+size] if pos is not None else None

def get_dtb_part_info(dtb, part_name):
    k = dtb.find(b'fixed-partitions\x00')
    if k <= 0:
        return None
    while True:
        k = dtb.find(b"partition@", k)
        if k < 0:
            break
        k = dtb.find(b"\x00", k) + 1
        k = (k + 3) & 0xFFFFFFFC
        k += 12
        n = dtb.find(b"\x00", k)
        name = dtb[k:n]
        name_len = len(name)
        name = name.decode('latin_1')
        if name != part_name:
            continue
        k += name_len + 1
        k = (k + 3) & 0xFFFFFFFC
        k += 12
        addr = int.from_bytes(dtb[k:k+4], byteorder='big')
        size = int.from_bytes(dtb[k+4:k+8], byteorder='big')
        return {'addr': addr, 'size': size, 'name': name}
    return None

def get_fdt_string(img, offset, hdr = None):
    if not hdr:
        hdr = fdt_header.from_buffer_copy(img[:ctypes.sizeof(fdt_header)])
    offset = hdr.off_dt_strings + offset
    pos = offset
    while True:
        if img[pos:pos+1] == b'\x00':
            break
        pos += 1
    return img[offset:pos].decode()

def roundup4(value):
    return (value + 3) & 0xFFFFFFFC

def enum_fdt_nodes(img, hdr, pos, target_path, target_name, res, path = None):
    while True:
        tag = int.from_bytes(img[pos:pos+4], byteorder = 'big')
        if tag == FDT_BEGIN_NODE:
            node = fdt_node_header.from_buffer_copy( img[ pos:pos+ctypes.sizeof(fdt_node_header) ] )
            if path is None:
                if node.name:
                    raise RuntimeError(f'Incorrect FDT root name = {node.name}')
                path = [ ]
            else:
                path.append(node.name.decode())
            if not target_name:
                print('/' + '/'.join(path))
            pos += 4 + roundup4(len(node.name) + 1)
            pos = enum_fdt_nodes(img, hdr, pos, target_path, target_name, res, path)
            if pos == 0:
                return 0  # EOF
            continue
        if tag == FDT_PROP:
            prop = fdt_property.from_buffer_copy( img[ pos:pos+ctypes.sizeof(fdt_property) ] )
            name = get_fdt_string(img, prop.nameoff, hdr)
            pos += 12
            if not target_name:
                if prop.size <= 30:
                    data = img[pos:pos+prop.size]
                    print(f'  {name} = {data}')
                else:
                    data = img[pos:pos+30]                
                    print(f'  {name} = [len:{prop.size}] {data}')
            elif name == target_name and len(path) == len(target_path):
                kk = 0
                for i, dn in enumerate(path):
                    if target_path[i].endswith('*'):
                        if not dn.startswith(target_path[i][:-1]):
                            break
                    elif dn != target_path[i]:
                        break
                    kk += 1
                if kk == len(path):
                    res.append(img[pos:pos+prop.size])
                    return 0  # EOF
            pos += roundup4(prop.size)
            continue
        if tag == FDT_NOP:
            pos += 4
            continue
        if tag == FDT_END_NODE:
            if path:
                path.pop()
            pos += 4
            return pos
        if tag == FDT_END:
            return 0  # EOF
        raise RuntimeError(f'Incorrect FDT tag id = 0x{tag:X}')

def get_fdt_prop(img, target_path = None, target_name = None):
    hdr = fdt_header.from_buffer_copy( img[0:ctypes.sizeof(fdt_header) ] )
    #print(f'MAGIC = 0x{hdr.magic:X}')
    #print(f'off_dt_strings  = 0x{hdr.off_dt_strings:X}')
    #print(f'size_dt_strings = 0x{hdr.size_dt_strings:X}')
    pos = ctypes.sizeof(fdt_header) + ctypes.sizeof(fdt_reserve_entry)
    node = fdt_node_header.from_buffer_copy( img[ pos:pos+ctypes.sizeof(fdt_node_header) ] )
    if node.tag != FDT_BEGIN_NODE or node.name:
        return None
    if target_path and isinstance(target_path, str):
        target_path = target_path.strip('/')
        target_path = target_path.split('/')
        if not target_path[0]:
            target_path = [ ]
    if not target_path:
        target_path = [ ]
    res = [ ]
    enum_fdt_nodes(img, hdr, pos, target_path, target_name, res)
    return res[0] if res else None

if __name__ == "__main__":
    img_fn = None
    if len(sys.argv) > 1:
        img_fn = sys.argv[1]
            
    if not img_fn or not os.path.exists(img_fn):
        print(f'ERROR: file "{img_fn}" not found!')
        sys.exit(1)
    
    with open(img_fn, 'rb') as file:
        image = file.read()

    fdt = get_dtb(image, maxsize = None)
    if not fdt:
        print(f'ERROR: file "{img_fn}" not contain FDT image!')
        sys.exit(1)
    
    target_path = '/images/kernel*/'
    #target_name = 'os'
    target_name = None
    prop = get_fdt_prop(fdt, target_path, target_name)
    if target_name:
        print(f'RESULT: {target_path}{target_name} = {prop}')
    
    print('==== Finish ====')

