#!/bin/sh
if [ -z "$PYTHON_EXE" ]; then
    PYTHON_EXE="/usr/bin/python"
fi

prefix="/usr"
LC_ALL=C PYTHONPATH="${prefix}/share/vdsm" "$PYTHON_EXE" ../tests/testrunner.py $@
