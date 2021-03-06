#!/Library/Frameworks/Python.framework/Versions/3.5/bin/python3
# -*- coding: utf-8 -*-

# The MIT License (MIT)
#
# Copyright (c) 2015 Jakub Uhlík
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import sys
import traceback
import argparse
import textwrap
import os


def log(msg, indent=0):
    m = "{0}> {1}".format("    " * indent, msg)
    print(m)


def main(args):
    p = args.mxm_path
    s = Cmaxwell(mwcallback)
    m = s.readMaterial(p)
    for i in range(m.getNumLayers()[0]):
        l = m.getLayer(i)
        e = l.getEmitter()
        if(e.isNull()):
            # no emitter layer
            return False
        if(not e.getState()[0]):
            # there is, but is disabled
            return False
        # is emitter
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=textwrap.dedent('''Read MXM file and check is there is an emitter layer'''), epilog='',
                                     formatter_class=argparse.RawDescriptionHelpFormatter, add_help=True, )
    parser.add_argument('pymaxwell_path', type=str, help='path to directory containing pymaxwell')
    parser.add_argument('mxm_path', type=str, help='path to .mxm')
    args = parser.parse_args()
    
    PYMAXWELL_PATH = args.pymaxwell_path
    
    try:
        from pymaxwell import *
    except ImportError:
        if(not os.path.exists(PYMAXWELL_PATH)):
            raise OSError("pymaxwell for python 3.5 does not exist ({})".format(PYMAXWELL_PATH))
        sys.path.insert(0, PYMAXWELL_PATH)
        from pymaxwell import *
    
    found = False
    try:
        found = main(args)
    except Exception as e:
        m = traceback.format_exc()
        log(m)
        sys.exit(1)
    if(found):
        # lets communicate with exit code
        sys.exit(100)
    sys.exit(0)
