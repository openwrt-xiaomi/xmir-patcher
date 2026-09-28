# Installing OpenWrt on the Xiaomi AX3000T **RD03v2** (IPQ5018)

> **Read this before following any AX3000T tutorial.** The RD03v2 is a *different machine*
> from the RD03/RD23. Those are MediaTek Filogic 820; this one is Qualcomm IPQ5018.
> Stock RD03v2 has `rootfs`/`rootfs_1` slots, while installed OpenWrt uses
> `ubi_kernel`/`rootfs`. Both stock variants may use `flag_boot_rootfs`, but their
> partition addresses differ. **The `mtd8`/`mtd9` commands in RD03 guides will
> not work here and can brick the unit.**

Identify the unit before you start: RD03v2 packaging has a barcode ending `706330`, SKU
`DVB4510CN`, and `init_info` reports `"hardware":"RD03v2"` / `"model":"xiaomi.router.rd03v2"`.

---

## Why the install is two steps

On this board, `sysupgrade` must run from a RAM initramfs so it can reformat
both UBI partitions for the locked stock bootloader. The installed NAND system
refuses an in-place `sysupgrade`. The install is therefore:

1. **Boot an initramfs in RAM** — a throwaway system that lives entirely in memory.
2. **`sysupgrade` the squashfs image** from that RAM system — *this* is the persistent install.

XMiR-Patcher's `connect.py` roots initialized stock, and `install_fw.py` boots
the RAM image. Step 2 writes the permanent image from RAM.

---

## Step 1 — root stock and boot the initramfs

This procedure was tested on an RD03v2 running MiWiFi/XiaoQiang 2.0.28.

If stock is at its first-run setup wizard (`init_info` reports `inited=0`),
initialize and reboot it **before** running XMiR-Patcher. Otherwise
`connect.py` stops with *"You need to make the initial configuration"* and
`cab_meshd` is not listening. For this installation method, use the
[RD03v2 `init_router.py` helper](https://github.com/ADCDS/xiaomi-ax3000t-cabmeshd-disclosure/blob/master/poc/init_router.py)
instead of completing the normal stock web wizard:

```sh
# from a clone of xiaomi-ax3000t-cabmeshd-disclosure
python3 poc/init_router.py --host 192.168.31.1 --reboot
```

That helper marks stock as initialized without changing its Wi-Fi password,
admin password, or WAN settings, then waits for the mesh service to start.
The normal web wizard calls `mesh_connect.sh init_cap 2`, which sets
`NETMODE=whc_cap` (`4`) on stock 2.0.28 and closes the `cap_init` path used by
`connect9`. A factory reset followed by the same wizard closes it again.
On an already configured router, skip the helper and check the result of
`connect.py`; see the `NETMODE=4` note below.

### 1a. Put exactly one image in `firmware/`

Download the RAM image, its paired permanent image, and `sha256sums.txt` from
the [same release](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/releases/tag/v1.11).
The table lists the v1.11 filenames; do not mix releases or the plain and NSS
flavors. In the download directory, run
`sha256sum -c sha256sums.txt --ignore-missing` before copying the chosen image
into `firmware/`; its checksum must say `OK`.

Choose an **initramfs** image. XMiR-Patcher accepts only initramfs OpenWrt images here
(`OpenWRT: Supported only InitRamFS images`). All filenames in this table start with
`openwrt-qualcommax-ipq50xx-xiaomi_mi-router-ax3000t-v2-`:

| RAM image in `firmware/` | Permanent image for Step 2 |
|---|---|
| `initramfs-factory.ubi` | `squashfs-sysupgrade.bin` |
| `initramfs-factory-wifi.ubi` | `squashfs-sysupgrade.bin` |
| `initramfs-factory-nss.ubi` | `squashfs-sysupgrade-nss.bin` |
| `initramfs-factory-nss-wifi.ubi` | `squashfs-sysupgrade-nss.bin` |

Use a `-wifi` initramfs if you need wireless access **while running from RAM**. It
beacons `OpenWrt-RD03v2-Installer` (WPA2, key `rd03v2install`) on both radios.
The non-`-wifi` initramfs leaves both radios disabled. The `-nss` images include
experimental NSS offload; use the matching `-nss` sysupgrade image in Step 2.

> **Keep only one image file in `firmware/`.** `install_fw.py` aborts with
> *"Too many different files in directory"* when more than one UBI image is
> present. Keep the Step 2 sysupgrade image outside that directory.

### 1b. Root stock, verify SSH, and boot the initramfs

Run these commands in order from the XMiR-Patcher directory:

```sh
./run.sh connect.py
./run.sh read_info.py
./run.sh install_fw.py
```

`connect.py` runs the stock rooting flow and enables SSH. `read_info.py` must
connect and identify the RD03v2 over SSH before you run `install_fw.py`: the
installer requires working SSH at startup and cannot root stock itself. Stop
if either command fails.

Stock normally uses `192.168.31.1`. If yours has another address, pass it to
`connect.py` (for example, `./run.sh connect.py 192.168.31.2`); XMiR-Patcher
saves that address for the following commands. If rooting over Wi-Fi, expect
the stock radios to bounce during `connect9` and follow its reconnect instructions.

If `connect.py` reports `NETMODE=4` (`whc_cap`), `connect9` will not fire its
`cap_init` payload in that state. Normal stock web setup, mesh commissioning,
and a previous completed `cap_init` can all set this mode, so the value does
not identify which event happened. Stock's full reset path erases the config
containing this mode, but repeating the normal web wizard writes it again.
If you reset the router for this method, use the minimal `init_router.py`
setup above. Do not proceed to `install_fw.py` until SSH works.

`install_fw.py` then:

- checks that the initramfs is a supported image for this device,
- writes it to stock's **inactive** A/B slot (for example, `rootfs_1` at `0x02880000`),
- reads the write back, selects that slot with the stock boot flags, and reboots.

The stock slot currently in use is left intact at this stage.

### 1c. Confirm you are in RAM

The RAM system uses `192.168.1.1`. If you used a `-wifi` initramfs, rejoin
`OpenWrt-RD03v2-Installer` and obtain a new address before connecting over SSH.

```sh
ssh root@192.168.1.1
. /lib/upgrade/common.sh; rootfs_type       # must print: tmpfs
```

If it prints `squashfs` or `overlay`, the RAM boot did not succeed. Stop before
running `sysupgrade`.

## Step 2 — the permanent install

Use the sysupgrade image paired with your Step 1 initramfs in the table above.
This example shows the plain image; use `openwrt-qualcommax-ipq50xx-xiaomi_mi-router-ax3000t-v2-squashfs-sysupgrade-nss.bin`
if you used either `-nss` initramfs:

The NSS initramfs can be short on free memory. Before uploading the image,
check `grep MemAvailable /proc/meminfo` on the RAM router. If it is below
30 MB, free memory for the transfer:

```sh
ssh root@192.168.1.1 'for s in rd03v2-watchdog odhcpd sysntpd uhttpd; do /etc/init.d/$s stop; done; sync; echo 3 > /proc/sys/vm/drop_caches; echo 4096 > /proc/sys/vm/min_free_kbytes; grep MemAvailable /proc/meminfo'
```

The changed memory setting lasts only until the next reboot. Check
`MemAvailable` again and **do not upload if it is still below 30 MB**.

```sh
# From your computer, in the directory with the selected image and sha256sums.txt.
# For an NSS initramfs, use the matching ...-squashfs-sysupgrade-nss.bin here.
(
set -e
IMAGE=openwrt-qualcommax-ipq50xx-xiaomi_mi-router-ax3000t-v2-squashfs-sysupgrade.bin
sha256sum -c sha256sums.txt --ignore-missing  # selected image must say OK
cat "$IMAGE" | ssh root@192.168.1.1 'cat > /tmp/fw.bin'
IMAGE_SHA256=$(sha256sum "$IMAGE" | cut -d ' ' -f 1)
printf '%s  /tmp/fw.bin\n' "$IMAGE_SHA256" | ssh root@192.168.1.1 'sha256sum -c -'
ssh root@192.168.1.1 'sysupgrade -T /tmp/fw.bin'
ssh root@192.168.1.1 'setsid sh -c "sysupgrade -n /tmp/fw.bin > /tmp/sysupgrade.log 2>&1" </dev/null >/dev/null 2>&1 &'
)
```

Use the pipe above rather than modern `scp`: the RAM image has no
`sftp-server`, so the default SFTP transfer fails.

Run the final line **only after** the release checksum, upload checksum, and
`sysupgrade -T` all succeed. `setsid` lets the NAND write continue if the SSH
link drops during reboot; do not run the write under `timeout` or interrupt
power. Wait for the router to reboot, then run
`ssh root@192.168.1.1 '. /lib/upgrade/common.sh; rootfs_type'` and confirm it
reports `overlay`. If it never goes offline, inspect `/tmp/sysupgrade.log` on
the RAM system.

`-n` discards configuration, which is appropriate for a first install. Run
`sysupgrade` only after Step 1c reports `tmpfs`; the RAM system prepares both
OpenWrt UBI partitions before writing the permanent image.

The router reboots into OpenWrt on NAND when the write finishes.

Later updates also require a matching initramfs boot and `sysupgrade` from
RAM. See [reflashing without UART](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/blob/main/docs/no-uart-reflash.md).

## After the install — use Ethernet to configure Wi-Fi

The `-wifi` initramfs provides a temporary network only while the router runs
from RAM. After `sysupgrade -n`, the installer SSID disappears and the
permanent OpenWrt system starts with both radios disabled. Arrange wired LAN
access before Step 2 if you need to configure the installed system.

Connect a cable to a LAN port and browse to `http://192.168.1.1`, or use
`ssh root@192.168.1.1` (no password until you set one). Then enable the radios,
set the country code, and configure your own Wi-Fi credentials.

---

## Partition layout (why the slot matters)

| Partition | Start | Size | Purpose |
|---|---|---|---|
| stock `rootfs` (slot 0) | `0x0a80000` | 30M | stock kernel + `ubi_rootfs` |
| stock `rootfs_1` (slot 1) | `0x2880000` | 30M | second stock boot slot |
| stock `overlay` | `0x4680000` | 57M | config / data |
| OpenWrt `ubi_kernel` | `0x0a80000` | 36M | |
| OpenWrt `rootfs` | `0x2e80000` | 81M | |

Stock keeps a real A/B pair with exactly one slot attached at runtime. Writing the initramfs to
the slot you are *not* booted from is what makes this reversible: if the new slot fails to boot,
stock is still there.

Stock's A/B layout applies to the Step 1 write only. The Step 2 `sysupgrade`
from RAM formats the OpenWrt `ubi_kernel` and `rootfs` partitions and replaces
the stock slot contents. After the permanent install, do not expect an intact
stock slot or use stock's `rootfs_1` write recipe against OpenWrt. Returning
to stock requires the full stock recovery or restore procedure.

## Recovery

- **The initramfs fails before Step 2** — the previously active stock slot is
  still intact. Use U-Boot TFTP recovery if it does not boot automatically.
- **The permanent install fails, or you want stock again** — Step 2 replaced
  the stock slots. Restore a genuine RD03v2 stock image with the full TFTP
  recovery procedure.
  Stock recovery enforces Xiaomi's RSA signature and anti-rollback version rule.

See the [RD03v2 UART and recovery guide](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/blob/main/docs/installation-and-usage.md#uart-installation-guide)
for TFTP setup and signed stock image checksums.

## Verified

- XMiR-Patcher `install_fw.py` accepts the RD03v2 initramfs and produces a correct recipe
  (`install_method = 200`, inactive-slot write, read-back verified).
- End-to-end on an RD03v2 bench: stock 2.0.28 → `init_router.py --reboot` →
  `connect.py` → `read_info.py` → v1.11 NSS Wi-Fi initramfs in RAM
  (`rootfs_type: tmpfs`) → matching `squashfs-sysupgrade-nss.bin`, SHA-256
  verified and accepted by `sysupgrade -T` → OpenWrt on NAND
  (`rootfs_type: overlay`).
- The exploit half (`connect8`/`connect9`) roots stock 2.0.28 without requiring
  the user's admin password.
