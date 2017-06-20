import traceback
from ..distributor import *

tests=[]
def test( fn ):
    tests.append(fn)
    return fn

def runTests():
    for t in tests:
        print t
        try: t()
        except Exception as e:
            print e
            traceback.print_exc()
        print

@test
def shouldCaluculateColumnWidths():
    def test( sizes, exp_widths ):
        widths = distributeItems( sizes )
        if len(widths) != len(exp_widths):
            raise Exception( "Column counts do not match, %s, exp: %s" % (widths, exp_widths) )
        for ic in xrange(len(widths)):
            if widths[ic] != exp_widths[ic]:
                raise Exception( "Widths do not match, %s, exp: %s" % (widths, exp_widths) )
        print sizes, widths, "ok"

    # This behavior is not perfect but good enough.
    test( [0, 0, 0], [4, 4, 4] )
    test( [2, 1, 1], [6, 3, 3] )
    test( [4, 1, 1], [8, 2, 2] )
    test( [40, 10, 30], [6, 2, 4] )
    test( [40, 30, 20], [6, 4, 2] )
    # test( [10, 30, 40], [2, 4, 6] )
    test( [13, 1, 3], [8, 2, 2] )
    test( [3, 1, 13], [2, 2, 8] )

runTests()
