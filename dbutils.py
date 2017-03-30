from trac.util.text import unicode_urlencode
from trac.ticket.query import Query
import copy


def _encode_trac_query( query_args ):
    return unicode_urlencode(query_args) \
	.replace('%21=', '!=') \
        .replace('%21%7E=', '!~=') \
        .replace('%7E=', '~=') \
        .replace('%5E=', '^=') \
        .replace('%24=', '$=') \
        .replace('%21%5E=', '!^=') \
        .replace('%21%24=', '!$=') \
        .replace('%7C', '|') \
        .replace('+', ' ') \
        .replace('%23', '#') \
        .replace('%28', '(') \
        .replace('%29', ')')


def get_viewable_tickets(env, req, query_args):
    # set maximum number of returned tickets to 0 to get all tickets at once
    query_args = copy.copy( query_args )
    query_args['max'] = 0
    query_string = _encode_trac_query( query_args )
    env.log.debug("query_string: %s", query_string)
    query = Query.from_string(env, query_string)

    tickets = query.execute(req)

    tickets = [t for t in tickets
               if ('TICKET_VIEW' or 'TICKET_VIEW_CC')
               in req.perm('ticket', t['id'])]

    return tickets


def require_ticket_fields( query_args, fieldnames ):
    for f in fieldnames:
        if not f in query_args:
            query_args[ f + "!" ] = "###"


from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

    return (now + dt.timedelta( hours = morehours )).date()


def _workday_diff( start, end ):
    if (end-start).days < 1:
        return 0
    daydiff = end.weekday() - start.weekday()
    days = ((end-start).days - daydiff) / 7 * 5 + min(daydiff,5) - (max(end.weekday() - 4, 0) % 5)
    return days


def estimate_end_workdays( start, now, total, remaining ):
    done = total - remaining
    if done <= 0:
        return None
    # days = (now - start).days
    days = _workday_diff(start, now)
    if days < 1:
        return None
    perday = float(done) / days
    moredays = int(math.ceil(remaining / perday))
    enddate = now + dt.timedelta( days = moredays )
    offdays = moredays - _workday_diff(now, enddate)

    # raise Exception( "days %d, perday %f, moredays %f, enddate %s, offdays %d" % ( days, perday, moredays, enddate, offdays ) )
    return (enddate + dt.timedelta( days = offdays )).date()

