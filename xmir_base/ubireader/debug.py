#!/usr/bin/env python
#############################################################
# ubi_reader/ubifs
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

import sys
import traceback
from ubireader import settings

def log(obj, message):
    if settings.logging_on or settings.logging_on_verbose:
        print('{} {}'.format(obj.__name__, message))

def verbose_log(obj, message):
    if settings.logging_on_verbose:
        log(obj, message)

def verbose_display(displayable_obj):
    if settings.logging_on_verbose:
        print(displayable_obj.display('\t'))

def error(obj, level, message):
    if settings.error_action == 'exit':
        print('{} {}: {}'.format(obj.__name__, level, message))
        if settings.fatal_traceback:
            traceback.print_exc()
        sys.exit(1)

    else:
        if level.lower() == 'warn':
            print('{} {}: {}'.format(obj.__name__, level, message))
        elif level.lower() == 'fatal':
            print('{} {}: {}'.format(obj.__name__, level, message))
            if settings.fatal_traceback:
                traceback.print_exc()
            sys.exit(1)
        else:
            print('{} {}: {}'.format(obj.__name__, level, message))

