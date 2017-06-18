import math
import datetime as dt

def estimate_end( start, now, total, remaining ):
    done = total - remaining
    if done <= 0:
        return None
    hours = (now - start).total_seconds() / 3600
    if hours < 1:
        return None
    perhour = float(done) / hours
    morehours = int(math.ceil(remaining / perhour))

    return now + dt.timedelta( hours = morehours )


def _workday_diff( start, end ):
    if start > end:
        return 0
    diff = end-start
    if diff.days < 1:
        return diff.seconds / 86400.0

    daydiff = end.weekday() - start.weekday()
    days = (diff.days - daydiff) / 7 * 5 + min(daydiff,5) - (max(end.weekday() - 4, 0) % 5)
    return days + diff.seconds / 86400.0


def skip_weekend( when ):
    if when.weekday() <= 4:
        return when
    when += dt.timedelta( days = 2 - when.weekday() % 5 )
    return when.replace( hour=0, minute=0, second=0, microsecond=0 )


def adjusted_start( when ):
    return skip_weekend( when )


def adjusted_end( when ):
    if when.weekday() <= 4:
        return when
    when -= dt.timedelta( days = when.weekday() % 4 )
    return when.replace( hour=23, minute=59, second=59, microsecond=0 )


def estimate_end_workdays( start, now, total, remaining ):
    done = total - remaining
    if done <= 0:
        return None
    days = _workday_diff(adjusted_start(start), adjusted_end(now))
    if days <= 0:
        return None

    perday = float(done) / days
    moredays = remaining / perday

    # skip weekends
    # Note: days may be 1 off because of rounding, but we are ok with that
    ( weeks, days ) = divmod(int(moredays), 5 )
    moredays += weeks * 2
    nowStart = adjusted_start( now )
    if nowStart.weekday() + days > 4:
        moredays += 2

    (seconds, moredays) = math.modf( moredays )
    seconds *= 86400.0
    enddate = nowStart + dt.timedelta( days = moredays, seconds = seconds )
    return enddate

