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

import re
from string import printable


def is_string(data):
    """ Check property string validity """
    if not len(data):
        return None
    if data[-1] != 0:
        return None
    pos = 0
    while pos < len(data):
        posi = pos
        while pos < len(data) and \
              data[pos] != 0 and \
              data[pos] in printable.encode() and \
              data[pos] not in (ord('\r'), ord('\n')):
            pos += 1
        if data[pos] != 0 or pos == posi:
            return None
        pos += 1
    return True


def extract_string(data, offset=0):
    """ Extract string """
    str_end = offset
    while data[str_end] != 0:
        str_end += 1
    return data[offset:str_end].decode("ascii")


def line_offset(tabsize, offset, string):
    offset = " " * (tabsize * offset)
    return offset + string


def get_version_info(text):
    ret = dict()
    for line in text.split('\n'):
        line = line.rstrip('\0')
        if line and line.startswith('/ {'):
            break
        if line and line.startswith('//'):
            line = line.replace('//', '').replace(':', '')
            line = line.split()
            if line[0] in ('version', 'last_comp_version', 'boot_cpuid_phys'):
                ret[line[0]] = int(line[1], 0)
    return ret


def strip_comments(text):
    text = re.sub(r'//.?(\r\n?|\n)|/*.?*/', '\n', text, flags=re.S)
    return text


def split_to_lines(text):
    lines = []
    mline = str()
    for line in text.split('\n'):
        line = line.replace('\t', ' ')
        line = line.rstrip('\0')
        line = line.rstrip(' ')
        line = line.lstrip(' ')
        if not line or line.startswith('/dts-'):
            continue
        if line.endswith('{') or line.endswith(';'):
            line = line.replace(';', '')
            lines.append(mline + line)
            mline = str()
        else:
            mline += line + ' '

    return lines

