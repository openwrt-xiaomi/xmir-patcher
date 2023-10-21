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

import os

from .header import Header, DTB_BEGIN_NODE, DTB_END_NODE, DTB_PROP, DTB_END, DTB_NOP
from .items import new_property, Property, PropBytes, PropWords, PropStrings, PropIncBin, Node
from .misc import strip_comments, split_to_lines, get_version_info, extract_string

__author__  = "Martin Olejar"
__contact__ = "martin.olejar@gmail.com"
__version__ = "0.3.3"
__license__ = "Apache 2.0"
__status__  = "Development"
__all__     = [
    # FDT Classes
    'FDT',
    'Node',
    'Header',
    # properties
    'Property',
    'PropBytes',
    'PropWords',
    'PropStrings',
    'PropIncBin',
    # core methods
    'parse_dts',
    'parse_dtb',
    'diff'
]


class ItemType:
    NODE = 0
    PROP = 1
    # Specific property type
    PROP_BASE = 5
    PROP_WORDS = 6
    PROP_BYTES = 7
    PROP_STRINGS = 8
    # All types
    ALL = 100


class FDT:
    """ Flattened Device Tree Class """

    @property
    def empty(self):
        return self.root.empty

    def __init__(self, header=None, entries=[]):
        """
        FDT class constructor

        :param header:
        """
        self.entries = entries
        self.header = Header() if header is None else header
        self.root = Node('/')
        self.last_handle = 0
        self.label_to_handle = {}
        self.handle_to_label = {}


    def __str__(self):
        """ String representation """
        return self.info()

    def info(self, props = False):
        """ Return object info in human readable format """
        msg = "FDT Content:\n"
        for path, nodes, props in self.walk():
            txt = "{} ({},{})".format(path, len(nodes), len(props))
            if props:
                txt += ' : ' + ", ".join(x.name for x in props)
            msg += txt + "\n"
        return msg

    def get_node(self, path: str, create: bool = False) -> Node:
        """ 
        Get node object from specified path
        
        :param path: Path as string
        :param create: If True, not existing nodes will be created
        """
        assert isinstance(path, str), "Node path must be a string type !"

        node = self.root
        path = path.lstrip('/')
        if path:
            names = path.split('/')
            for name in names:
                item = node.get_subnode(name)
                if item is None:
                    if create:
                        item = Node(name)
                        node.append(item)
                    else:
                        raise ValueError("Path \"{}\" doesn't exists".format(path))
                node = item

        return node

    def get_property(self, name: str, path: str = '') -> Property:
        """ 
        Get property object by name from specified path
        
        :param name: Property name
        :param path: Path to sub-node
        """
        return self.get_node(path).get_property(name)

    def set_property(self, name: str, value, path: str = '', create: bool = True):
        """
        Set property object by name
        
        :param name: Property name
        :param value: Property value
        :param path: Path to subnode
        :param create: If True, not existing nodes will be created
        """
        self.get_node(path, create).set_property(name, value)

    def exist_node(self, path: str) -> bool:
        """ 
        Check if <path>/node exist and return True
        
        :param path: path/node name
        :return True if <path>/node exist else False
        """
        try:
            self.get_node(path)
        except ValueError:
            return False
        else:
            return True

    def exist_property(self, name: str, path: str = '') -> bool:
        """ 
        Check if property exist
        
        :param name: Property name
        :param path: The path
        """
        return self.get_node(path).exist_property(name) if self.exist_node(path) else False

    def remove_node(self, name: str, path: str = ''):
        """ 
        Remove node obj by path/name. Raises ValueError if path/name doesn't exist
        
        :param name: Node name
        :param path: Path to sub-node
        """
        self.get_node(path).remove_subnode(name)

    def remove_property(self, name: str, path: str = ''):
        """ 
        Remove property obj by name. Raises ValueError if path/name doesn't exist
        
        :param name: Property name
        :param path: Path to subnode
        """
        self.get_node(path).remove_property(name)

    def add_item(self, obj, path: str = '', create: bool = True):
        """ 
        Add sub-node or property at specified path. Raises ValueError if path doesn't exist
        
        :param obj: The node or property object
        :param path: The path to subnode
        :param create: If True, not existing nodes will be created
        """
        self.get_node(path, create).append(obj)

    def add_label(self, label):
        ''' track labels/references to convert to phandles
            adds label with incrmenting handle to dictionary if not alread present
            returns handle for which can be used to replace the reference'''
        if label in self.label_to_handle:
            return self.label_to_handle[label]
        self.last_handle += 1
        self.label_to_handle[label] = self.last_handle
        self.handle_to_label[self.last_handle] = label
        return self.last_handle

    def search(self, name: str, itype: int = ItemType.ALL, path: str = '', recursive: bool = True) -> list:
        """ 
        Search properties and/or nodes with specified name. Return list of founded items
        
        :param name: The Property or Node name. If empty "", all nodes or properties will selected
        :param itype: Item type - NODE, PROP, PROP_BASE, PROP_WORDS, PROP_BYTES, PROP_STRINGS or ALL
        :param path: Path to root node
        :param recursive: Search in all sub-nodes (default: True)
        """
        assert isinstance(name, str), "Property name must be a string type !"

        node = self.get_node(path)
        nodes = []
        items = []
        pclss = {
            ItemType.PROP_BASE: Property,
            ItemType.PROP_BYTES: PropBytes,
            ItemType.PROP_WORDS: PropWords,
            ItemType.PROP_STRINGS: PropStrings
        }
        while True:
            nodes += node.nodes
            if itype == ItemType.NODE or itype == ItemType.ALL:
                if not name or node.name == name:
                    items.append(node)
            if itype != ItemType.NODE or itype == ItemType.ALL:
                for p in node.props:
                    if name and p.name != name:
                        continue
                    if itype in pclss and type(p) is not pclss[itype]:
                        continue
                    items.append(p)
            if not recursive or not nodes:
                break
            node = nodes.pop()

        return items

    def walk(self, path: str = '', relative: bool = False) -> list:
        """ 
        Walk trough nodes and return relative/absolute path with list of sub-nodes and properties
        
        :param path: The path to root node
        :param relative: True for relative or False for absolute return path
        """
        all_nodes = []

        node = self.get_node(path)
        while True:
            all_nodes += node.nodes
            current_path = node.path
            current_path = current_path.replace('///', '/')
            current_path = current_path.replace('//', '/')
            if path and relative:
                current_path = current_path.replace(path, '').lstrip('/')
            yield current_path, node.nodes, node.props
            if not all_nodes:
                break
            node = all_nodes.pop()

    def merge(self, fdt_obj, replace: bool = True):
        """
        Merge external FDT object into this object.
        
        :param fdt_obj: The FDT object which will be merged into this
        :param replace: True for replace existing items or False for keep old items
        """
        assert isinstance(fdt_obj, FDT)
        if self.header.version is None:
            self.header = fdt_obj.header
        else:
            if fdt_obj.header.version is not None and \
               fdt_obj.header.version > self.header.version:
                self.header.version = fdt_obj.header.version
        if fdt_obj.entries:
            for in_entry in fdt_obj.entries:
                exist = False
                for index in range(len(self.entries)):
                    if self.entries[index]['address'] == in_entry['address']:
                        self.entries[index]['size'] = in_entry['size']
                        exist = True
                        break
                if not exist:
                    self.entries.append(in_entry)

        self.root.merge(fdt_obj.get_node('/'), replace)

    def update_phandles(self):
        all_nodes = []
        no_phandle_nodes = []

        node = self.root
        all_nodes += self.root.nodes
        while all_nodes:
            props = (node.get_property('phandle'), node.get_property('linux,phandle'))
            value = None
            for i, p in enumerate(props):
                if isinstance(p, PropWords) and isinstance(p.value, int):
                    value = None if i == 1 and p.value != value else p.value
            if value is None:
                no_phandle_nodes.append(node)
            # ...
            node = all_nodes.pop()
            all_nodes += node.nodes

        for node in no_phandle_nodes:
            if node.name != '/':
                if node.path == '/':   
                    phandle_value = self.add_label(node.name)
                else:
                    phandle_value = self.add_label(node.path)
                node.set_property('linux,phandle', phandle_value)
                node.set_property('phandle', phandle_value)


    def to_dts(self, tabsize: int = 4) -> str:
        """
        Store FDT Object into string format (DTS)

        :param tabsize:
        """
        result = "/dts-v1/;\n"
        if self.header.version is not None:
            result += "// version: {}\n".format(self.header.version)
            result += "// last_comp_version: {}\n".format(self.header.last_comp_version)
            if self.header.version >= 2:
                result += "// boot_cpuid_phys: 0x{:X}\n".format(self.header.boot_cpuid_phys)
        result += '\n'
        if self.entries:
            for entry in self.entries:
                result += "/memreserve/ "
                result += "{:#x} ".format(entry['address']) if entry['address'] else "0 "
                result += "{:#x}".format(entry['size']) if entry['size'] else "0"
                result += ";\n"
        if self.root is not None:
            result += self.root.to_dts(tabsize)
        return result

    def to_dtb(self, version: int = None, last_comp_version: int = None, boot_cpuid_phys: int = None, strings: str = None) -> bytes:
        """
        Export FDT Object into Binary Blob format (DTB)

        :param version:
        :param last_comp_version:
        :param boot_cpuid_phys:
        :param strings:

        The strings param is useful (only) when manipulating a signed itb or dtb.  The signature includes
        the strings buffer in the dtb _in order_.  C executables write the strings out in a surprising order.
        The argument is used as an initial version of the strings buffer, so that all strings in the input
        file are included (and in the same order) in the output file.  Usage:

            # Read and parse dtb
            with open(input, 'rb') as file:
                data = file.read()
            dtree = fdt.parse_dtb(data)

            # Read strings buffer (Assumes version >= 3)
            strings_start = dtree.header.off_dt_strings
            strings_end = strings_start + dtree.header.size_dt_strings
            strings = data[strings_start:strings_end].decode("ascii")

            # Serialize dtb and write to output
            data = dtree.to_dtb(strings=strings)
            with open(output, 'wb') as file:
                file.write(data)

        """
        if self.root is None:
            return b''

        from struct import pack

        if version is not None:
            self.header.version = version
        if last_comp_version is not None:
            self.header.last_comp_version = last_comp_version
        if boot_cpuid_phys is not None:
            self.header.boot_cpuid_phys = boot_cpuid_phys
        if self.header.version is None:
            raise Exception("DTB Version must be specified !")
        if strings is None:
            strings = ''

        blob_entries = bytes()
        if self.entries:
            for entry in self.entries:
                blob_entries += pack('>QQ', entry['address'], entry['size'])
        blob_entries += pack('>QQ', 0, 0)
        blob_data_start = self.header.size + len(blob_entries)
        (blob_data, blob_strings, data_pos) = self.root.to_dtb(strings, blob_data_start, self.header.version)
        blob_data += pack('>I', DTB_END)
        self.header.size_dt_strings = len(blob_strings)
        self.header.size_dt_struct = len(blob_data)
        self.header.off_mem_rsvmap = self.header.size
        self.header.off_dt_struct = blob_data_start
        self.header.off_dt_strings = blob_data_start + len(blob_data)
        self.header.total_size = blob_data_start + len(blob_data) + len(blob_strings)
        blob_header = self.header.export()
        return blob_header + blob_entries + blob_data + blob_strings.encode('ascii')


def parse_dts(text: str, root_dir: str = '') -> FDT:
    """
    Parse DTS text file and create FDT Object

    :param text:
    :param root_dir: 
    """
    ver = get_version_info(text)
    text = strip_comments(text)
    dts_lines = split_to_lines(text)
    fdt_obj = FDT()
    if 'version' in ver:
        fdt_obj.header.version = ver['version']
    if 'last_comp_version' in ver:
        fdt_obj.header.last_comp_version = ver['last_comp_version']
    if 'boot_cpuid_phys' in ver:
        fdt_obj.header.boot_cpuid_phys = ver['boot_cpuid_phys']
    # parse entries
    fdt_obj.entries = []
    for line in dts_lines:
        if line.endswith('{'):
            break
        if line.startswith('/memreserve/'):
            line = line.strip(';')
            line = line.split()
            if len(line) != 3 :
                raise Exception()
            fdt_obj.entries.append({'address': int(line[1], 0), 'size': int(line[2], 0)})
    # parse nodes
    curnode = None
    fdt_obj.root = None
    for line in dts_lines:
        if line.endswith('{'):
            # start node
            if ':' in line:  #indicates the present of a label
                label, rest = line.split(':')
                node_name = rest.split()[0]
                new_node = Node(node_name)
                new_node.set_label(label)

                
            else:
                node_name = line.split()[0]
                new_node = Node(node_name)
            if fdt_obj.root is None:
                fdt_obj.root = new_node
            if curnode is not None:
                curnode.append(new_node)
            curnode = new_node
        elif line.endswith('}'):
            # end node
            if curnode is not None:
                if curnode.get_property('phandle') is None:
                    if curnode.label is not None:
                        handle = fdt_obj.add_label(curnode.label)
                        curnode.set_property('phandle', handle)
                curnode = curnode.parent
        else:
            # properties
            if line.find('=') == -1:
                prop_name = line
                prop_obj = Property(prop_name)
            else:
                line = line.split('=', maxsplit=1)
                prop_name = line[0].rstrip(' ')
                prop_value = line[1].lstrip(' ')
                if prop_value.startswith('<'):
                    prop_obj = PropWords(prop_name)
                    prop_value = prop_value.replace('<', '').replace('>', '')
                    # ['interrupts ' = ' <0 5 4>, <0 6 4>']
                    # just change ',' to ' ' -- to concatenate the values into single array
                    if ',' in prop_value:
                        prop_value = prop_value.replace(',', ' ')
                    
                    # keep the orginal references for phandles as a phantom
                    # property
                    if "&" in prop_value:
                        phantom_obj = PropStrings(prop_name+'_with_references')
                        phantom_obj.append(line[1].lstrip(' '))
                        if curnode is not None:
                            curnode.append(phantom_obj)
                    for prop in prop_value.split():
                        if prop.startswith('0x'):
                            prop_obj.append(int(prop, 16))
                        elif prop.startswith('0b'):
                            prop_obj.append(int(prop, 2))
                        elif prop.startswith('0'):
                            prop_obj.append(int(prop, 8))
                        elif prop.startswith('&'):
                            prop_obj.append(fdt_obj.add_label(prop[1:]))
                        else:
                            prop_obj.append(int(prop))
                elif prop_value.startswith('['):
                    prop_obj = PropBytes(prop_name)
                    prop_value = prop_value.replace('[', '').replace(']', '')
                    for prop in prop_value.split():
                        prop_obj.append(int(prop, 16))
                elif prop_value.startswith('/incbin/'):
                    prop_value = prop_value.replace('/incbin/("', '').replace('")', '')
                    prop_value = prop_value.split(',')
                    file_path  = os.path.join(root_dir, prop_value[0].strip())
                    file_offset = int(prop_value.strip(), 0) if len(prop_value) > 1 else 0
                    file_size = int(prop_value.strip(), 0) if len(prop_value) > 2 else 0
                    if file_path is None or not os.path.exists(file_path):
                        raise Exception("File path doesn't exist: {}".format(file_path))
                    with open(file_path, "rb") as f:
                        f.seek(file_offset)
                        prop_data = f.read(file_size) if file_size > 0 else f.read()
                    prop_obj = PropIncBin(prop_name, prop_data, os.path.split(file_path)[1])
                elif prop_value.startswith('/plugin/'):
                    raise NotImplementedError("Not implemented property value: /plugin/")
                elif prop_value.startswith('/bits/'):
                    raise NotImplementedError("Not implemented property value: /bits/")
                else:
                    prop_obj = PropStrings(prop_name)
                    expect_open = True
                    in_prop = False
                    prop = ''
                    for c in prop_value:
                        if c == '"' and not in_prop and expect_open:
                            prop = ''
                            in_prop = True
                        elif c == '"' and in_prop:
                            if not len(prop) > 0:
                                raise ValueError('Empty string')
                            prop_obj.append(prop)
                            in_prop = False
                            expect_open = False
                        elif in_prop:
                            prop += c
                        elif c == ',' and not expect_open:
                            expect_open = True
                        elif c == ' ':
                            continue
                        else:
                            raise ValueError(f'Invalid char: {c}')

                    if expect_open:
                        raise ValueError('Expected string after ,')
            if curnode is not None:
                curnode.append(prop_obj)

    return fdt_obj


def parse_dtb(data: bytes, offset: int = 0) -> FDT:
    """
    Parse FDT Binary Blob and create FDT Object
    
    :param data: FDT Binary Blob in bytes
    :param offset: The offset of input data
    """
    assert isinstance(data, (bytes, bytearray)), "Invalid argument type"

    from struct import unpack_from

    fdt_obj = FDT()
    # parse header
    fdt_obj.header = Header.parse(data)
    # parse entries
    index = fdt_obj.header.off_mem_rsvmap
    while True:
        entrie = dict(zip(('address', 'size'), unpack_from(">QQ", data, offset + index)))
        index += 16
        if entrie['address'] == 0 and entrie['size'] == 0:
            break
        fdt_obj.entries.append(entrie)
    # parse nodes
    current_node = None
    fdt_obj.root = None
    index = fdt_obj.header.off_dt_struct
    while True:
        if len(data) < (offset + index + 4):
            raise Exception("Index out of range !")
        tag = unpack_from(">I", data, offset + index)[0]
        index += 4
        if tag == DTB_BEGIN_NODE:
            node_name = extract_string(data, offset + index)
            index = ((index + len(node_name) + 4) & ~3)
            if not node_name: node_name = '/'
            new_node = Node(node_name)
            if fdt_obj.root is None:
                fdt_obj.root = new_node
            if current_node is not None:
                current_node.append(new_node)
            current_node = new_node
        elif tag == DTB_END_NODE:
            if current_node is not None:
                current_node = current_node.parent
        elif tag == DTB_PROP:
            prop_size, prop_string_pos, = unpack_from(">II", data, offset + index)
            prop_start = index + 8
            if fdt_obj.header.version < 16 and prop_size >= 8:
                prop_start = ((prop_start + 7) & ~0x7)
            prop_name = extract_string(data, fdt_obj.header.off_dt_strings + prop_string_pos)
            prop_raw_value = data[offset + prop_start : offset + prop_start + prop_size]
            index = prop_start + prop_size
            index = ((index + 3) & ~0x3)
            if current_node is not None:
                current_node.append(new_property(prop_name, prop_raw_value))
        elif tag == DTB_END:
            break
        else:
            raise Exception("Unknown Tag: {}".format(tag))

    return fdt_obj


def diff(fdt1: FDT, fdt2: FDT) -> tuple:
    """ 
    Compare two flattened device tree objects and return list of 3 objects (same in 1 and 2, specific for 1, specific for 2)
    
    :param fdt1: The object 1 of FDT
    :param fdt2: The object 2 of FDT
    """
    assert isinstance(fdt1, FDT), "Invalid argument type"
    assert isinstance(fdt2, FDT), "Invalid argument type"

    fdt_a = FDT(fdt1.header)
    fdt_b = FDT(fdt2.header)

    if fdt1.header.version is not None and fdt2.header.version is not None:
        fdt_same = FDT(fdt1.header if fdt1.header.version > fdt2.header.version else fdt2.header)
    else:
        fdt_same = FDT(fdt1.header)

    if fdt1.entries and fdt2.entries:
        for entry_a in fdt1.entries:
            for entry_b in fdt2.entries:
                if entry_a['address'] == entry_b['address'] and entry_a['size'] == entry_b['size']:
                    fdt_same.entries.append(entry_a)
                    break

    for entry_a in fdt1.entries:
        found = False
        for entry_s in fdt_same.entries:
            if entry_a['address'] == entry_s['address'] and entry_a['size'] == entry_s['size']:
                found = True
                break
        if not found:
            fdt_a.entries.append(entry_a)

    for entry_b in fdt2.entries:
        found = False
        for entry_s in fdt_same.entries:
            if entry_b['address'] == entry_s['address'] and entry_b['size'] == entry_s['size']:
                found = True
                break
        if not found:
            fdt_b.entries.append(entry_b)

    for path, nodes, props in fdt1.walk():
        try:
            rnode = fdt2.get_node(path)
        except:
            rnode = None

        for node_b in nodes:
            if rnode is None or rnode.get_subnode(node_b.name) is None:
                fdt_a.add_item(Node(node_b.name), path)
            else:
                fdt_same.add_item(Node(node_b.name), path)

        for prop_a in props:
            if rnode is not None and prop_a == rnode.get_property(prop_a.name):
                fdt_same.add_item(prop_a.copy(), path)
            else:
                fdt_a.add_item(prop_a.copy(), path)

    for path, nodes, props in fdt2.walk():
        try:
            rnode = fdt_same.get_node(path)
        except:
            rnode = None

        for node_b in nodes:
            if rnode is None or rnode.get_subnode(node_b.name) is None:
                fdt_b.add_item(Node(node_b.name), path)

        for prop_b in props:
            if rnode is None or prop_b != rnode.get_property(prop_b.name):
                fdt_b.add_item(prop_b.copy(), path)

    return fdt_same, fdt_a, fdt_b
