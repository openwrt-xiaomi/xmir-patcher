import os
import sys

#print("xmir_base")

xmir_base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(xmir_base_dir)

root_dir = os.path.dirname(xmir_base_dir)
sys.path.append(root_dir)

import xmir_init
