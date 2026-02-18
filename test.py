#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XMiR Patcher environment diagnostic test.
Checks imports, configuration, and device availability.
"""

import sys

def main():
    print("=" * 50)
    print("XMiR Patcher — Environment Diagnostic")
    print("=" * 50)

    # 1. Import tests
    print("\n[1] Imports...")
    try:
        import xmir_base
        print("    xmir_base — OK")
    except Exception as e:
        print("    xmir_base — ERROR:", e)
        return 1

    try:
        import gateway
        print("    gateway — OK")
    except Exception as e:
        print("    gateway — ERROR:", e)
        return 1

    try:
        import xqmodel
        print("    xqmodel — OK")
    except Exception as e:
        print("    xqmodel — ERROR:", e)
        return 1

    try:
        import read_info
        print("    read_info — OK")
    except Exception as e:
        print("    read_info — ERROR:", e)

    # 2. Configuration
    print("\n[2] Configuration...")
    try:
        gw = gateway.Gateway(detect_device=False, detect_ssh=False)
        print("    Device IP: {}".format(gw.ip_addr))
        print("    SSH port: {}".format(gw.ssh_port))
        if gw.passw:
            print("    Password (memcfg): saved")
        else:
            print("    Password (memcfg): not set")
    except PermissionError as e:
        print("    Shared memory error (possibly sandboxed): {}".format(e))
        gw = None
    except Exception as e:
        print("    Initialization error: {}".format(e))
        gw = None

    # 3. Device detection (without SSH)
    print("\n[3] Device detection...")
    if gw:
        try:
            gw.detect_device()
            if gw.status >= 1:
                print("    Device found: {}".format(gw.device_name))
                print("    ROM: {} {}".format(gw.rom_version or "?", gw.rom_channel or ""))
            else:
                print("    Device not found (IP: {})".format(gw.ip_addr))
        except SystemExit:
            print("    Device unavailable or requires initial setup via WEB UI")
        except Exception as e:
            print("    Error: {}".format(e))
    else:
        print("    Skipped (Gateway not initialized)")

    # 4. Supported models
    print("\n[4] Known models (examples): R3G, R3P, RM2100, R4A, WR30...")
    print("    Total in xqmodel: {} models".format(len(xqmodel.xqModelList)))

    # 5. Unsupported models
    print("\n[5] Unsupported features:")
    print("    BE3600, BE2600 2.5G and other Wi-Fi 7 (BE-series) routers:")
    print("    — Reason: use Qualcomm IPQ (ARM), not MediaTek MT7621 (MIPS)")
    print("    — Breed bootloader and certain features are designed only for MIPS")
    print("    — Supported models: R3G, R3P, RM2100")

    print("\n" + "=" * 50)
    print("Diagnostic completed.")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())