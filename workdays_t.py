from datetime import datetime, timedelta
from time import strptime
import math

def _workday_diff( start, end ):
    if (end-start).days < 1:
        return 0
    daydiff = end.weekday() - start.weekday()
    days = ((end-start).days - daydiff) / 7 * 5 + min(daydiff,5) - (max(end.weekday() - 4, 0) % 5)
    return days

def _estimate_end_workdays( start, now, total, remaining ):
    done = total - remaining
    if done <= 0:
        return None
    # days = (now - start).days 
    days = _workday_diff(start, now)
    if days < 1:
        return None
    perday = float(done) / days
    print done, days, perday
    moredays = int(math.ceil(remaining / perday))
    enddate = now + timedelta( days = moredays )
    offdays = moredays - _workday_diff(now, enddate)

    # raise Exception( "days %d, perday %f, moredays %f, enddate %s, offdays %d" % ( days, perday, moredays, enddate, offdays ) )
    return enddate + timedelta( days = offdays )

def _parse_date( datestr ):
    return datetime(*strptime(datestr, "%Y-%m-%d")[0:5]).date()

def test( d1, d2, total, remaining, dexp ):
    d1 = _parse_date(d1)
    d2 = _parse_date(d2)
    dexp = _parse_date(dexp)
    dres = _estimate_end_workdays( d1, d2, total, remaining )
    print "expected: %s, actual %s, %s" % (dexp, dres, dres == dexp )

test( "2017-03-06", "2017-03-07", 2, 1, "2017-03-08" )
test( "2017-03-06", "2017-03-08", 2, 1, "2017-03-10" )
test( "2017-03-06", "2017-03-09", 2, 1, "2017-03-14" )
test( "2017-03-06", "2017-03-10", 2, 1, "2017-03-16" )
test( "2017-03-06", "2017-03-13", 2, 1, "2017-03-20" ) # FIXME: returns -19

startdate="2017-03-06"
enddate="2017-03-17"
import datetime as dt
import time
startdate = time.mktime(dt.datetime.combine(_parse_date(startdate), dt.time.min).timetuple())
enddate   = time.mktime(dt.datetime.combine(_parse_date(enddate), dt.time.max).timetuple())

print startdate, enddate
