import os
import sys

#print("xmir_base (win)")

current_dir = os.path.dirname(os.path.abspath(__file__))
pyexe_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(pyexe_dir)

sys.path.append(root_dir + '/xmir_base')

import xmir_init

