# Installing OpenWrt on the Xiaomi AX3000T **RD03v2** (IPQ5018)

> **Read this before following any AX3000T tutorial.** The RD03v2 is a *different machine*
> from the RD03/RD23. Those are MediaTek Filogic 820 with `mtd8`/`mtd9` and
> `flag_boot_rootfs`. This one is Qualcomm IPQ5018 with `ubi_kernel`/`rootfs`. **The
> `mtd8`/`mtd9` commands in the RD03 guides will not work here and can brick the unit.**

Identify the unit before you start: RD03v2 packaging has a barcode ending `706330`, SKU
`DVB4510CN`, and `init_info` reports `"hardware":"RD03v2"` / `"model":"xiaomi.router.rd03v2"`.

---

## Why the install is two steps

OpenWrt cannot rewrite the flash it is currently running from. So the install is always:

1. **Boot an initramfs in RAM** — a throwaway system that lives entirely in memory.
2. **`sysupgrade` the squashfs image** from that RAM system — *this* is the persistent install.

XMiR-Patcher automates step 1. Step 2 is one `sysupgrade` command. This is the same shape as
the official AX3000T instructions; only the artifacts and slot names differ.

---

## Step 1 — root stock and flash the initramfs

Stock firmware must be **MiWiFi/XiaoQiang 2.0.28** (the version these images are built for).

### 1a. Put exactly one image in `firmware/`

Use the **initramfs** image — XMiR-Patcher accepts only initramfs for OpenWrt
(`OpenWRT: Supported only InitRamFS images`):

```
openwrt-qualcommax-ipq50xx-xiaomi_mi-router-ax3000t-v2-initramfs-factory.ubi
```

**If you have no Ethernet cable**, use the `-wifi` variant instead:

```
openwrt-qualcommax-ipq50xx-xiaomi_mi-router-ax3000t-v2-initramfs-factory-wifi.ubi
```

It beacons `OpenWrt-RD03v2-Installer` (WPA2, key `rd03v2install`) while running from RAM. The
plain image comes up with **both radios disabled**, so over Wi-Fi only you would lose the unit.

> **Only one image file may be in `firmware/`.** `install_fw.py` aborts with *"Too many
> different files in directory"* when more than one UBI image is present — and both the
> initramfs and the squashfs-factory image classify as UBI. Do not unzip the whole release in
> there.

### 1b. Run it

```sh
./run.sh install_fw.py
```

It will, in order:

- root the stock firmware (the API-RCE path, then permanent SSH),
- verify the image against the running device (`xiaomi,mi-router-ax3000t-v2`, `qcom,ipq5018`),
- **write the initramfs to the *inactive* A/B slot** — the console prints the exact address,
  e.g. `mtd -e "rootfs_1" write ... "rootfs_1"` at `0x02880000`,
- read it back and compare, then set `flag_boot_rootfs` to that slot and reboot.

The slot it is *currently booted from* is never written, so stock remains intact.

### 1c. Confirm you are in RAM

```sh
ssh root@192.168.1.1
. /lib/upgrade/common.sh; rootfs_type       # must print: tmpfs
```

If it prints `squashfs` or `overlay` you are **not** in RAM — do not run `sysupgrade`, it would
erase the system you are running from.

## Step 2 — the permanent install

```sh
# from your computer
cat openwrt-qualcommax-ipq50xx-xiaomi_mi-router-ax3000t-v2-squashfs-sysupgrade.bin \
  | ssh root@192.168.1.1 'cat > /tmp/fw.bin'
ssh root@192.168.1.1 'sha256sum /tmp/fw.bin'      # compare with the release sha256sums.txt
ssh root@192.168.1.1 'sysupgrade -n /tmp/fw.bin'
```

Note: use the pipe above rather than `scp` — the RAM image ships no `sftp-server`, so modern
`scp` fails with *"/usr/libexec/sftp-server: not found"*.

`-n` means "do not keep configuration" — correct for a first install.

The box then erases and writes the squashfs to NAND and reboots into the installed system.

## After the install — you will need Ethernet

**The installed system comes up with Wi-Fi disabled**, like any default OpenWrt install. The
installer SSID is gone and nothing is beaconing. Connect a cable to a LAN port and browse to
`http://192.168.1.1`, or `ssh root@192.168.1.1` (no password until you set one), then enable
the radios and set the country code.

This is the step people mistake for a brick. It is not — the unit is up, its radios are simply
off by configuration.

---

## Partition layout (why the slot matters)

| | Start | Size | |
|---|---|---|---|
| stock `rootfs` (slot 0) | `0x0a80000` | 30M | kernel + `ubi_rootfs` |
| stock `rootfs_1` (slot 1) | `0x2880000` | 30M | the spare slot |
| stock `overlay` | `0x4680000` | 57M | config / data |
| OpenWrt `ubi_kernel` | `0x0a80000` | 36M | |
| OpenWrt `rootfs` | `0x2e80000` | 81M | |

Stock keeps a real A/B pair with exactly one slot attached at runtime. Writing the initramfs to
the slot you are *not* booted from is what makes this reversible: if the new slot fails to boot,
stock is still there.

## Recovery

- **Boot fails / no network** — the stock slot is untouched. Use the U-Boot TFTP recovery
  (hold reset while powering on; the unit asks for a TFTP server at `192.168.31.100` and
  downloads a file named from its assigned IP, e.g. `C0A81F02.img`). Recovery enforces
  Xiaomi's RSA signature, so only genuine stock firmware flashes.
- **Back to stock** — flash the genuine `miwifi_rd03v2_*_2.0.28.bin` from Xiaomi's CDN via the
  same recovery path, or restore the stock UBI over the installed system.

## Verified

- XMiR-Patcher `install_fw.py` accepts the RD03v2 initramfs and produces a correct recipe
  (`install_method = 200`, inactive-slot write, read-back verified).
- End-to-end: stock 2.0.28 → initramfs in RAM (`rootfs_type: tmpfs`) → `sysupgrade -n` of the
  release `squashfs-sysupgrade.bin`, sha256-verified on the device before flashing.
- The exploit half (`connect8`/`connect9`) roots stock 2.0.28 with no credentials.
