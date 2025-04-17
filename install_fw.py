#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import types
import tarfile
import lzma
import ctypes
import re

import xmir_base
import gateway
from gateway import die
import read_info
import activate_boot
import xqmodel
from devtree import *
import fdt


UIMAGE_MAGIC = b"\x27\x05\x19\x56"
FIT_MAGIC    = FDT_MAGIC
HSQS_MAGIC   = b"hsqs"
UBI_MAGIC    = b"UBI#"
UBIv1_MAGIC  = UBI_MAGIC + b"\x01\x00\x00\x00"


gw = gateway.Gateway()
if not gw.device_name:
    die(f"Xiaomi Mi Wi-Fi device not found! (IP: {gw.ip_addr})")


class FwError(Exception): pass

class ImgHeader():
    size = None      # Image Data Size
    os = None        # OS type: IH_OS_LINUX = 5
    arch = None      # CPU arch: IH_CPU_MIPS = 5, IH_CPU_ARM = 2
    type = None      # Image Type: IH_TYPE_KERNEL = 2
    comp = None      # IH_COMP_NONE = 0, IH_COMP_GZIP = 1, IH_COMP_BZIP2 = 2, IH_COMP_LZMA = 3, IH_COMP_XZ = 5

class Image():
    type = None      # fw_img / kernel / rootfs
    ostype = None    # 'stock', 'openwrt', 'padavan', 'pandorabox', etc
    into_ubi = False
    initrd = False
    hdr = ImgHeader()
    addr = None
    addr2 = None     # for kernel_stok/kernel_dup
    fn_local = None
    fn_remote = None
    data = None
    data2 = None     # unpacked kernel image
    dtb = None       # device-tree
    cmd = None
    
    def __init__(self, type):
        self.type = type
        
    def get_data_size(self, KB = False):
        return 0 if self.data is None else len(self.data)
    
    data_size = property(get_data_size)

def extract_str(data, offset = 0, maxlen = 256, encoding = 'UTF8'):
    x = data.find(b'\x00', offset)
    if x < 0:
        return None
    if x - offset > maxlen:
        x = offset + maxlen
    str = data[offset:x]
    return str.decode(encoding)

class XqFlash():
    img_write = True
    fw_img = Image('fw_img')
    kernel = Image('kernel')
    rootfs = Image('rootfs')
    imglst = { 'fw_img': fw_img, 'kernel': kernel, 'rootfs': rootfs }
    dn_tmp = 'tmp/fw/'
    dn_dir = 'firmware/'
    img_stock = False

    def __init__(self):
        global gw
        self.gw = gw
        os.makedirs(self.dn_dir, exist_ok = True)
        os.makedirs(self.dn_tmp, exist_ok = True)
        if gw.img_write == False:
            self.img_write = False
        print(f'device: "{gw.device_name}"')
        print(f'img_write = {gw.img_write}')
        self.fw_img.fn_remote = '/tmp/fw_img.bin'
        self.fw_img.fn_local = self.dn_tmp + 'fw_img.bin'
        self.kernel.fn_remote = '/tmp/kernel.bin'
        self.kernel.fn_local = self.dn_tmp + 'kernel.bin'
        self.rootfs.fn_remote = '/tmp/rootfs.bin'
        self.rootfs.fn_local = self.dn_tmp + 'rootfs.bin'
        self.clear_dir(self.dn_tmp)

    def clear_dir(self, dirname):
        if os.path.isdir(dirname):
            for fn in os.listdir(dirname):
                try:
                    os.remove(dirname + '/' + fn)
                except Exception:
                    pass

    def found_all_images(self):
        self.imglist = [ ]
        fn_list = [f for f in os.listdir(self.dn_dir) if os.path.isfile(os.path.join(self.dn_dir, f))]
        for i, fname in enumerate(fn_list):
            fname = self.dn_dir + fname
            fsize = os.path.getsize(fname)
            if fsize < 256*1024:
                continue
            with open(fname, "rb") as file:
                data = file.read(256)
            img = types.SimpleNamespace()
            img.fn = fname
            img.type = None
            if data[:4] == b'HDR1' or data[:4] == b'HDR2':
                img.type = 'stock'
            if data[:4] == UIMAGE_MAGIC:    # uImage 
                img.type = 'factory'
            if data[:4] == FDT_MAGIC:       # factory squashfs image
                img.type = 'factory'
            if data[:8] == UBIv1_MAGIC:     # rootfs_ubi
                img.type = 'ubifs'
            if img.type:
                if len(self.imglist) == 0:
                    print('Image files in directory "{}":'.format(self.dn_dir))
                print('  "{}"'.format(fname))
                self.imglist.append(img)

    def parse_all_images(self):
        if len(self.imglist) <= 0:
            die('The firmware was not found in the "{}" folder!'.format(self.dn_dir))

        c_stock = len([i for i in self.imglist if i.type == 'stock'])
        c_factory = len([i for i in self.imglist if i.type == 'factory'])
        c_ubifs = len([i for i in self.imglist if i.type == 'ubifs'])

        if c_stock > 1 or c_factory > 1 or c_ubifs > 1:
            die('Too many different files in directory {}'.format(self.dn_dir))

        if c_stock and len(self.imglist) > 1:
            die('Too many different files in directory {}'.format(self.dn_dir))

        self.dev = read_info.DevInfo(verbose = 0, infolevel = 1)
        self.cpuarch = self.dev.info.cpu_arch
        if self.cpuarch not in 'mips armv7 arm64':
            die("Currently support only MIPS, ARMv7, ARM64 arch!")
        '''
        if True:
            for part in self.dev.partlist:
                if part['name'] == 'firmware':
                    part['name'] = 'ubi'
                if part['name'] == 'firmware1':
                    part['name'] = 'ubi1'
                if part['name'] == 'kernel':
                    part['name'] = '_kernel'
            print('=== device partlist patched ===')
        '''
        self.img_stock_names = { }
        print('Parse all images...')
        for img in self.imglist:
            self.current_image_fn = img.fn
            self.current_image_pos = 0
            with open(img.fn, "rb") as file:
                image = file.read()
            if img.type == 'stock':
                self.parse_stock_image(image)
            else:
                self.parse_image(image, None)
        self.current_image_fn = None
        pass

    def init_image(self, image, data, err_msg):
        if image.data is None:
            image.data = data
            return
        print(f'ERROR: Image "{image.type}" already initialized!')
        die(err_msg)

    def parse_image(self, image, img_name):
        hr = 0
        #print(image[:4], '   0x%x' % len(image))
        if len(image) < 1*1024*1024:
            raise FwError("Image size too small")
        if image[:4] == UIMAGE_MAGIC:
            hr = self.parse_uimage(image, footer = True)
            print(f'parse_uimage = {hr}')
            if hr >= 2:
                self.init_image(self.fw_img, image, 'Incorrect image! (101)')
            if img_name:
                self.img_stock_names[img_name] = len(image)
        if image[:4] == FDT_MAGIC:
            hr = self.parse_fit(image, footer = True)
            print(f'parse_fit = {hr}')
            if hr >= 2:
                self.init_image(self.fw_img, image, 'Incorrect image! (201)')
            if img_name:
                self.img_stock_names[img_name] = len(image)
        if image[:4] == HSQS_MAGIC:
            hr = 1
            self.init_image(self.rootfs, image, 'Incorrect image! (301)')
            if img_name:
                self.img_stock_names[img_name] = len(image)
        if image[:8] == UBIv1_MAGIC:
            ubivol = self.parse_ubifs(image)
            print(f'parse_ubifs = {len(ubivol)}')
            kk = 0
            if 'kernel' in ubivol:
                self.kernel.into_ubi = True
                kk = self.parse_fit(ubivol['kernel'], footer = False)
                if kk <= 0:
                    die('FIT: Incorrect image! (401)')
                hr += kk
            if 'rootfs' in ubivol:
                self.init_image(self.rootfs, ubivol['rootfs'], 'Incorrect image! (402)')
                self.rootfs.into_ubi = True
                hr += 1
            if 'kernel' in ubivol and ('rootfs' in ubivol or kk == 2):
                self.init_image(self.fw_img, image, 'Incorrect image! (403)')
            if img_name:
                self.img_stock_names[img_name] = len(image)
            #self.save_all_images(req_cmd = False, prefix = "_ubi_")
        if image[:4] == b'cs6c':
            print(f'Images "cs6c" not supported!')
        return hr
        
    def parse_stock_image(self, image):
        data = image
        if data[:4] == b'HDR2':
            die(f'HDR2 stock image not supported!')
        hdr_model_id = int.from_bytes(data[14:16], byteorder='little')
        while True:
            model_id = xqmodel.get_modelid_by_name(gw.device_name)
            if model_id > 0:
                if model_id == hdr_model_id:
                    break
            if gw.device_name in xqmodel.xqModelList:
                sim_model = xqmodel.xqModelList[gw.device_name]['similar']
                if sim_model:
                    sim_model_id = xqmodel.get_modelid_by_name(sim_model)
                    if sim_model_id > 0:
                        if sim_model_id == hdr_model_id:
                            break
            die(f'Loaded stock firmware not compatible with "{gw.device_name}" !!!')
            break
        imglst = [ ]
        for i in range(8):
            p = 0x10 + i * 4
            img = types.SimpleNamespace()
            img.offset = int.from_bytes(data[p:p+4], byteorder='little')
            if img.offset == 0:
                continue
            if img.offset > len(data) - 64:
                die('Incorrect stock image! (2)')
            if data[img.offset:img.offset+4] != b'\xBE\xBA\x00\x00':
                die('Incorrect stock image! (3)')
            img.size = int.from_bytes(data[img.offset+8:img.offset+8+4], byteorder='little')
            img.name = extract_str(data, img.offset+16, maxlen = 64)
            hdr_size = 0x30
            img.data = data[img.offset+hdr_size:img.offset+hdr_size+img.size]
            if len(img.data) != img.size:
                die('Incorrect stock image! (4)')
            self.current_image_pos = img.offset + hdr_size
            #print('offset = {}  header = {}'.format("%08X" % (img.offset + hdr_size), img.data[:4]))
            imglst.append(img)
        
        if not imglst:
            die('Incorrect stock image! (5)')
        
        self.img_stock = True
        self.img_stock_names = { }
        for i, img in enumerate(imglst):
            self.img_stock_names[img.name] = img.size
        
        print(f'Stock image list: {self.img_stock_names}')
        self.img_stock_names = { }
        for i, img in enumerate(imglst):
            #print(img.data[:4], '   0x%x' % len(img.data))
            if img.name == 'xiaoqiang_version':
                txt = img.data.decode('latin_1')
                x = re.search(r"option HARDWARE '(.*?)'", txt)
                if x:
                    self.img_stock_model = x.group(1)
                    print(f'Parse HDR image for "{self.img_stock_model}" router')
            if len(img.data) < 1*1024*1024:  # skip uboot and other files
                continue
            hr = self.parse_image(img.data, img.name)
        
        print(f'Stock image list: {self.img_stock_names}')
        if not self.fw_img.data:
            if not self.kernel.data:
                if not self.rootfs.data:
                    die('Stock image is empty!')
        
        if self.rootfs.data:
            if not self.fw_img.data and not self.kernel.data:
                die('Stock image not contain kernel!')
        
        if not self.kernel.data:
            die('Stock: Kernel section not found!')

    def get_uimage_size(self, img, offset = 0):
        if img[offset:offset+4] != UIMAGE_MAGIC:
            return -1
        offset += 0x0C
        size = int.from_bytes(img[offset:offset+4], byteorder='big')
        return size + 0x40

    def parse_uimage(self, image, offset = 0, footer = True):
        data = image
        if image is None:
            data = self.kernel.data
            offset = 0
        if offset + 512 > len(data):
            die("UIMG: Kernel size too small!")
        if data[offset:offset+4] != UIMAGE_MAGIC:
            die("UIMG: Kernel header is incorrect! (1)")
        kernel_size = self.get_uimage_size(data, offset)
        if kernel_size == 0:
            die("UIMG: Kernel header is incorrect! (2)")
        if offset + kernel_size > len(data):
            die("UIMG: Kernel header is incorrect! (3)")
        data = data[offset:offset+kernel_size]
        if image:
            self.init_image(self.kernel, data, 'UIMG: Found second "kernel" section!')
        else:
            self.kernel.data = data
        if kernel_size < 1*1024*1024:
            die('Kernel image size is too small! (size: {} KB)'.format(kernel_size // 1024))
        pos = 0x1C
        kernel = self.kernel
        kernel.ostype = None
        kernel.hdr.size = kernel_size
        kernel.hdr.arch = int.from_bytes(kernel.data[pos+1:pos+2], byteorder='little')
        kernel.hdr.type = int.from_bytes(kernel.data[pos+2:pos+3], byteorder='little')
        kernel.hdr.comp = int.from_bytes(kernel.data[pos+3:pos+4], byteorder='little')
        kernel.hdr.name = kernel.data[0x20:0x40]
        #print('cpu_arch = {}, img_type = {}, cmp_type = {}'.format(cpu_arch, img_type, cmp_type))
        if kernel.hdr.type == 4:      # IH_TYPE_MULTI
            raise FwError("UIMG: FIXME (IH_TYPE_MULTI)")
        if kernel.hdr.type != 2:      # IH_TYPE_KERNEL
            die(f'UIMG: Kernel type is incorrect! type = {kernel.hdr.type}')
        if kernel.hdr.arch == 5 and self.dev.info.cpu_arch != 'mips':
            die('UIMG: Kernel arch is not MIPS!')
        if kernel.hdr.arch == 2 and self.dev.info.cpu_arch != 'armv7':
            die('UIMG: Kernel arch is not ARMv7!')
        try:
            iname = kernel.hdr.name.decode('ascii')
        except Exception:
            iname = None
        if kernel.hdr.name[0:1] == b'\x03':      # padavan kernel version
            iname = None
            if kernel.hdr.name[2:3] == b'\x03':  # padavan fw version
                ksize = int.from_bytes(kernel.hdr.name[0x1C:0x20], byteorder='big')
                if ksize > 1*1024*1024 and ksize < kernel_size:
                    kernel.ostype = 'padavan'
                    try:
                        iname = kernel.hdr.name[4:0x1B].decode('ascii')
                    except Exception:
                        iname = None
                    kernel_size = ksize
                    #kernel.hdr.size = kernel_size
                    if kernel.data[ksize:ksize+4] != HSQS_MAGIC:
                        die('UIMG: Incorrect padavan kernel image! RootFS not found!')
                    self.init_image(self.rootfs, kernel.data[ksize:], 'UIMG: Padavan: Found second "rootfs" section!')
                    print(f'UIMG: Padavan firmware loaded!')
        if iname is None:
            die(f'UIMG: Incorrect kernel image name! (name: "{kernel.hdr.name}")')
        print(f"UIMG: Kernel image name = '{iname}'")
        kernel.hdr.name = iname
        if kernel.ostype == 'padavan':
            return 2
        if self.img_stock:
            #if kernel.hdr.comp == 0:      # IH_COMP_NONE
            #    die("Stock Kernel must be packed!")
            if iname.find('OpenWrt') >= 0:
                if (iname.find('Linux-3.') > 0 or iname.find('Linux-4.') > 0 or iname.find('Linux-5.') > 0):
                    kernel.ostype = 'stock'
        else:
            if iname.find('PandoraBox') >= 0:
                die('UIMG: Pandora kernel not supported!')
            if iname.find('OpenWrt') >= 0:
                if iname.find('Linux-4.') > 0 or iname.find('Linux-5.') > 0 or iname.find('Linux-6.') > 0:
                    kernel.ostype = 'openwrt'
        if not kernel.ostype:
            die("UIMG: Incorrect kernel image! Can't detect target OS type!")
        if kernel_size > 4*1024*1024 - 128:
            die('UIMG: Kernel image size is too large! (size: {} KB)'.format(kernel_size // 1024))
        if footer:
            hr = self.parse_footer(image, offset + kernel_size)
            if hr >= 1:
                return 2
        return 1
    
    def get_fdt_node(self, dt, path):        
        plist = [ path ]
        if '*' in path:
            plist = [ ]
            plist.append(path.replace('*', '-'))
            plist.append(path.replace('*', '@'))
        for npath in plist:
            try:
                node = dt.get_node(npath)
                return node
            except ValueError:
                pass
        return None
        
    def get_fdt_node_by_name(self, dt, name, compatible = None):
        res = [ ]
        for path, nodes, props in dt.walk():
            nodename = os.path.basename(path)
            if nodename == name:
                if compatible:
                    try:
                        compat = dt.get_property('compatible', path)
                    except ValueError:
                        continue  # go to next node
                    if not compat or compat.value != compatible:
                        continue  # go to next node
                res.append(path)
        return res
        
    def get_fdt_part_list(self, dt, partlist):
        res = [ ]
        if isinstance(partlist, str):
            partlist = dt.get_node(partlist)
        for node in partlist.nodes:
            name = node.get_property('label').value
            addr = node.get_property('reg')[0]
            size = node.get_property('reg')[1]
            readonly = False
            if node.get_property('read-only'):
                readonly = True
            res.append( { 'addr': addr, 'size': size, 'name': name, 'ro': readonly } )
        return res
        
    def get_dtb_part_info(self, partlist, name):
        for i, part in enumerate(partlist):
            if part['name'] == name:
                return part
        return None
    
    def parse_fit(self, image, offset = 0, footer = True):
        kernel = self.kernel
        rootfs = self.rootfs
        data = image
        if image is None:
            data = self.kernel.data
            offset = 0
        dtb_offset = 0
        magic = data[offset:offset+4]
        if magic == b'\x17\x00\x00\x00':
            dtb_offset, fir_size = find_dtb(data, offset, maxsize = 90*1024*1024)
            if not dtb_offset:
                die('FIT: Incorrect image header (0)')
            data = data[dtb_offset:]
            offset = 0
        magic = data[offset:offset+4]
        if magic != FDT_MAGIC:
            die('FIT: Incorrect image (0)')
        fit_size = get_dtb_totalsize(data, offset)
        if fit_size <= 0:
            die('FIT: Incorrect image (1)')
        if fit_size < 200*1024:
            die('FIT: Incorrect image (2)')
        data = data[offset:offset+fit_size]
        if image:
            self.init_image(self.kernel, data, 'FIT: Found second "kernel" section!')
        else:
            self.kernel.data = data
        kernel.ostype = None
        print('FIT size = 0x%X (%d KiB)' % (fit_size, fit_size // 1024))
        fit_dt = fdt.parse_dtb(kernel.data)
        #print(fit_dt.info(props = True))
        #if fit_dt.root.nodes[0]._name != 'images':
        #    die('FIT: Incorrect image (4)')
        fit_name = fit_dt.get_property('description').value
        print(f'FIT: name = "{fit_name}"')
        self.fit_dt = fit_dt
        cfg_list = fit_dt.get_node('/configurations')
        def_cfg_name = cfg_list.get_property('default').value
        print(f'FIT: def_cfg: "{def_cfg_name}"')
        def_cfg = fit_dt.get_node(f'/configurations/{def_cfg_name}')
        def_cfg_desc = def_cfg.get_property('description').value
        print(f'FIT: def_cfg desc = "{def_cfg_desc}"')
        
        ubi_loader = False
        fit_model = ''
        if 'xiaomi_' in def_cfg_desc:
            x = def_cfg_desc.find('xiaomi_')
            fit_model = 'xiaomi,' + def_cfg_desc[x+7:]
            print(f'FIT: model = "{fit_model}"')
        
        def_fdt = def_cfg.get_property('fdt')
        
        if not def_fdt:
            krn1 = self.get_fdt_node(fit_dt, '/images/kernel*1')
            krn1desc = krn1.get_property('description').value
            print(f'KRN: desc = "{krn1desc}"')
            if 'Linux-u-boot' not in krn1desc:
                die('FIT: Incorrect image (5)')
            print(f'Linux-u-boot image founded! (detect ubi-loader)')
            ubi_loader = True
            if not fit_model:
                die('FIT: Incorrect image (5)(1) ')
        else:
            def_fdt_name = def_fdt.value
            print(f'FIT: def_fdt: "{def_fdt_name}"')
            fdt1 = self.get_fdt_node(fit_dt, f'/images/{def_fdt_name}')
            print('FDT: desc = "{}"'.format(fdt1.get_property('description').value))
            print('FDT: type = "{}"'.format(fdt1.get_property('type').value))
            print('FDT: arch = "{}"'.format(fdt1.get_property('arch').value))
            if fdt1.get_property('type').value != 'flat_dt':
                die('FIT: Incorrect image (6)')
            if fdt1.get_property('compression').value != 'none':
                die('FIT: Incorrect image (7)')
            kernel.hdr.arch = fdt1.get_property('arch').value
            krn1 = self.get_fdt_node(fit_dt, '/images/kernel*1')
            print('KRN: desc = "{}"'.format(krn1.get_property('description').value))
            print('KRN: type = "{}"'.format(krn1.get_property('type').value))
            print('KRN: arch = "{}"'.format(krn1.get_property('arch').value))
            print('KRN: compression = "{}"'.format(krn1.get_property('compression').value))
            krn_size = len(krn1.get_property("data"))
            print(f'KRN: data = {krn_size} bytes')

            krn_dt_data = fdt1.get_property('data')
            if hasattr(krn_dt_data, 'raw_value'):
                krn_dt_data = krn_dt_data.raw_value
            else:
                krn_dt_data = krn_dt_data.data
            dt = fdt.parse_dtb(krn_dt_data)
            self.krn_dt = dt
            dt_tree = dt.info(props = True)
            #with open('dt_tree.txt', "w") as file:
            #    file.write(dt_tree)
            dt_compat = dt.get_property('compatible')
            print('FDT:', dt_compat)
            dt_model = dt.get_property('model').value
            print(f'FDT: model = "{dt_model}"')
          
        if ubi_loader:
            dt = None
            dt_compat = [ fit_model ]
            dt_model = None
        
        if not self.img_stock:
            cm = self.check_model(dt_compat, dt_model)
            if cm < 0:
                die(f'FIT: Loaded firmware not compatible with "{gw.device_name}" !!!')
        
        if dt:
            dt_part = self.get_fdt_node_by_name(dt, 'partitions', 'fixed-partitions')
            print(f'FDT: dt_part: {dt_part}')
        
        kernel.fit = True
        if self.img_stock:
            kernel.ostype = 'stock'
        else:
            if 'OpenWrt FIT' in fit_name:
                kernel.ostype = 'openwrt'
        if not kernel.ostype:
            die('FIT: Currently supported only OpenWrt FIT images!')
        
        rootfs1 = self.get_fdt_node(fit_dt, '/images/rootfs*1')
        if rootfs1:
            die('FIT: Founded "rootfs-1" node. Not supported!')
        
        initrd1 = self.get_fdt_node(fit_dt, '/images/initrd*1')
        if initrd1:
            print('FIT: Founded "initrd-1" node')
            iname = initrd1.get_property('description').value
            print(f'FIT: initrd image name: "{iname}"')
            if self.img_stock:
                die('FIT: Error (4566)')
            initrd1_data = initrd1.get_property('data')
            self.init_image(rootfs, initrd1_data.data, 'FIT: Found second "rootfs" section! (initrd)')
            kernel.initrd = True
            rootfs.initrd = True
            if kernel.into_ubi:
                rootfs.into_ubi = True
            return 2
            
        if not footer and krn_size > 6*1024*1024 and kernel.ostype == 'openwrt':
            print(f'FIT: detect initrd into kernel image')
            self.init_image(rootfs, b'0' * 1024, 'FIT: Found Second "rootfs" section! (InitRD)')
            kernel.initrd = True
            rootfs.initrd = True
            if kernel.into_ubi:
                rootfs.into_ubi = True
            return 2
            
        if footer:
            hr = self.parse_footer(image, offset + fit_size)
            if hr >= 1:
                return 2
        return 1
        
    def parse_footer(self, image, offset, init = True):
        if len(image) - offset < 1*1024*1024:
            return 0
        pos_list = { }
        pos = image.find(UBIv1_MAGIC, offset)
        if pos >= 0:
            pos_list[pos] = 'ubifs'
        pos = image.find(HSQS_MAGIC, offset)
        if pos >= 0:
            pos_list[pos] = 'ubifs'
        if not pos_list:
            if not self.rootfs.data:
                print("Footer: WARNING: rootfs not found")
            return 0
        pos_list = dict(sorted(pos_list.items()))
        rootfs_offset = next(iter(pos_list))
        if pos_list[rootfs_offset] == 'ubifs':
            print('Footer: UBI offset = 0x%X' % rootfs_offset)
        if pos_list[rootfs_offset] == 'hsqs':
            print('Footer: hsqs offset = 0x%X' % rootfs_offset)
        rootfs_data = image[rootfs_offset:]
        if init:
            self.init_image(self.rootfs, rootfs_data, 'Footer: Found second "rootfs" section!')
        else:
            self.rootfs.data = rootfs_data
        return 1

    def parse_ubifs(self, ubifs_image, init = True):
        from ubireader.ubi import ubi
        from ubireader.ubi import ubi_base
        from ubireader.ubi_io import ubi_file
        from ubireader import settings
        from ubireader.ubi.defines import UBI_EC_HDR_MAGIC
        from ubireader.ubifs.defines import UBIFS_NODE_MAGIC
        from ubireader.utils import guess_filetype, guess_start_offset, guess_leb_size, guess_peb_size 

        settings.logging_on = False
        settings.logging_on_verbose = False
        settings.warn_only_block_read_errors = False
        settings.ignore_block_header_errors = False
        settings.uboot_fix = False 
        path = self.current_image_fn
        start_offset = self.current_image_pos
        filetype = guess_filetype(path, start_offset) 
        print('UBI: filetype:', filetype)
        if filetype != UBI_EC_HDR_MAGIC:
            die('UBI: File does not look like UBI data.')
        block_size = guess_peb_size(path)
        if not block_size:
            die('UBI: Block size could not be determined.')  
        ufile_obj = ubi_file(path, block_size, start_offset)
        #ubi_obj = ubi_base(ufile_obj) 
        ubi_obj = ubi(ufile_obj) 
        print('UBI: Decoding UBIFS...')
        kernel_volume = None
        rootfs_volume = None
        for image in ubi_obj.images:
            for volume in image.volumes:
                data = b""
                vol = image.volumes[volume]
                for block in vol.reader(ubi_obj):
                    data += block
                if volume == 'kernel' and len(data) > 1024:
                    kernel_volume = data
                if volume == 'rootfs' and len(data) > 1024:
                    rootfs_volume = data
                if volume == 'ubi_rootfs' and len(data) > 1024:
                    rootfs_volume = data
                print(f'UBI:   volume: "{volume}" \t size: {len(data)} ')
        ufile_obj.close()
        out = { }
        if kernel_volume:
            out['kernel'] = kernel_volume
        if rootfs_volume:
            out['rootfs'] = rootfs_volume
        return out

    def unpack_kernel(self):
        kernel = self.kernel
        data2 = kernel.data[0x40:]
        img_comp = kernel.hdr.comp
        if img_comp == 0:
            loader_data = data2[:0x8000]
            x1 = loader_data.find(b'Incorrect LZMA stream properties!') # b'OpenWrt kernel loader for MIPS based SoC'
            x2 = loader_data.find(b'XZ-compressed data is corrupt')
            if x1 < 0 and x2 < 0:
                die('Kernel image not compressed! It is very strange!')
            if x1 > 0 and x2 > 0:
                die("Strange error! (1)")
            if x1 > 0:
                k1 = loader_data.find(b'\x00\x6D\x00\x00', x1)   # LZMA prefix
                k2 = loader_data.find(b'\x00\x5D\x00\x00', x1)   # LZMA prefix
                if k1 < 0 and k2 < 0:
                    die("Can't unpack kernel image! (lzma loader)")
                if k1 > 0 and k2 > 0:
                    k = min(k1, k2)
                else: 
                    k = k1 if k1 > 0 else k2
                data2 = data2[k+1:]
                img_comp = 3  #  IH_COMP_LZMA
            if x2 > 0:
                k = loader_data.find(b'\xFD7zXZ\x00', x2)   # XZ prefix
                if k < 0:
                    die("Can't unpack kernel image! (XZ loader)")
                data2 = data2[k:]
                img_comp = 5    # IH_COMP_XZ
        if img_comp == 3:   # IH_COMP_LZMA
            kernel.data2 = lzma.decompress(data2)
        if img_comp == 5:   # IH_COMP_XZ
            kernel.data2 = lzma.decompress(data2, lzma.FORMAT_XZ)
        if kernel.data2:
            print(f'File "kernel_unpacked.bin" saved! (size: {len(kernel.data2)})')
            with open(self.dn_tmp + '_kernel_unpacked.bin', "wb") as file:
                file.write(kernel.data2)
        else:
            print(f'WARNING: cannot unpack kernel image (comp = {img_comp})')
        return 1

    def prepare_for_padavan(self):
        dev = self.dev
        kernel = self.kernel
        rootfs = self.rootfs
        if kernel.data[:4] != UIMAGE_MAGIC:
            die("Padavan support only UImage firmware")
        if self.install_method != 100:
            die('Padavan firmware required install_method = 100')
        kernel.addr = 0x600000
        part = dev.get_part_by_addr(kernel.addr)
        if not part:
            die('Partition for addr {} not found'.format("0x%X" % kernel.addr))
        part_size = part['size']
        if len(kernel.data) > part_size:
            rootfs.data = kernel.data[part_size:]
            kernel.data = kernel.data[:part_size]
            rootfs.addr = kernel.addr + part_size
            part2 = dev.get_part_by_addr(rootfs.addr)
            if not part2:
                die('Partition for addr {} not found'.format("0x%X" % rootfs.addr))
        else:
            rootfs.addr = kernel.addr + part_size
            part2 = dev.get_part_by_addr(rootfs.addr)
            if not part2:
                die('Partition for addr {} not found'.format("0x%X" % rootfs.addr))
            part2_size = part2['size']
            if part2_size > 8*1024*1024:
                part2_size = 8*1024*1024
            rootfs.data = b'\x00' * part2_size

    def check_model(self, compat, model):
        if not compat:
            return 0  # unknown
        compat_list = compat
        if isinstance(compat, str):
            compat_list = [ x.strip() for x in compat.split(';') ]
        dn = gw.device_name
        if dn not in xqmodel.xqModelList:
            return 0  # unknown
        model = xqmodel.xqModelList[dn]
        altname = model['altname']
        if not altname:
            return 0  # unknown
        for compat in compat_list:
            sep = compat.find(',')
            if sep >= 0:
                compat = compat[sep+1:]
            if compat.startswith(altname):
                return 1  # compatiple firmware
        return -1  # NOT COMPATIBLE !!!

    def prepare_for_openwrt_100(self):
        dev = self.dev
        kernel = self.kernel
        rootfs = self.rootfs
        if self.install_method != 100:
            die('OpenWRT firmware required install_method = 100')
        dtb = get_dtb(kernel.data, 32)
        if not dtb and kernel.data2:
            dtb = get_dtb(kernel.data2, 0)
        if not dtb:
            die("Can't found FDT (flattened device tree)")
        dt = fdt.parse_dtb(dtb)
        #print(dt.info(props = True))
        dt_compat = dt.get_property('compatible')
        print('FDT:', dt_compat)
        dt_model = dt.get_property('model').value
        print(f'FDT: model = "{dt_model}"')
        cm = self.check_model(dt_compat, dt_model)
        if cm < 0:
            die(f'Loaded OpenWRT firmware not compatible with "{gw.device_name}" !!!')
        self.dt = dt
        dt_part = self.get_fdt_node_by_name(dt, 'partitions', 'fixed-partitions')
        print(f'FDT: dt_part: {dt_part}')
        if len(dt_part) == 0:
            die("Cannot found fixed-partitions node into FDT")
        if len(dt_part) > 1:
            die("Several nodes were found with fixed-partition info")
        dt_part = dt_part[0]
        partlist = self.get_fdt_part_list(dt, dt_part)
        #print(partlist)
        kernel_part = self.get_dtb_part_info(partlist, "kernel")
        if not kernel_part:
            die('Cannot found "kernel" partition in DTB!')
        print('part kernel = 0x%X (size: 0x%X)' % (kernel_part['addr'], kernel_part['size']))
        kernel.addr = kernel_part['addr']
        part = dev.get_part_by_addr(kernel.addr)
        if not part:
            die("Can't support flashing kernel to addr 0x%X" % kernel.addr)
        kernel2_part = self.get_dtb_part_info(partlist, "kernel_dup")
        if not kernel2_part:
            kernel2_part = self.get_dtb_part_info(partlist, "kernel_stock")
        if not kernel2_part:
            die('Cannot found "kernel_dup"/"kernel_stock" partition in DTB!')
        print('part kernel2 = 0x%X (size: 0x%X)' % (kernel2_part['addr'], kernel2_part['size']))
        kernel.addr2 = kernel2_part['addr']
        part = dev.get_part_by_addr(kernel.addr2)
        if not part:
            die("Can't support flashing kernel to addr 0x%X" % kernel.addr2)
        ubi_part = self.get_dtb_part_info(partlist, "ubi")
        if not ubi_part:
            die('Cannot found "ubi" partition in DTB!')
        print('part ubi = 0x%X (size: 0x%X)' % (ubi_part['addr'], ubi_part['size']))
        rootfs.addr = ubi_part['addr']
        part = dev.get_part_by_addr(rootfs.addr)
        if not part:
            die("Can't support flashing ubi to addr 0x%X" % rootfs.addr)
        if len(rootfs.data) + 0x8000 >= part['size']:
            die("Partition '%s' is too small (data size: 0x%X, part size: 0x%X)" % (part['name'], len(rootfs.data), part['size']))

    def prepare_for_stock(self):
        dev = self.dev
        kernel = self.kernel
        rootfs = self.rootfs

    def prepare_data(self):
        dev = self.dev
        kernel = self.kernel
        rootfs = self.rootfs
        fw_img = self.fw_img

        if not kernel.data:
            die('Kernel data not found!')

        if not rootfs.data:
            die('RootFS data not found!')

        dev.get_bootloader()
        if not dev.bl.img:
            die("Can't dump current bootloader!")
        
        dev.get_env_list()
        if not dev.env.fw.data or dev.env.fw.len <= 0:
            die("Can't dump current NVRAM params!")
        
        print(f"current flag_boot_rootfs = {dev.rootfs.num}")
        self.install_fw_num = None

        self.install_method = 0
        
        kernel_num  = dev.get_part_num("kernel")
        kernel0_num = dev.get_part_num("kernel0")
        kernel1_num = dev.get_part_num("kernel1")
        rootfs_num  = dev.get_part_num("rootfs")
        rootfs0_num = dev.get_part_num("rootfs0")
        rootfs1_num = dev.get_part_num("rootfs1")
        if kernel0_num > 0 and kernel1_num > 0 and rootfs1_num > 0:
            self.install_method = 100
            self.install_parts = [ ]

        osl_num = dev.get_part_num("OS1")
        os2_num = dev.get_part_num("OS2")
        if osl_num > 0 and os2_num > 0 and rootfs_num > 0:
            self.install_method = 50
            self.install_parts = [ 'OS1', 'OS2' ]
            die("Unsupported install method 50")

        rootfs_1_num = dev.get_part_num("rootfs_1")
        if rootfs_num > 0 and rootfs_1_num > 0:
            self.install_method = 200  # qcom ipq807x
            self.install_parts = [ 'rootfs', 'rootfs_1' ]
            if not fw_img.data or not kernel.data or not rootfs.data:
                die('Cannot firmware image! (200)')
            if not kernel.into_ubi:
                die('Kernel image must be into UBIFS (200)')
            if kernel.ostype == 'openwrt':
                if not kernel.initrd:
                    die('OpenWRT: Supported only InitRamFS images (200)')

        firmware0_num = dev.get_part_num('firmware')
        firmware1_num = dev.get_part_num('firmware1')
        if firmware0_num > 0 and firmware1_num > 0:
            self.install_method = 300
            self.install_parts = [ 'firmware', 'firmware1' ]
            if not kernel.data:
                die('Cannot kernel image! (300)')
            if not rootfs.data:
                die('Cannot rootfs image! (300)')
            if not fw_img.data:
                print(f'WARNING: Image "fw_img" not found')
                kernel_addr = dev.partlist[kernel_num]['addr']
                rootfs_addr = dev.partlist[rootfs_num]['addr']
                offset = rootfs_addr - kernel_addr
                if kernel.data_size >= offset:
                    die('Kernel image very huge! (300)')
                if offset <= 0:
                    die('Error 301')
                pad_data = b"\x00" * (offset - kernel.data_size)
                fw_img.data = kernel.data + pad_data + rootfs.data

        ubi0_num = dev.get_part_num('ubi')
        ubi1_num = dev.get_part_num('ubi1')
        if ubi0_num > 0 and ubi1_num > 0:
            self.install_method = 400  # mtk filogic
            self.install_parts = [ 'ubi', 'ubi1' ]
            if not fw_img.data or not kernel.data or not rootfs.data:
                die('Cannot firmware image! (400)')
            if not kernel.into_ubi:
                die('Kernel image must be into UBIFS (400)')
            if kernel.ostype == 'openwrt':
                if not kernel.initrd:
                    die('OpenWRT: Supported only InitRamFS images (400)')

        print(f'install_method = {self.install_method}')
        if self.install_method <= 0:
            die('Cannot detect install method')
            
        if kernel.data[:4] == UIMAGE_MAGIC:
            self.unpack_kernel()

        if self.img_stock:
            if dev.rootfs.num is None or dev.rootfs.num < 0:
                die("Can't detect current booted rootfs!")
            self.install_fw_num = 1 - dev.rootfs.num
            self.prepare_for_stock()
        else:
            self.install_fw_num = 0
            
            if kernel.ostype == 'padavan':
                self.install_fw_num = None
                self.prepare_for_padavan()

            if kernel.ostype == 'openwrt':
                if self.install_method == 100:
                    self.prepare_for_openwrt_100()

        self.save_all_images(req_cmd = False, prefix = "_")

        print("--------- prepare command lines -----------")
        
        if self.install_method == 100:
            if self.img_stock:
                kernel.partname = "kernel{}".format(self.install_fw_num)
                kp = dev.get_part_num(kernel.partname)
                if kp <= 0:
                    die("Partition {} not found!".format(kernel.partname))
                kernel.addr = dev.partlist[kp]['addr']
                kernel.cmd = 'mtd -e "{part}" write "{bin}" "{part}"'.format(part=kernel.partname, bin=kernel.fn_remote)
                rootfs.partname = "rootfs{}".format(self.install_fw_num)
                rp = dev.get_part_num(rootfs.partname)
                if rp <= 0:
                    die("Partition {} not found!".format(rootfs.partname))
                rootfs.addr = dev.partlist[rp]['addr']
                rootfs.cmd = 'mtd -e "{part}" write "{bin}" "{part}"'.format(part=rootfs.partname, bin=rootfs.fn_remote)
            else:
                fw_addr = 0
                if not kernel.addr or not rootfs.addr:
                    die('Unknown addr for flashing!')
                part = dev.get_part_by_addr(kernel.addr)
                if not part:
                    die('Partition for addr {} not found'.format("0x%X" % kernel.addr))
                if part['size'] < len(kernel.data):
                    die('Partition size is too small!')
                kernel.partname = part['name']
                kernel.cmd = 'mtd -e "{part}" write "{bin}" "{part}"'.format(part=kernel.partname, bin=kernel.fn_remote)
                if kernel.addr2:
                    part = dev.get_part_by_addr(kernel.addr2)
                    if not part:
                        die('Partition for addr {} not found'.format("0x%X" % kernel.addr2))
                    if part['size'] < len(kernel.data):
                        die('Partition size is too small!')
                    kernel.cmd += ' ; mtd -e "{part}" write "{bin}" "{part}"'.format(part=part['name'], bin=kernel.fn_remote)
                part = dev.get_part_by_addr(rootfs.addr)
                if not part:
                    die('Partition for addr {} not found'.format("0x%X" % rootfs.addr))
                if part['size'] < len(rootfs.data):
                    die('Partition size is too small!')
                rootfs.partname = part['name']
                rootfs.cmd = 'mtd -e "{part}" write "{bin}" "{part}"'.format(part=rootfs.partname, bin=rootfs.fn_remote)

        if self.install_method in [ 200, 300, 400 ]:
            if not self.img_stock and self.install_method == 300:
                self.install_fw_num = 0
            else:
                if dev.rootfs.num is None or dev.rootfs.num < 0:
                    die("Cannot detect current booted rootfs! (X)")
                self.install_fw_num = 1 - dev.rootfs.num
            fw_img.partname = self.install_parts[self.install_fw_num]
            fw_part = dev.get_part(fw_img.partname)
            fw_img.addr = fw_part['addr']
            fw_img.cmd = 'mtd -e "{part}" write "{bin}" "{part}"'.format(part=fw_img.partname, bin=fw_img.fn_remote)
            kernel.cmd = None
            rootfs.cmd = None
            #if 'ro' not in fw_part:
            #    die(f'Cannot get readonly flag for partition "{fw_img.partname}"')
            if 'ro' in fw_part and fw_part['ro'] == True:
                die(f'Target partition "{fw_img.partname}" has readonly flag')

        self.save_all_images(req_cmd = True, prefix = "")
    
    def save_image_to_disk(self, image, req_cmd = True, prefix = ""):
        if image.data:
            if req_cmd and not image.cmd:
                return
            dname = os.path.dirname(image.fn_local)
            fname = os.path.basename(image.fn_local)
            with open(f'{dname}/{prefix}{fname}', "wb") as file:
                file.write(image.data)
                
    def save_all_images(self, req_cmd = True, prefix = ""):
        for i, (iname, img) in enumerate(self.imglst.items()):
            self.save_image_to_disk(img, req_cmd, prefix)
    
    def process_bootloader_env(self, fw_num):
        global gw
        dev = self.dev
        kernel = self.kernel
        rootfs = self.rootfs
        if dev.bl.type == 'breed':
            fw_addr = None
            if 'autoboot.command' in dev.env.breed.var:
                cmd = dev.env.breed.var['autoboot.command']
                lst = cmd.split(' ')
                if len(lst) == 3:
                    try:
                        fw_addr = int(lst[2].strip(), 16)
                    except Exception:
                        fw_addr = None
            if fw_addr and fw_addr == kernel.addr:
                print("Breed boot address is correct! (addr: 0x%X)" % fw_addr)
            elif self.img_write:
                if fw_num is not None:
                    fw_addr = activate_boot.breed_boot_change(gw, dev, fw_num, None, None)
                else: 
                    fw_addr = activate_boot.breed_boot_change(gw, dev, None, kernel.addr, None)
                pass

    def flash(self):
        global gw
        dev = self.dev
        fw_img = self.fw_img
        kernel = self.kernel
        rootfs = self.rootfs

        if not fw_img.cmd and not kernel.cmd and not rootfs.cmd:
            die("Flashing recipe unknown!")

        print("------------- flash images -------------")
        
        self.process_bootloader_env(self.install_fw_num)

        gw.set_timeout(12)
        if fw_img.cmd:
            gw.upload(fw_img.fn_local, fw_img.fn_remote, md5chk = 2)
        if kernel.cmd:
            gw.upload(kernel.fn_local, kernel.fn_remote, md5chk = 2)
        if rootfs.cmd:
            gw.upload(rootfs.fn_local, rootfs.fn_remote, md5chk = 2)

        if self.img_write:
            cmd = [ ]
            cmd.append("nvram set bootdelay=3")
            cmd.append("nvram set boot_wait=on")
            cmd.append("nvram set bootmenu_delay=5")
            cmd.append("nvram set ssh_en=1")
            cmd.append("nvram set uart_en=1")
            cmd.append("nvram commit")
            rc = gw.run_cmd(';'.join(cmd), timeout = 8)
            if rc is None:
                die(f'Cannot change nvram parameters!')

        if fw_img.cmd:
            self.flash_data_to_mtd('firmware', fw_img, timeout = 60)
        
        if kernel.cmd:
            self.flash_data_to_mtd('kernel', kernel, timeout = 34)

        if rootfs.cmd:
            self.flash_data_to_mtd('rootfs', rootfs, timeout = 60)

        if not self.img_write:
            die('===== Flash TEST is over =====')

        if self.install_fw_num is not None:
            print("Run scripts for change NVRAM params...")
            activate_boot.uboot_boot_change(gw, self.install_fw_num)
            if hasattr(kernel, 'partname') and kernel.partname:
                print(f'Boot from partition "{kernel.partname}" activated. [{self.install_fw_num}]')
            else:
                print(f'Boot from firmware [{self.install_fw_num}] activated.')
            nvram = self.dev.get_nvram()
            if 'flag_boot_rootfs' not in nvram:
                die(f'Parameter "flag_boot_rootfs" not founeded into nvram')
            flag_boot_rootfs = int(nvram['flag_boot_rootfs'])
            if flag_boot_rootfs != self.install_fw_num:
                die(f'Parameter flag_boot_rootfs = {flag_boot_rootfs} , but expected [{self.install_fw_num}]')

        print("The firmware has been successfully flashed!")

        if self.install_method == 100:
            gw.run_cmd("sync ; umount -a", timeout = 5)
            print("Please, reboot router!")
        else:
            import ssh2
            print('Send command "reboot" via SSH/Telnet ...')
            try:
                gw.run_cmd("reboot -f", die_on_error = False)
                print("Forced REBOOT activated!")
            except ssh2.exceptions.SocketRecvError as e:
                print("Forced REBOOT Activated!")
                pass 

    def flash_data_to_mtd(self, img_name, img: Image, timeout, check = True):
        print(f'Writing {img_name} image to addr 0x{img.addr:08X} ...')
        print(f"  {img.cmd}")
        partname = img.partname
        size = os.path.getsize(img.fn_local)
        size = (size // 4096) * 4096
        md5_orig = self.gw.get_md5_for_local_file(img.fn_local, size)
        if not self.img_write:
            return True
        rc = self.gw.run_cmd(img.cmd, timeout = timeout, die_on_error = True)
        if rc is None:
            print(f'  ERROR: cannot flash data to partition "{partname}"')
            return False
        if check:
            md5 = self.dev.get_md5_for_mtd_data(partname, offset = 0, size = size)
            if md5 != md5_orig:
                die(f'Flashed data corrupted! Partition "{partname}" md5: {md5}')
                return False
        return True

# =====================================================================

xf = XqFlash()

xf.found_all_images()
xf.parse_all_images()

print(f"fw_img: {xf.fw_img.data_size // 1024} KiB |",
      f"kernel: {xf.kernel.data_size // 1024} KiB |",
      f"rootfs: {xf.rootfs.data_size // 1024} KiB ")

xf.prepare_data()

print(f"fw_img: {xf.fw_img.data_size // 1024} KiB |",
      f"kernel: {xf.kernel.data_size // 1024} KiB |",
      f"rootfs: {xf.rootfs.data_size // 1024} KiB")

xf.flash()


