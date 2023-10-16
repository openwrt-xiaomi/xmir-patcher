#!/usr/bin/env python
#############################################################
# ubi_reader
# (c) 2013 Jason Pruitt (jrspruitt@gmail.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#############################################################

output_dir = 'ubifs-root'

error_action = True                     # if 'exit' on any error exit program.
fatal_traceback = False                 # Print traceback on fatal errors.

ignore_block_header_errors = False      # Ignore block errors.
warn_only_block_read_errors = False     # Warning instead of Fatal error.

logging_on = False                      # Print debug info on.
logging_on_verbose = False              # Print verbose debug info on.

use_dummy_socket_file = False           # Create regular file place holder for sockets.
use_dummy_devices = False               # Create regular file place holder for devices.

uboot_fix = False                       # Older u-boot sets image_seq to 0 on blocks it's written to.
