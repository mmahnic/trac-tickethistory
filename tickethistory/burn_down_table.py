## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

import time
import StringIO
import math
import traceback
import datetime as dt

from genshi.core import Markup
from trac.wiki.macros import WikiMacroBase
from trac.wiki import Formatter
from trac.wiki.api import parse_args
from trac.util.datefmt import from_utimestamp as from_timestamp, to_datetime, to_utimestamp as to_timestamp
from trac.core import TracError
from tickethistory import options, dbutils, workdays, ticket_timetable as history

class BurnDownTableOptions(options.OptionRegistry):
    def __init__(self):
        super(BurnDownTableOptions, self).__init__(["startdate", "enddate", "today"])
        self._overrides = None


    def get_parameter_sets(self):
        return (self.iniParams, self.macroParams, self.urlParams, self._overrides)


    def apply_defaults(self):
        self._overrides = {}
        options = self.options()

        def parse_date( datestr ):
            return dt.datetime(*time.strptime(datestr, "%Y-%m-%d")[0:5]).date()

        for name in [ "startdate", "enddate", "today" ]:
            if name in options:
                self._overrides[name] = parse_date( options.get(name) )

        options = self.options()
        today = dt.datetime.now().date()
        self._overrides['enddate'] = options.get('enddate') or today
        self._overrides['today'] = options.get('today') or today


    def verify(self):
        options = self.options()
        if not options.get('startdate'):
            raise TracError("No start date specified!")

        if (options['startdate'] >= options['enddate']):
            options['enddate'] = options['startdate'] + dt.timedelta(days=1)


class BurnDownTableMacro(WikiMacroBase):
    def expand_macro(self, formatter, name, text, args):
        request = formatter.req

        self.tt_config = history.TimetableConfig()
        retriever = dbutils.MilestoneRetriever(self.env, request)

        optionReg = BurnDownTableOptions()
        optionReg.set_macro_params(text)
        optionReg.set_url_params(request.args)
        optionReg.apply_defaults()
        optionReg.verify()
        options = optionReg.options()
        query_args = optionReg.query_args()

        desired_fields = [self.tt_config.estimation_field]

        builder = history.HistoryBuilder( self.env.get_db_cnx() )
        builder.timestamp_to_datetime = lambda ts: from_timestamp( ts )
        tickets = retriever.retrieve( query_args, desired_fields )

        starttime = to_datetime(dt.datetime.combine(options['startdate'], dt.time.min))
        time_first = to_datetime(dt.datetime.combine(options['startdate'], dt.time.max))
        time_end = to_datetime(dt.datetime.combine(options['enddate'], dt.time.max))
        delta = dt.timedelta(days=1)

        timetable = history.Timetable( starttime )
        timetable.entries = [ history.TimetableEntry( time_first ) ]
        time_next = time_first + delta
        while time_next <= time_end:
            timetable.entries += [ history.TimetableEntry( time_next ) ]
            time_next += delta

        builder.fillTicketTimetable(tickets, timetable, [self.tt_config.estimation_field] )

        fmt_todaycell = "**%s**"
        fmt_dayoffcell = "[[span(style=color: #c0c0c0, %s)]]"
        def cellcontent( c, wrapformat ):
            align_start = " " if c[0] == " " else ""
            align_end = " " if c[-1] == " " else ""
            return align_start + (wrapformat % c.strip()) + align_end
        def wikirow( cells ):
            return "||" + ( "||".join( cells ) ) + "||" + "%s" + "||"
        cells = [ " %s ", " %.1f", " %.1f", " %.1f", " %.1f", " %.1f", " %s", " %s" ]
        fmtnormal  = wikirow( cells )
        fmttoday   = wikirow( cellcontent(c, fmt_todaycell) for c in cells )
        fmtweekend = wikirow( cellcontent(c, fmt_dayoffcell) for c in cells )

        result = []
        result.append( "||= Date =||= Total =||= Remain =||= New =||= WiP =||= Done =||= End =||= End* =||= =||" )

        def estimate(tinfo, default=1):
            v = tinfo.value_or( self.tt_config.estimation_field, default )
            try: return float(v) if v is not None else default
            except: return default

        dmin, dmax = self._getMinMaxEstimateDelta( timetable, starttime )

        today = options['today']
        for entry in timetable.entries:
            date = entry.endtime.date()
            pnew = sum( estimate(t) for t in entry.tickets if t.status in self.tt_config.new_states )
            pdone = sum( estimate(t) for t in entry.tickets if t.status in self.tt_config.closed_states )
            ptotal = sum( estimate(t) for t in entry.tickets )
            pwip = ptotal - pnew - pdone
            premaining = ptotal - pdone

            enddate = workdays.estimate_end( starttime, entry.endtime, ptotal, premaining )
            enddate = "" if enddate is None else enddate.date()
            if date.weekday() > 4:
                enddate_wd = ""
            else:
                enddate_wd = workdays.estimate_end_workdays( starttime, entry.endtime, ptotal, premaining )
                enddate_wd = "" if enddate_wd is None else enddate_wd.date()

            if date == today: fmt = fmttoday
            elif date.weekday() > 4: fmt = fmtweekend
            else: fmt = fmtnormal

            result.append( fmt % (date, ptotal, premaining, pnew, pwip, pdone, enddate, enddate_wd,
                    self._dayStateGraph( date, enddate_wd, dmin, dmax ) ) )
        result.append( "" )

        newtext = "\n".join( result )
        out = StringIO.StringIO()
        Formatter(self.env, formatter.context).format(newtext, out)
        return Markup(out.getvalue())

    # calculate the limits for the "graph"
    def _getMinMaxEstimateDelta( self, timetable, starttime ):
        import workdays
        dmin = 0
        dmax = 0

        def estimate(tinfo, default=1):
            v = tinfo.value_or( self.tt_config.estimation_field, default )
            try: return float(v) if v is not None else default
            except: return default

        for entry in timetable.entries:
            date = entry.endtime.date()
            if date.weekday() > 4:
                continue
            pdone = sum( estimate(t) for t in entry.tickets if t.status in self.tt_config.closed_states )
            ptotal = sum( estimate(t) for t in entry.tickets )
            premaining = ptotal - pdone
            enddate_wd = workdays.estimate_end_workdays( starttime, entry.endtime, ptotal, premaining )
            if enddate_wd is None:
                continue
            delta = (enddate_wd.date() - date).days
            if delta < dmin:
                dmin = delta
            if delta > dmax:
                dmax = delta
        return (dmin, dmax)

    def _dayStateGraph( self, graphdate, enddate, dmin, dmax ):
        if graphdate is None or enddate is None or enddate == "":
            return ""
        delta = (enddate - graphdate).days
        # FIXME: can't insert {{{#!html}}} into a || table
        # return '<div style="color:red;width:100px;" />'
        return ("%d" % delta) if delta <= 0 else "+%d" % delta
