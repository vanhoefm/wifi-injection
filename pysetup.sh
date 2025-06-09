#!/bin/bash
# Copyright (c) 2022, Mathy Vanhoef <mathy.vanhoef@kuleuven.be>
#
# This code may be distributed under the terms of the BSD license.
# See README for more details.

# Start from a clean environment
rm -rf venv/

# Basic python3 virtual environment
python3 -m venv venv
source venv/bin/activate
pip install wheel

# In case the user forgot to recursively clone
git submodule init
git submodule update

# Install requirements of libwifi
pip install -r libwifi/requirements.txt

