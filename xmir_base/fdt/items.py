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

from struct import pack, Struct
from string import printable

from .header import Header, DTB_PROP, DTB_BEGIN_NODE, DTB_END_NODE
from .misc import is_string, line_offset

BIGENDIAN_WORD = Struct(">I")

########################################################################################################################
# Helper methods
########################################################################################################################

def new_property(name: str, raw_value: bytes) -> object:
    """
    Instantiate property with raw value type

    :param name: Property name
    :param raw_value: Property raw data
    """
    if is_string(raw_value):
        obj = PropStrings(name)
        # Extract strings from raw value
        for st in raw_value.decode('ascii').split('\0'):
            if st:
                obj.append(st)
        return obj

    elif len(raw_value) > 0 and len(raw_value) <= 256*1024 and len(raw_value) % 4 == 0:
        obj = PropWords(name)
        # Extract words from raw value
        obj.data = [BIGENDIAN_WORD.unpack(raw_value[i:i + 4])[0] for i in range(0, len(raw_value), 4)]
        obj.raw_value = raw_value
        return obj

    elif len(raw_value):
        return PropBytes(name, data=raw_value)

    return Property(name)


########################################################################################################################
# Base Class
########################################################################################################################

class BaseItem:

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def parent(self):
        return self._parent

    @property
    def path(self):
        node = self._parent
        path = ""
        while node:
            if node.name == '/': break
            path = '/' + node.name + path
            node = node.parent
        return path if path else '/'

    def __init__(self, name: str, label=None):
        """ 
        BaseItem constructor
        
        :param name: Item name
        """
        assert isinstance(name, str)
        assert all(c in printable for c in name), "The value must contain just printable chars !"
        self._name = name
        self._label = label
        self._parent = None

    def __str__(self):
        """ String representation """
        return "{}".format(self.name)

    def set_name(self, value: str):
        """ 
        Set item name
        
        :param value: The name in string format
        """
        assert isinstance(value, str)
        assert all(c in printable for c in value), "The value must contain just printable chars !"
        self._name = value

    def set_label(self, value: str):
        """ 
        Set item label
        
        :param value: The label in string format
        """
        assert isinstance(value, str)
        assert all(c in printable for c in value), "The value must contain just printable chars !"
        self._label = value


    def set_parent(self, value):
        """ 
        Set item parent

        :param value: The parent node 
        """
        assert isinstance(value, Node)
        self._parent = value

    def to_dts(self, tabsize: int = 4, depth: int = 0):
        raise NotImplementedError()

    def to_dtb(self, strings: str, pos: int = 0, version: int = Header.MAX_VERSION):
        raise NotImplementedError()


########################################################################################################################
# Property Classes
########################################################################################################################

class Property(BaseItem):

    def __getitem__(self, value):
        """ Returns No Items """
        return None

    def __eq__(self, obj):
        """ Check Property object equality """
        return isinstance(obj, Property) and self.name == obj.name

    def copy(self):
        """ Get object copy """
        return Property(self.name)

    def to_dts(self, tabsize: int = 4, depth: int = 0):
        """
        Get string representation

        :param tabsize: Tabulator size in count of spaces
        :param depth: Start depth for line
        """
        return line_offset(tabsize, depth, '{};\n'.format(self.name))

    def to_dtb(self, strings: str, pos: int = 0, version: int = Header.MAX_VERSION):
        """
        Get binary blob representation

        :param strings:
        :param pos:
        :param version:
        """
        strpos = strings.find(self.name + '\0')
        if strpos < 0:
            strpos = len(strings)
            strings += self.name + '\0'
        pos += 12
        return pack('>III', DTB_PROP, 0, strpos), strings, pos


class PropStrings(Property):
    """Property with strings as value"""

    @property
    def value(self):
        return self.data[0] if self.data else None

    def __init__(self, name: str, *args):
        """ 
        PropStrings constructor
        
        :param name: Property name
        :param args: str1, str2, ...
        """
        super().__init__(name)
        self.data = []
        for arg in args:
            self.append(arg)

    def __str__(self):
        """ String representation """
        return "{} = {}".format(self.name, self.data)

    def __len__(self):
        """ Get strings count """
        return len(self.data)

    def __getitem__(self, index):
        """ Get string by index """
        return self.data[index]

    def __eq__(self, obj):
        """ Check PropStrings object equality """
        if not isinstance(obj, PropStrings) or self.name != obj.name or len(self) != len(obj):
            return False
        for index in range(len(self)):
            if self.data[index] != obj[index]:
                return False
        return True

    def copy(self):
        """ Get object copy """
        return PropStrings(self.name, *self.data)

    def append(self, value: str):
        assert isinstance(value, str)
        assert len(value) > 0, "Invalid strings value"
        assert all(c in printable or c in ('\r', '\n') for c in value), "Invalid chars in strings value"
        self.data.append(value)

    def pop(self, index: int):
        assert 0 <= index < len(self.data), "Index out of range"
        return self.data.pop(index)

    def clear(self):
        self.data.clear()

    def to_dts(self, tabsize: int = 4, depth: int = 0):
        """
        Get string representation

        :param tabsize: Tabulator size in count of spaces
        :param depth: Start depth for line
        """
        result  = line_offset(tabsize, depth, self.name)
        result += ' = "'
        result += '", "'.join([item.replace('"', '\\"') for item in self.data])
        result += '";\n'
        return result

    def to_dtb(self, strings: str, pos: int = 0, version: int = Header.MAX_VERSION):
        """
        Get blob representation

        :param strings:
        :param pos:
        :param version:
        """
        blob = pack('')
        for chars in self.data:
            blob += chars.encode('ascii') + pack('b', 0)
        blob_len = len(blob)
        if version < 16 and (pos + 12) % 8 != 0:
            blob = pack('b', 0) * (8 - ((pos + 12) % 8)) + blob
        if blob_len % 4:
            blob += pack('b', 0) * (4 - (blob_len % 4))
        strpos = strings.find(self.name + '\0')
        if strpos < 0:
            strpos = len(strings)
            strings += self.name + '\0'
        blob = pack('>III', DTB_PROP, blob_len, strpos) + blob
        pos += len(blob)
        return blob, strings, pos


class PropWords(Property):
    """Property with words as value"""

    @property
    def value(self):
        return self.data[0] if self.data else None

    def __init__(self, name, *args):
        """
        PropWords constructor

        :param name: Property name
        :param args: word1, word2, ...
        """
        super().__init__(name)
        self.data = []
        self.word_size = 32
        for val in args:
            self.append(val)

    def __str__(self):
        """ String representation """
        return "{} = {}".format(self.name, self.data)

    def __getitem__(self, index):
        """ Get word by index """
        return self.data[index]

    def __len__(self):
        """ Get words count """
        return len(self.data)

    def __eq__(self, prop):
        """ Check PropWords object equality  """
        if not isinstance(prop, PropWords):
            return False
        if self.name != prop.name:
            return False
        if len(self) != len(prop):
            return False
        for index in range(len(self)):
            if self.data[index] != prop[index]:
                return False
        return True

    def copy(self):
        return PropWords(self.name, *self.data)

    def append(self, value):
        assert isinstance(value, int), "Invalid object type"
        assert 0 <= value < 2**self.word_size, "Invalid word value {}, use <0x0 - 0x{:X}>".format(
            value, 2**self.word_size - 1)
        self.data.append(value)

    def pop(self, index):
        assert 0 <= index < len(self.data), "Index out of range"
        return self.data.pop(index)

    def clear(self):
        self.data.clear()

    def to_dts(self, tabsize: int = 4, depth: int = 0):
        """
        Get string representation

        :param tabsize: Tabulator size in count of spaces
        :param depth: Start depth for line
        """
        result  = line_offset(tabsize, depth, self.name)
        result += ' = <'
        result += ' '.join(["0x{:X}".format(word) for word in self.data])
        result += ">;\n"
        return result

    def to_dtb(self, strings: str, pos: int = 0, version: int = Header.MAX_VERSION):
        """
        Get blob representation

        :param strings:
        :param pos:
        :param version:
        """
        strpos = strings.find(self.name + '\0')
        if strpos < 0:
            strpos = len(strings)
            strings += self.name + '\0'
        blob = pack('>III', DTB_PROP, len(self.data) * 4, strpos)
        blob += bytes().join([BIGENDIAN_WORD.pack(word) for word in self.data])
        pos += len(blob)
        return blob, strings, pos


class PropBytes(Property):
    """Property with bytes as value"""

    def __init__(self, name, *args, data=None):
        """ 
        PropBytes constructor
        
        :param name: Property name
        :param args: byte0, byte1, ...
        :param data: Data as list, bytes or bytearray
        """
        super().__init__(name)
        self.data = bytearray(args)
        if data:
            assert isinstance(data, (list, bytes, bytearray))
            self.data += bytearray(data)

    def __str__(self):
        """ String representation """
        return "{} = {}".format(self.name, self.data)

    def __getitem__(self, index):
        """Get byte by index """
        return self.data[index]

    def __len__(self):
        """ Get bytes count """
        return len(self.data)

    def __eq__(self, prop):
        """ Check PropBytes object equality  """
        if not isinstance(prop, PropBytes):
            return False
        if self.name != prop.name:
            return False
        if len(self) != len(prop):
            return False
        for index in range(len(self)):
            if self.data[index] != prop[index]:
                return False
        return True

    def copy(self):
        """ Create a copy of object """
        return PropBytes(self.name, data=self.data)

    def append(self, value):
        assert isinstance(value, int), "Invalid object type"
        assert 0 <= value <= 0xFF, "Invalid byte value {}, use <0 - 255>".format(value)
        self.data.append(value)

    def pop(self, index):
        assert 0 <= index < len(self.data), "Index out of range"
        return self.data.pop(index)

    def clear(self):
        self.data = bytearray()

    def to_dts(self, tabsize: int = 4, depth: int = 0):
        """
        Get string representation

        :param tabsize: Tabulator size in count of spaces
        :param depth: Start depth for line
        """
        result  = line_offset(tabsize, depth, self.name)
        result += ' = ['
        result += ' '.join(["{:02X}".format(byte) for byte in self.data])
        result += '];\n'
        return result

    def to_dtb(self, strings: str, pos: int = 0, version: int = Header.MAX_VERSION):
        """
        Get blob representation

        :param strings:
        :param pos:
        :param version:
        """
        strpos = strings.find(self.name + '\0')
        if strpos < 0:
            strpos = len(strings)
            strings += self.name + '\0'
        blob  = pack('>III', DTB_PROP, len(self.data), strpos)
        blob += bytes(self.data)
        if len(blob) % 4:
            blob += bytes([0] * (4 - (len(blob) % 4)))
        pos += len(blob)
        return blob, strings, pos


class PropIncBin(PropBytes):
    """Property with bytes as value"""

    def __init__(self, name, data=None, file_name=None, rpath=None):
        """
        PropIncBin constructor

        :param name: Property name
        :param data: Data as list, bytes or bytearray
        :param file_name: File name
        :param rpath: Relative path
        """
        super().__init__(name, data)
        self.file_name = file_name
        self.relative_path = rpath

    def __eq__(self, prop):
        """ Check PropIncBin object equality  """
        if not isinstance(prop, PropIncBin):
            return False
        if self.name != prop.name:
            return False
        if self.file_name != prop.file_name:
            return False
        if self.relative_path != prop.relative_path:
            return False
        if self.data != prop.data:
            return False
        return True

    def copy(self):
        """ Create a copy of object """
        return PropIncBin(self.name, self.data, self.file_name, self.relative_path)

    def to_dts(self, tabsize: int = 4, depth: int = 0):
        """
        Get string representation

        :param tabsize: Tabulator size in count of spaces
        :param depth: Start depth for line
        """
        file_path = self.file_name
        if self.relative_path is not None:
            file_path = "{}/{}".format(self.relative_path, self.file_name)
        result  = line_offset(tabsize, depth, self.name)
        result += " = /incbin/(\"{}\");\n".format(file_path)
        return result


########################################################################################################################
# Node Class
########################################################################################################################

class Node(BaseItem):
    """Node representation"""

    @property
    def path(self):
        return super().path + '/' + self.name

    @property
    def props(self):
        return self._props

    @property
    def nodes(self):
        return self._nodes

    @property
    def empty(self):
        return False if self.nodes or self.props else True

    def __init__(self, name, *args, label=None):
        """ 
        Node constructor
        
        :param name: Node name
        :param args: List of properties and subnodes
        """
        super().__init__(name, label=label)
        self._props = []
        self._nodes = []
        for item in args:
            self.append(item)

    def __str__(self):
        """ String representation """
        return "< {}: {} props, {} nodes >".format(self.name, len(self.props), len(self.nodes))

    def __eq__(self, node):
        """ Check node equality """
        if not isinstance(node, Node):
            return False
        if self.name != node.name or \
           len(self.props) != len(node.props) or \
           len(self.nodes) != len(node.nodes):
            return False
        for p in self.props:
            if p not in node.props:
                return False
        for n in self.nodes:
            if n not in node.nodes:
                return False
        return True

    def copy(self):
        """ Create a copy of Node object """
        node = Node(self.name, label=self.label)
        for p in self.props:
            node.append(p.copy())
        for n in self.nodes:
            node.append(n.copy())
        return node

    def get_property(self, name):
        """ 
        Get property object by its name
        
        :param name: Property name
        """
        for p in self.props:
            if p.name == name:
                return p
        return None

    def set_property(self, name, value):
        """
        Set property

        :param name: Property name
        :param value: Property value
        """
        if value is None:
            new_prop = Property(name)
        elif isinstance(value, int):
            new_prop = PropWords(name, value)
        elif isinstance(value, str):
            new_prop = PropStrings(name, value)
        elif isinstance(value, list) and isinstance(value[0], int):
            new_prop = PropWords(name, *value)
        elif isinstance(value, list) and isinstance(value[0], str):
            new_prop = PropStrings(name, *value)
        elif isinstance(value, (bytes, bytearray)):
            new_prop = PropBytes(name, data=value)
        else:
            raise TypeError('Value type not supported')
        new_prop.set_parent(self)
        old_prop = self.get_property(name)
        if old_prop is None:
            self.props.append(new_prop)
        else:
            index = self.props.index(old_prop)
            self.props[index] = new_prop

    def get_subnode(self, name: str):
        """ 
        Get subnode object by name

        :param name: Subnode name
        """
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    def exist_property(self, name: str) -> bool:
        """ 
        Check if property exist and return True if exist else False
        
        :param name: Property name
        """
        return False if self.get_property(name) is None else True

    def exist_subnode(self, name: str) -> bool:
        """ 
        Check if subnode exist and return True if exist else False
        
        :param name: Subnode name
        """
        return False if self.get_subnode(name) is None else True

    def remove_property(self, name: str):
        """ 
        Remove property object by its name.
        
        :param name: Property name
        """
        item = self.get_property(name)
        if item is not None:
            self.props.remove(item)

    def remove_subnode(self, name: str):
        """ 
        Remove subnode object by its name.
        
        :param name: Subnode name
        """
        item = self.get_subnode(name)
        if item is not None:
            self.nodes.remove(item)

    def append(self, item):
        """ 
        Append node or property
        
        :param item: The node or property object
        """
        assert isinstance(item, (Node, Property)), "Invalid object type, use \"Node\" or \"Property\""

        if isinstance(item, Property):
            if self.get_property(item.name) is not None:
                raise Exception("{}: \"{}\" property already exists".format(self, item.name))
            item.set_parent(self)
            self.props.append(item)

        else:
            if self.get_subnode(item.name) is not None:
                raise Exception("{}: \"{}\" node already exists".format(self, item.name))
            if item is self:
                raise Exception("{}: append the same node {}".format(self, item.name))
            item.set_parent(self)
            self.nodes.append(item)

    def merge(self, node_obj, replace: bool = True):
        """ 
        Merge two nodes
        
        :param node_obj: Node object
        :param replace: If True, replace current properties with the given properties
        """
        assert isinstance(node_obj, Node), "Invalid object type"

        def get_property_index(name):
            for i, p in enumerate(self.props):
                if p.name == name:
                    return i
            return None

        def get_subnode_index(name):
            for i, n in enumerate(self.nodes):
                if n.name == name:
                    return i
            return None

        for prop in node_obj.props:
            index = get_property_index(prop.name)
            if index is None:
                self.append(prop.copy())
            elif prop in self._props:
                continue
            elif replace:
                new_prop = prop.copy()
                new_prop.set_parent(self)
                self._props[index] = new_prop
            else:
                pass

        for sub_node in node_obj.nodes:
            index = get_subnode_index(sub_node.name)
            if index is None:
                self.append(sub_node.copy())
            elif sub_node in self._nodes:
                continue
            else:
                self._nodes[index].merge(sub_node, replace)

    def to_dts(self, tabsize: int = 4, depth: int = 0) -> str:
        """ 
        Get string representation of NODE object
        
        :param tabsize: Tabulator size in count of spaces
        :param depth: Start depth for line
        """
        if self._label is not None:
            dts  = line_offset(tabsize, depth, self._label + ': ' + self.name + ' {\n')
        else:
            dts  = line_offset(tabsize, depth, self.name + ' {\n')
        # phantom properties which maintain reference state info
        # have names ending with _with_references
        # don't write those out to dts file
        dts += ''.join(
            prop.to_dts(tabsize, depth + 1) 
            for prop in self._props if prop.name.endswith('_with_references') is False)
        dts += ''.join(node.to_dts(tabsize, depth + 1) for node in self._nodes)
        dts += line_offset(tabsize, depth, "};\n")
        return dts

    def to_dtb(self, strings: str, pos: int = 0, version: int = Header.MAX_VERSION) -> tuple:
        """ 
        Get NODE in binary blob representation
        
        :param strings: 
        :param pos:
        :param version:
        """
        if self.name == '/':
            blob = pack('>II', DTB_BEGIN_NODE, 0)
        else:
            blob = pack('>I', DTB_BEGIN_NODE)
            blob += self.name.encode('ascii') + b'\0'
        if len(blob) % 4:
            blob += pack('b', 0) * (4 - (len(blob) % 4))
        pos += len(blob)
        for prop in self._props:
            # phantom property too maintain reference state should
            # not write out to dtb file
            if prop.name.endswith('_with_references') is False:
                (data, strings, pos) = prop.to_dtb(strings, pos, version)
                blob += data
        for node in self._nodes:
            (data, strings, pos) = node.to_dtb(strings, pos, version)
            blob += data
        pos += 4
        blob += pack('>I', DTB_END_NODE)
        return blob, strings, pos
