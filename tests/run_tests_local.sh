#!/bin/sh
if [ -z "$PYTHON_EXE" ]; then
    PYTHON_EXE="/usr/bin/python"
fi

if [ ! -f ../tests/server.crt ] || [ ! -f ../tests/server.csr ] || [ ! -f ../tests/server.key ] || [ ! -f ../tests/other.crt ] || [ ! -f ../tests/other.csr ] || [ ! -f ../tests/other.key ]; then
    ../tests/makecert.sh
fi

PYTHONDONTWRITEBYTECODE=1 LC_ALL=C PYTHONPATH="../lib:../vdsm:../client:../vdsm_api:$PYTHONPATH" "$PYTHON_EXE" ../tests/testrunner.py --local-modules $@
