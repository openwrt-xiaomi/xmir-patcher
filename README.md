[![Download latest](https://img.shields.io/badge/⏬-Download_latest-green)](https://github.com/openwrt-xiaomi/xmir-patcher/archive/refs/heads/main.zip)
[![dowloads](https://raw.githubusercontent.com/openwrt-xiaomi/xmir-patcher/gh-pages/traffic/clones.svg)](https://github.com/openwrt-xiaomi/xmir-patcher/archive/refs/heads/main.zip)
[![GitHub Stars](https://img.shields.io/github/stars/openwrt-xiaomi/xmir-patcher?style=flat)](https://github.com/openwrt-xiaomi/xmir-patcher/stargazers)
[![ViewCount](https://views.whatilearened.today/views/github/openwrt-xiaomi/xmir-patcher.svg)](https://github.com/openwrt-xiaomi/xmir-patcher)
[![Donations Page](https://github.com/andry81-cache/gh-content-static-cache/raw/master/common/badges/donate/donate.svg)](https://github.com/remittor/donate)

# XMiR-Patcher
Firmware patcher for Xiaomi routers


## Usage

### Windows

* Run `run.bat`

### Linux / Mac OS

* Install python 3.8+ and openssl
* Run `run.sh`

## Language install

Menu item "Install EN/RU languages" installs the translation catalogue only.
Strings hardcoded in the web templates (menus, home page, Wi-Fi and WAN
settings) are not covered by it and stay Chinese. To patch those as well, run:

```
python install_lang.py full
```

Uninstall with `python install_lang.py uninstall`. The template patch is
re-applied on every boot, because the templates live in a tmpfs mirror that is
rebuilt from the read-only squashfs each time.

## Donations

[![Donations Page](https://github.com/andry81-cache/gh-content-static-cache/raw/master/common/badges/donate/donate.svg)](https://github.com/remittor/donate)
