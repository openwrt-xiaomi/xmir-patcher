#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import gateway
from gateway import die


gw = gateway.Gateway()

print("Send command...")
gw.run_cmd("reboot")

print("Reboot activated!")
