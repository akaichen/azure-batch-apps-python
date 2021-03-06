#-------------------------------------------------------------------------
# The Azure Batch Apps Python Client
#
# Copyright (c) Microsoft Corporation. All rights reserved. 
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#--------------------------------------------------------------------------
"""
Batch Apps Python Client Unit Test Suite
"""

import sys
import os

if sys.version_info[:2] < (2, 7, ):
    try:
        import unittest2
        from unittest2 import TestLoader, TextTestRunner

    except ImportError:
        raise ImportError("The BatchApps Python Client test suite requires "
                          "the unittest2 package to run on Python 2.6 and "
                          "below.\nPlease install this package to continue.")
else:
    import unittest
    from unittest import TestLoader, TextTestRunner

if sys.version_info[:2] >= (3, 3, ):
    from unittest import mock
else:
    try:
        import mock

    except ImportError:
        raise ImportError("The BatchApps Python Client test suite requires "
                          "the mock package to run on Python 3.2 and below.\n"
                          "Please install this package to continue.")

try:
    from teamcity import is_running_under_teamcity
    from teamcity.unittestpy import TeamcityTestRunner
    TC_BUILD = is_running_under_teamcity()

except ImportError:
    TC_BUILD = False

if __name__ == '__main__':

    if TC_BUILD:
        runner = TeamcityTestRunner()
    else:
        runner = TextTestRunner(verbosity=2)

    test_dir = os.path.dirname(__file__)
    top_dir = os.path.dirname(os.path.dirname(test_dir))
    test_loader = TestLoader()
    suite = test_loader.discover(test_dir,
                                 pattern="unittest_*.py",
                                 top_level_dir=top_dir)
    runner.run(suite)
