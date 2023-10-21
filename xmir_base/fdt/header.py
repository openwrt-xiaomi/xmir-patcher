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

from struct import unpack_from, pack


########################################################################################################################
# Binary Blob Constants
########################################################################################################################

DTB_BEGIN_NODE = 0x1
DTB_END_NODE = 0x2
DTB_PROP = 0x3
DTB_NOP = 0x4
DTB_END = 0x9


########################################################################################################################
# Header Class
########################################################################################################################

class Header:

    MIN_SIZE = 4 * 7
    MAX_SIZE = 4 * 10

    MAX_VERSION = 17

    MAGIC_NUMBER = 0xD00DFEED

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        if value > self.MAX_VERSION:
            raise ValueError("Invalid Version {}, use: 0 - 17 !".format(value))
        # update size and padding
        self._size = self.MIN_SIZE
        if value >= 2:
            self._size += 4
        if value >= 3:
            self._size += 4
        if value >= 17:
            self._size += 4
        self._padding = 8 - (self._size % 8) if self._size % 8 != 0 else 0
        self._version = value
        self.last_comp_version = value - 1

    @property
    def size(self):
        return self._size + self._padding

    @property
    def padding(self):
        return self._padding

    def __init__(self):
        # private variables
        self._version = None
        self._size = 0
        self._padding = 0
        # public variables
        self.total_size = 0
        self.off_dt_struct = 0
        self.off_dt_strings = 0
        self.off_mem_rsvmap = 0
        self.last_comp_version = 0
        # version depend variables
        self.boot_cpuid_phys = 0
        self.size_dt_strings = None
        self.size_dt_struct = None

    def __str__(self):
        return '<FDT-v{}, size: {}>'.format(self.version, self.size)

    def info(self):
        nfo = 'FDT Header:'
        nfo += '- Version: {}'.format(self.version)
        nfo += '- Size:    {}'.format(self.size)
        return nfo

    def export(self) -> bytes:
        """

        :return:
        """
        if self.version is None:
            raise Exception("Header version must be specified !")

        blob = pack('>7I', self.MAGIC_NUMBER, self.total_size, self.off_dt_struct, self.off_dt_strings,
                    self.off_mem_rsvmap, self.version, self.last_comp_version)
        if self.version >= 2:
            blob += pack('>I', self.boot_cpuid_phys)
        if self.version >= 3:
            blob += pack('>I', self.size_dt_strings)
        if self.version >= 17:
            blob += pack('>I', self.size_dt_struct)
        if self.padding:
            blob += bytes([0] * self.padding)

        return blob

    @classmethod
    def parse(cls, data: bytes, offset: int = 0):
        """

        :param data:
        :param offset:
        """
        if len(data) < (offset + cls.MIN_SIZE):
            raise ValueError('Data size too small !')

        header = cls()
        (magic_number,
         header.total_size,
         header.off_dt_struct,
         header.off_dt_strings,
         header.off_mem_rsvmap,
         header.version,
         header.last_comp_version) = unpack_from('>7I', data, offset)
        offset += cls.MIN_SIZE

        if magic_number != cls.MAGIC_NUMBER:
            raise Exception('Invalid Magic Number')
        if header.last_comp_version > cls.MAX_VERSION - 1:
            raise Exception('Invalid last compatible Version {}'.format(header.last_comp_version))

        if header.version >= 2:
            header.boot_cpuid_phys = unpack_from('>I', data, offset)[0]
            offset += 4

        if header.version >= 3:
            header.size_dt_strings = unpack_from('>I', data, offset)[0]
            offset += 4

        if header.version >= 17:
            header.size_dt_struct = unpack_from('>I', data, offset)[0]
            offset += 4

        return header
