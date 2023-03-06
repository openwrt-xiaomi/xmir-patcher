#!/usr/bin/env bash

set -e

python3 -m venv venv

source ./venv/bin/activate

python3 -m pip install -r requirements.txt

python3 menu.py "$1"

exit 0