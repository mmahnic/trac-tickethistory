from workdays import *
from datetime import datetime, timedelta
from time import strptime
import math
import traceback

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

def _parse_date( datestr ):
    return datetime(*strptime(datestr, "%Y-%m-%d")[0:5]).date()

def _parse_datetime( datestr ):
    return datetime(*strptime(datestr, "%Y-%m-%d %H:%M")[0:5])

def _is_same_dt( d1, d2, numParts=5 ):
    return d1.timetuple()[:numParts] == d2.timetuple()[:numParts]

@test
def shouldEstimateEnd():
    def test( d1, d2, total, remaining, dexp ):
        d1 = _parse_datetime(d1)
        d2 = _parse_datetime(d2)
        dexp = _parse_date(dexp)
        dres = estimate_end( d1, d2, total, remaining )
        print "expected: %s, actual %s, %s" % (dexp, dres, _is_same_dt( dres, dexp, 3 ) )

    # Monday 2017-03-06
    test( "2017-03-06 00:00", "2017-03-07 00:00", 2, 1, "2017-03-08" )
    test( "2017-03-06 00:00", "2017-03-08 00:00", 2, 1, "2017-03-10" )
    test( "2017-03-06 00:00", "2017-03-09 00:00", 2, 1, "2017-03-12" )
    test( "2017-03-06 00:00", "2017-03-10 00:00", 2, 1, "2017-03-14" )
    test( "2017-03-06 00:00", "2017-03-13 00:00", 2, 1, "2017-03-20" )

@test
def shouldAdjustStart():
    def test( d1, dexp ):
        dexp = _parse_datetime(dexp)
        dres = adjusted_start( _parse_datetime( d1 ) )
        print "expected: %s, actual %s, %s" % (dexp, dres, _is_same_dt( dres, dexp, 5 ) )

    # Monday 2017-03-06
    test( "2017-03-06 08:00", "2017-03-06 08:00" )
    test( "2017-03-07 08:00", "2017-03-07 08:00" )
    test( "2017-03-08 08:00", "2017-03-08 08:00" )
    test( "2017-03-09 08:00", "2017-03-09 08:00" )
    test( "2017-03-10 08:00", "2017-03-10 08:00" )
    test( "2017-03-11 08:00", "2017-03-13 00:00" )
    test( "2017-03-12 08:00", "2017-03-13 00:00" )

@test
def shouldAdjustEnd():
    def test( d1, dexp ):
        dexp = _parse_datetime(dexp)
        dres = adjusted_end( _parse_datetime( d1 ) )
        print "expected: %s, actual %s, %s" % (dexp, dres, _is_same_dt( dres, dexp, 5 ) )

    # Monday 2017-03-06
    test( "2017-03-06 08:00", "2017-03-06 08:00" )
    test( "2017-03-07 08:00", "2017-03-07 08:00" )
    test( "2017-03-08 08:00", "2017-03-08 08:00" )
    test( "2017-03-09 08:00", "2017-03-09 08:00" )
    test( "2017-03-10 08:00", "2017-03-10 08:00" )
    test( "2017-03-11 08:00", "2017-03-10 23:59" )
    test( "2017-03-12 08:00", "2017-03-10 23:59" )

@test
def shouldEstimateEndWorkdays():
    def test( d1, d2, total, remaining, dexp ):
        d1 = _parse_datetime(d1)
        d2 = _parse_datetime(d2)
        dexp = _parse_datetime(dexp)
        dres = estimate_end_workdays( d1, d2, total, remaining )
        print "expected: %s, actual %s, %s" % (dexp, dres, _is_same_dt( dres, dexp, 3 ) )

    # Monday 2017-03-06
    # same week
    test( "2017-03-06 08:00", "2017-03-07 08:00", 2, 1, "2017-03-08 08:00" )
    test( "2017-03-06 08:00", "2017-03-08 08:00", 2, 1, "2017-03-10 08:00" )
    # projection spans weekends
    test( "2017-03-06 08:00", "2017-03-09 08:00", 2, 1, "2017-03-14 08:00" )
    test( "2017-03-06 08:00", "2017-03-10 08:00", 2, 1, "2017-03-16 08:00" )
    # a weekend is in the completed time, estimate falls on weekend
    # 06 07 08 09 10 w11 w12 13 14 15 16 17 w18 w19 20
    test( "2017-03-06 08:00", "2017-03-13 08:00", 2, 1, "2017-03-20 08:00" )
    # Start on weekend
    test( "2017-03-05 08:00", "2017-03-10 08:00", 2, 1, "2017-03-16 08:00" )
    test( "2017-03-04 08:00", "2017-03-10 08:00", 2, 1, "2017-03-16 08:00" )
    # Start and now on weekend
    test( "2017-03-05 08:00", "2017-03-11 08:00", 2, 1, "2017-03-17 23:59" )
    test( "2017-03-04 08:00", "2017-03-12 08:00", 2, 1, "2017-03-17 23:59" )


runTests()
