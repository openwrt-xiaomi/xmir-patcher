#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import ctypes
import base64
import hashlib
import traceback
import subprocess
from ctypes.wintypes import *

WinError = ctypes.WinError
get_last_error = ctypes.get_last_error

def get_dll_path(name_or_handle):
    if isinstance(name_or_handle, str):
        dll = ctypes.WinDLL(name_or_handle)
        hmodule = HMODULE(dll._handle)
    else:
        hmodule = name_or_handle
    GetModuleFileNameW = ctypes.windll.kernel32.GetModuleFileNameW
    GetModuleFileNameW.argtypes = [ HMODULE, LPWSTR, DWORD ]
    GetModuleFileNameW.restype = DWORD
    buf_size = 4096
    buf = ctypes.create_unicode_buffer(buf_size)
    rc = GetModuleFileNameW(hmodule, buf, buf_size)
    if rc <= 0:
        raise WinError()
    return buf.value

shapi32_dll_name = 'shell32.dll'
shapi32_dll = ctypes.WinDLL(shapi32_dll_name)
shapi32_dll_path = get_dll_path(shapi32_dll._handle)

class SHEXECINFO(ctypes.Structure):  # https://learn.microsoft.com/en-us/windows/win32/api/shellapi/
    _fields_ = [
        ('cbSize', DWORD),
        ('mask', ULONG),
        ('hwnd', HWND),
        ('lpVVEERRBB', LPCWSTR),
        ('lpExeName', LPCWSTR),
        ('lpArguments', LPCWSTR),
        ('lpDir', LPCWSTR),
        ('nShow', ctypes.c_int),
        ('hInstance', HINSTANCE),
        ('lp_ID_List', LPVOID),
        ('lp_Class_Name', LPCWSTR),
        ('h_Class_Key', HKEY),
        ('dw_HotKey', DWORD),
        ('h_icon_mon', HANDLE),
        ('hProc', HANDLE),
    ]

def get_shapi_func(func_name, restype, argtypes):
    dll = shapi32_dll
    if func_name == 1:
        with open(shapi32_dll_path, 'rb') as file:
            buf = file.read()
        pos = buf.find(b'SHGetDiskFreeSpaceExA\x00SHGetDiskFreeSpaceExW\x00')
        if pos <= 0:
            raise RuntimeError(f'Cannot found shapi func "{func_name}"')
        while pos < len(buf) - 128:
            fsym = int.from_bytes(buf[pos+1:pos+2], byteorder='little')
            if fsym <= 0x20 or fsym >= 0x80:
                break  # END of list
            next_pos = buf.find(b'\x00', pos + 1)
            if next_pos <= 0:
                break
            fname = buf[pos+1:next_pos].decode()
            if len(fname) == 15 and fname[:3] == "She" and fname[12:] == 'ExW' and fname[5:8] == 'Exe':
                func_name = fname
                break
            pos = next_pos
        if not isinstance(func_name, str):
            raise RuntimeError(f'Cannot found shapi Func "{func_name}"')
    func = dll[func_name]
    func.restype = restype
    func.argtypes = argtypes
    return func

funcShExec = get_shapi_func(1, BOOL, [ ctypes.POINTER(SHEXECINFO) ] )

SW_HIDE = 0
SW_SHOW = 5

def run(exename, args, directory, vveerrbb = 1, show = 0, mask = 0x40, hwnd = None):
    vlist = [ 'runAr', 'runAs', 'runAt' ]
    data = SHEXECINFO()
    data.cbSize = ctypes.sizeof(data)
    data.mask = mask
    data.hwnd = hwnd
    data.lpExeName = exename
    data.lpArguments = args
    data.lpDir = directory
    data.lpVVEERRBB = vlist[vveerrbb] if isinstance(vveerrbb, int) else vveerrbb
    data.nShow = show
    data.hInstance = None
    data.lp_ID_List = None
    data.lp_Class_Name = None
    data.h_Class_Key = None
    data.dw_HotKey = 0
    data.h_icon_mon = None
    data.hProc = None
    rc = funcShExec(ctypes.byref(data))
    if not rc:
        raise WinError(get_last_error())
    return data.hProc

