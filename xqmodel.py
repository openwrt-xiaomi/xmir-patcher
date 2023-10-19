#!/usr/bin/env python3
# -*- coding: utf-8 -*-

mi = [ "" ] * 2000

mi[ 3] = "R1CM"
mi[ 4] = "R2D"
mi[ 5] = "R1CL"
mi[ 6] = "R2CM"
mi[ 7] = "R3"
mi[ 8] = "R3D"
mi[ 9] = "R3L"
mi[10] = "R3P"
mi[11] = "P01"
mi[12] = "R3A"
mi[13] = "R3G"
mi[14] = "R4"
mi[15] = "R4C"
mi[16] = "D01"
mi[17] = "R4A"
mi[18] = "R4CM"
mi[19] = "R4AC"
mi[20] = "R3GV2"
mi[21] = "R2600"

mi[22] = "R2100"
mi[23] = "RM2100"
mi[24] = "R3600"
mi[25] = "R1350"
mi[26] = "R2200"
mi[27] = "R2350"
mi[28] = "IR1200G"
mi[29] = "RM1800"
mi[30] = "R2100D"
mi[31] = "RA67"
mi[32] = "RA69"
mi[33] = "RA71"
mi[34] = "CR6006"
mi[35] = "CR6008"
mi[36] = "CR6009"
mi[37] = "RA70"           # AX9000
mi[38] = "RA75"
mi[39] = "RA72"           # Mi Router AX6000  Certification: 2021-05-20

mi[1005] = "RA50"         # Certification: 2022-13063
mi[1006] = "RB02"         # Xiaomi AC1200 (INT)
mi[1007] = "R4AV2"        # Xiaomi AC1200 (CN)

mi[43] = "RA80"           # AX3000 (CN)         Certification: 2022-2908
mi[44] = "RA81"           # Redmi AX3000
mi[45] = "RA82"           # AX3000 (INT)
mi[46] = "RA83"
mi[47] = "RA74"           # AX5400

mi[49] = "YY01"
mi[50] = "RB01"           # AX3200 (INT)
mi[51] = "RB03"           # AX6S    # CR8806 (ChinaMobile)
mi[52] = "CR8808"
mi[53] = "CR8809"
mi[54] = "RB04"           # Redmi AX5400
mi[55] = "CR5508"
mi[56] = "CR5506"
mi[57] = "CR5509"
mi[58] = "RB08"           # HomeWiFi

mi[1060] = "RB05"         # Certification: 2022-3478
mi[61] = "RB06"           # Redmi AX6000
mi[62] = "RB07"           # mediatek_mt7981

mi[64] = "CB04"
mi[65] = "CB0401"         # Xiaomi 5G CPE Pro, Magenta Internet 5G Box AX5400
mi[66] = "RC01"           # AX10000
mi[1067] = "RC04"         # RA75 analog
mi[68] = "CB0401V2"       # Xiaomi 5G CPE Pro

mi[70] = "RC06"           # Xiaomi Router 7000
mi[71] = "RD01"           # Xiaomi 全屋路由  # https://www.mi.com/xiaomi-routers/whole-room
mi[72] = "WR30"           # ???
mi[73] = "RD02"           # Xiaomi 全屋路由 子路由 (Whole house routing sub-routing) # ipq5018  # Certification: 2023-11107
mi[74] = "CR8818"
mi[75] = "RD03"           # Xiaomi AX3000T (CN)
mi[76] = "RD04"           # Certification: 2023-12227
mi[77] = "RD05"
mi[78] = "RD06"
mi[79] = "CR8816"
mi[80] = "CR8819"
mi[81] = "RD08"

# routers with unknown device number
mi[1901] = "WR30U"        # Xiaomi AX3000NE
mi[1902] = "WR30T"        # mediatek_mt7981   # Certification: 2022-3536
mi[1903] = "WR30M"        # Certification: 2022-3202   6.0.49
  

xqModelList = mi

def get_modelid_by_name(name, unk = False):
    for i, m in enumerate(xqModelList):
        if not unk and i >= 1000:
            break
        if m.lower() == name.lower():
            return i
    return -1

