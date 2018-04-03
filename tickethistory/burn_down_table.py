## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

import time
import StringIO
import math
import traceback
import datetime as dt

from trac.wiki import Formatter
from trac.wiki.macros import WikiMacroBase
from trac.wiki.api import parse_args
from trac.util.datefmt import from_utimestamp as from_timestamp, to_datetime, to_utimestamp as to_timestamp
from trac.core import implements, TracError
from trac.web.chrome import ITemplateProvider, Chrome, add_stylesheet, add_script, add_script_data
from tickethistory import options, dbutils, workdays, ticket_timetable as history
from genshi.core import Markup


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


class BurnDownTableGraphColumn:
    """
    The graph shows the delay with two bars: the red bar is shown if the amount
    of completed work is behind schedule and the green bar is shown if the work
    is ahead of schedule.
    """
    def __init__(self, timeTableConfig, timeTable, milestoneStart, milestoneEnd ):
        self.tt_config = timeTableConfig
        self.timetable = timeTable
        self.starttime = milestoneStart
        self.endtime = milestoneEnd
        # graphs after this date have the style cg-future
        self.futureDate = (dt.datetime.today() + dt.timedelta(days=1)).date()
        self._updateMinMaxEstimatedDelay()


    # Calculate the limits for the "graph": the min and max projected delay.
    # Negative values mean that some work was done ahead of time.
    def _updateMinMaxEstimatedDelay(self, low=-8, high=+22):
        self.minDelay = 0
        self.maxDelay = 0

        def estimate(tinfo, default=1):
            v = tinfo.value_or( self.tt_config.estimation_field, default )
            try: return max(float(v), self.tt_config.min_estimation) if v is not None else default
            except: return default

        for entry in self.timetable.entries:
            date = entry.endtime.date()
            if date.weekday() > 4:
                continue
            pdone = sum( estimate(t) for t in entry.tickets if t.status in self.tt_config.closed_states )
            ptotal = sum( estimate(t) for t in entry.tickets )
            premaining = ptotal - pdone
            enddate_wd = workdays.estimate_end_workdays( self.starttime, entry.endtime, ptotal, premaining )
            if enddate_wd is None:
                continue
            delay = (enddate_wd.date() - self.endtime.date()).days
            if delay < self.minDelay:
                self.minDelay = delay
            if delay > self.maxDelay:
                self.maxDelay = delay
        if self.minDelay < low:
            self.minDelay = low
        if self.minDelay > low / 2:
            self.minDelay = low / 2
        if self.maxDelay > high:
            self.maxDelay = high
        if self.maxDelay < high / 2:
            self.maxDelay = high / 2


    def getDayStateGraph( self, graphdate, enddate ):
        if graphdate is None or enddate is None or enddate == "":
            return ""

        delay = (enddate - self.endtime.date()).days
        delayStr = ("%d" % delay) if delay <= 0 else "+%d" % delay
        delayClass = ""
        if delay < self.minDelay:
            delay = self.minDelay
            delayClass = " cg-aheadalot"
        if delay > self.maxDelay:
            delay = self.maxDelay
            delayClass = " cg-behindalot"
        scale = 4
        leftEmpty = ( 0 if delay > 0 else delay ) - self.minDelay
        ahead = 0 if delay >= 0 else -delay
        behind = 0 if delay <= 0 else delay
        rightEmpty = self.maxDelay - ( 0 if delay <= 0 else delay )
        cssFuture = " cg-future" if graphdate > self.futureDate else ""
        divs = [
                '<div class="cg-box%s">' % cssFuture,
                '<div class="cg-empty" style="width:%dpx;">&nbsp;</div>' % leftEmpty * scale,
                '<div class="cg-ahead" style="width:%dpx;">&nbsp;</div>' % ahead * scale,
                '<div class="cg-zero" style="width:4px;">&nbsp;</div>',
                '<div class="cg-behind" style="width:%dpx;">&nbsp;</div>' % behind * scale,
                '<div class="cg-empty" style="width:%dpx;">&nbsp;</div>' % rightEmpty * scale,
                '<div class="cg-text%s"> %s</div>' % (delayClass, delayStr),
                '</div>'
                ]
        return "".join(divs)


class HtmlBurnDownTableRenderer:
    def __init__(self, timeTableConfig, graphColumnRenderer ):
        self.tt_config = timeTableConfig
        self.graphColumn = graphColumnRenderer
        self.columns = [ "Date", "Total", "Remain", "New", "WiP", "Done", "End", "End*", "Delay" ]
        self.formats = [ "%s", "%.1f", "%.1f", "%.1f", "%.1f", "%.1f", "%s", "%s", "%s" ]
        self.alignments = [ "left", "right", "right", "right", "right", "right", "left", "left", "initial" ]
        self.tableRows = []


    def headerCells( self ):
        cells = [ '<th style="text-align:%s;">%s</th>' % (self.alignments[ic], c)
                for ic,c in enumerate(self.columns) ]
        return cells


    def addRow( self, cssclass, date, total, remain, new, wip, done, end, wd_end, graph ):
        values = [ date, total, remain, new, wip, done, end, wd_end, graph ]
        cells = [ '<td class="%s" style="text-align:%s;">%s</td>' % (cssclass, self.alignments[ic],
                self.formats[ic] % v if v != None else "")
                for ic,v in enumerate(values) ]
        self.tableRows.append( cells )


    def getContent( self ):
        content = [ '<table class="burn-down-table">' ]
        content += [ "<tr>" ] + self.headerCells() + [ "</tr>" ]
        for r in self.tableRows:
            content += [ "<tr>" ] + r + [ "</tr>" ]
        content.append( '</table>' )
        return "".join( content )


    def render(self, entries, starttime, today, formatter ):
        add_stylesheet(formatter.req, 'tickethistory/css/burndowntable.css')

        def estimate(tinfo, default=1):
            v = tinfo.value_or( self.tt_config.estimation_field, default )
            try: return max(float(v), self.tt_config.min_estimation) if v is not None else default
            except: return default

        for entry in entries:
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

            if date == today: cssclass = "today"
            elif date.weekday() > 4: cssclass = "weekend"
            else: cssclass = "normal"

            self.addRow( cssclass, date, ptotal, premaining, pnew, pwip, pdone, enddate, enddate_wd,
                    self.graphColumn.getDayStateGraph( date, enddate_wd ) )

        return Markup(self.getContent())


class DebugDumpRenderer:
    def __init__(self, timeTableConfig, env ):
        self.tt_config = timeTableConfig
        self.env = env


    def setFlagProvider( self, flagProvider ):
        pass


    def render(self, entries, starttime, today, formatter ):
        result = []
        for entry in entries:
            date = entry.endtime.date()
            result.append( "== %s" % date )
            result.append( "{{{" )
            for t in entry.tickets:
                result.append( "Ticket %s" % t.value_or( "id", "?" ) )
                result.append( "  Status '%s'" % t.status )
                result.append( "  Milestone '%s'" % t.milestone )
                result.append( "  Estimate '%s'" % t.value_or( self.tt_config.estimation_field, "-" ) )
                # result.append( "  Ticket content:" )
                # for k,v in t.ticket.iteritems():
                #     result.append( "     %s: %s" % (k, v) )
            result.append( "}}}" )

        newtext = "\n".join( result )
        out = StringIO.StringIO()
        Formatter(self.env, formatter.context).format(newtext, out)
        return Markup(out.getvalue())


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
        desired_fields = desired_fields + self.tt_config.iteration_fields

        isInIteration = self.tt_config.getIsInIteration( query_args );

        builder = history.HistoryBuilder( self.env.get_db_cnx(), isInIteration )
        builder.timestamp_to_datetime = lambda ts: from_timestamp( ts )
        tickets = retriever.retrieve( query_args, desired_fields )

        starttime = to_datetime(dt.datetime.combine(options['startdate'], dt.time.min))
        time_first = to_datetime(dt.datetime.combine(options['startdate'], dt.time.max))
        time_end = to_datetime(dt.datetime.combine(options['enddate'], dt.time.max))
        today = options['today']
        delta = dt.timedelta(days=1)

        timetable = history.Timetable( starttime )
        timetable.entries = [ history.TimetableEntry( time_first ) ]
        time_next = time_first + delta
        while time_next <= time_end:
            timetable.entries.append( history.TimetableEntry( time_next ) )
            time_next += delta
        if today > time_end.date():
            timetable.entries.append( history.TimetableEntry(
                    to_datetime(dt.datetime.combine(today, dt.time.max))) )

        builder.fillTicketTimetable(tickets, timetable, [self.tt_config.estimation_field] )

        graph = BurnDownTableGraphColumn( self.tt_config, timetable, starttime, time_end )
        # renderer = DebugDumpRenderer( self.tt_config, self.env )
        renderer = HtmlBurnDownTableRenderer(self.tt_config, graph)
        return renderer.render( timetable.entries, starttime, today, formatter )

