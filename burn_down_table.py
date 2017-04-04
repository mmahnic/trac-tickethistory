from genshi.core import Markup
from trac.wiki.macros import WikiMacroBase
from trac.wiki import Formatter
from trac.wiki.api import parse_args
from trac.util.datefmt import from_utimestamp as from_timestamp, to_datetime, to_utimestamp as to_timestamp
from trac.core import TracError

import datetime as dt
import time

import StringIO
import math
import traceback

class BurnDownTableMacro(WikiMacroBase):
    revision = "$Rev$"
    url = "$URL$"

    def _parse_options( self, content ):
        options = {}
        _, parsed_options = parse_args(content, strict=False)
        options.update(parsed_options)

        def parse_date( datestr ):
            return dt.datetime(*time.strptime(datestr, "%Y-%m-%d")[0:5]).date()

        for name in [ "startdate", "enddate", "today" ]:
            if name in options:
                options[name] = parse_date( options.get(name) )

        today = dt.datetime.now().date()
        options['enddate'] = options.get('enddate') or today
        options['today'] = options.get('today') or today

        return options


    def _verify_options( self, options ):
        if not options.get('startdate'):
            raise TracError("No start date specified!")

        if (options['startdate'] >= options['enddate']):
            options['enddate'] = options['startdate'] + dt.timedelta(days=1)

        return options


    def _extract_query_args( self, options ):
        AVAILABLE_OPTIONS = [ "starttdate", "enddate", "today" ]
        query_args = {}
        for key in options.keys():
            if not key in AVAILABLE_OPTIONS:
                query_args[key] = options[key]
        return query_args


    def expand_macro(self, formatter, name, text, args):
        self.estimation_field = "tm_estimate"
        self.closed_states = [ "closed" ]
        self.new_states = [ "new" ]
        req = formatter.req

        import ticket_timetable as listers
        import dbutils

        options = self._verify_options( self._parse_options( text ) )
        query_args = self._extract_query_args( options )
        milestone = query_args['milestone']
        dbutils.require_ticket_fields( query_args, [self.estimation_field] )

        lister = listers.CTicketListLoader( self.env.get_db_cnx() )
        lister.exec_ticket_query = lambda x, args: dbutils.get_viewable_tickets( self.env, req, args )
        lister.timestamp_to_datetime = lambda ts: from_timestamp( ts )
        tickets = lister.queryTicketsInMilestone( milestone, query_args )

        starttime = to_datetime(dt.datetime.combine(options['startdate'], dt.time.min))
        time_first = to_datetime(dt.datetime.combine(options['startdate'], dt.time.max))
        time_end = to_datetime(dt.datetime.combine(options['enddate'], dt.time.max))
        delta = dt.timedelta(days=1)

        timetable = listers.Timetable( starttime )
        timetable.entries = [ listers.TimetableEntry( time_first ) ]
        time_next = time_first + delta
        while time_next <= time_end:
            timetable.entries += [ listers.TimetableEntry( time_next ) ]
            time_next += delta

        lister.fillTicketTimetable(tickets, timetable, [self.estimation_field] )

        fmt_todaycell = "**%s**"
        fmt_dayoffcell = "[[span(style=color: #c0c0c0, %s)]]"
        def cellcontent( c, wrapformat ):
            align_start = " " if c[0] == " " else ""
            align_end = " " if c[-1] == " " else ""
            return align_start + (wrapformat % c.strip()) + align_end
        def wikirow( cells ):
            return "||" + ( "||".join( cells ) ) + "||"
        cells = [ " %s ", " %.1f", " %.1f", " %.1f", " %.1f", " %.1f", " %s", " %s" ]
        fmtnormal  = wikirow( cells )
        fmttoday   = wikirow( cellcontent(c, fmt_todaycell) for c in cells )
        fmtweekend = wikirow( cellcontent(c, fmt_dayoffcell) for c in cells )

        result = []
        result.append( "||= Date =||= Total =||= Remain =||= New =||= WiP =||= Done =||= End =||= End* =||" )

        today = options['today']
        for entry in timetable.entries:
            date = entry.endtime.date()
            pnew = sum( 1 for t in entry.tickets if t.status in self.new_states )
            pdone = sum( 1 for t in entry.tickets if t.status in self.closed_states )
            ptotal = sum( 1 for t in entry.tickets )
            pwip = ptotal - pnew - pdone
            premaining = ptotal - pdone

            enddate = dbutils.estimate_end( starttime, entry.endtime, ptotal, premaining )
            enddate = "" if enddate is None else enddate
            enddate_wd = dbutils.estimate_end_workdays( starttime, entry.endtime, ptotal, premaining )
            enddate_wd = "" if enddate_wd is None else enddate_wd

            if date == today: fmt = fmttoday
            elif date.weekday() > 4: fmt = fmtweekend
            else: fmt = fmtnormal

            result.append( fmt % (date, ptotal, premaining, pnew, pwip, pdone, enddate, enddate_wd ) )
        result.append( "" )

        newtext = "\n".join( result )
        out = StringIO.StringIO()
        Formatter(self.env, formatter.context).format(newtext, out)
        return Markup(out.getvalue())
