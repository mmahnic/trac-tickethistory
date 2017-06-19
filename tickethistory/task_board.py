## Copyright (c) Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

from trac.core import implements, TracError
from trac.wiki.macros import WikiMacroBase
from trac.wiki import Formatter
from trac.wiki.api import parse_args
from trac.util.datefmt import from_utimestamp as from_timestamp, to_datetime, to_utimestamp as to_timestamp
from trac.web.chrome import ITemplateProvider, Chrome, add_stylesheet, add_script, add_script_data
from genshi.core import Markup

import datetime as dt
import time
import os

import StringIO
import math
import traceback


class ColumnInfo:
    def __init__( self, title, states ):
        self.title = title
        self.states = states

class TracMarkupBoardRenderer:
    """
    Render the task board as a table using the Trac Markup.
    """
    def __init__( self, timetableConfig ):
        self.tt_config = timetableConfig
        self.heading   = "||= New =||= In progress =||= Done =||= Summary =||"
        self.line_new  = "|| %(id)s %(est)s || || || %(sum)s ||"
        self.line_wip  = "|| || %(id)s %(est)s %(own)s || || %(sum)s ||"
        self.line_done = "|| || || %(id)s %(est)s  || %(sum)s ||"

    def render( self, tickets, env, formatter ):
        result = []
        result.append( self.heading )
        board_tickets = sorted( tickets, key=lambda t: t.tid() )
        for t in board_tickets:
            if t.status in self.tt_config.new_states: lineformat = self.line_new
            elif t.status in self.tt_config.closed_states: lineformat = self.line_done
            else: lineformat = self.line_wip

            v = {}
            v["id"] = "#%d" % t.tid()
            estimate = t.value.get(self.tt_config.estimation_field)
            v["est"] = ( "(%s)" % estimate ) if estimate is not None else ""
            v["sum"] = t.value.get("summary") or ""
            owner = t.value.get("owner")
            v["own"] = ( "[%s]" % owner ) if owner is not None else ""

            # v["sum"] = "%s" % ( t.value ) # debug
            result.append( lineformat % v )

        newtext = "\n".join( result )
        out = StringIO.StringIO()
        Formatter(env, formatter.context).format(newtext, out)
        return Markup(out.getvalue())


class HtmlBoardRenderer:
    """
    Render the task board as HTML.
    """

    def __init__( self, timetableConfig, columns=None ):
        self.tt_config = timetableConfig
        self.columns = columns
        if self.columns is None:
            self.columns = [
                    ColumnInfo( "New", timetableConfig.new_states ),
                    ColumnInfo( "In progress", "*" ),
                    ColumnInfo( "Done", timetableConfig.closed_states ) ]

        # All the unmentioned states go to this column. The defult column is
        # the first column where ColumnInfo.states="*"
        self.defaultColumn = None
        for col in self.columns:
            if type(col.states) == type("") and col.states == "*":
                col.states = []
                self.defaultColumn = col
                break

    def splitTicketsIntoColumns( self, tickets ):
        res = [ [] for c in self.columns ]
        try: idefault = self.columns.index( self.defaultColumn )
        except ValueError: idefault = -1
        for t in tickets:
            found = False
            for ic,column in enumerate(self.columns):
                if t.status in column.states:
                    res[ic].append(t)
                    found = True
            if not found and idefault >= 0:
                res[idefault].append( t )
        return res

    def render( self, tickets, env, formatter ):
        tmpl = '<a class="%(status)s ticket" href="%(href)s" title="%(type)s: %(summary)s (%(status)s)">#%(id)d</a>'
        def ticketIdAddr( ticketInfo ):
            return tmpl % ticketInfo.ticket
        add_stylesheet(formatter.req, 'tickethistory/css/tickethistory.css')

        def isInProgress( ticketInfo ):
            ttc = self.tt_config
            return t.status not in ttc.new_states and t.status not in ttc.closed_states

        columns = self.splitTicketsIntoColumns( tickets )

        result = ['<div class="tickethist-board">']
        for ic,colTickets in enumerate(columns):
            result.append( '<div class="col-4 column">' )
            result.append( env.base_url )
            result.append( '<h2 class="column-title">%s</h2>' % self.columns[ic].title )
            for t in colTickets:
                # address = env.href( 'ticket', t.tid() )
                nameLink = ticketIdAddr( t )
                estimate = t.value_or(self.tt_config.estimation_field, "")
                if estimate != "": estimate = "(%s)" % estimate
                owner = t.value_or( "owner", "" ) if isInProgress( t ) else ""
                summary = t.value_or( "summary", "" )
                noteContent = '''<div class="note">
                    <span class="note-head">
                      <span class="ticket">%s</span>
                      <span class="estimate">%s</span>
                      <span class="owner">%s</span>
                    </span>
                    &nbsp;%s
                    </div>''' % ( nameLink, estimate, owner, summary )
                result.append( noteContent )
            result.append( '</div>' )

        result.append( '</div>' )

        return Markup( "\n".join( result ) )


class TaskBoardMacro(WikiMacroBase):
    implements(ITemplateProvider)

    def _parse_options( self, content ):
        options = {}
        _, parsed_options = parse_args(content, strict=False)
        options.update(parsed_options)

        return options

    def _verify_options( self, options ):
        return options

    def _extract_query_args( self, options ):
        AVAILABLE_OPTIONS = []
        query_args = {}
        for key in options.keys():
            if not key in AVAILABLE_OPTIONS:
                query_args[key] = options[key]
        return query_args

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('tickethistory', 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('tickethistory', os.path.abspath(resource_filename('tickethistory', 'htdocs')))]

    def expand_macro(self, formatter, name, text):
        request = formatter.req
        self.env.log.debug("TaskBoardMacro TEXT %s", text)
        self.env.log.debug("TaskBoardMacro ARGS %s", request.args)

        import ticket_timetable as history
        import dbutils
        self.tt_config = history.TimetableConfig()
        retriever = dbutils.MilestoneRetriever(self.env, request)

        options = self._verify_options( self._parse_options( text ) )
        query_args = self._extract_query_args( options )
        desired_fields = [self.tt_config.estimation_field, "summary", "owner"]

        builder = history.HistoryBuilder( self.env.get_db_cnx() )
        builder.timestamp_to_datetime = lambda ts: from_timestamp( ts )
        tickets = retriever.retrieve( query_args, desired_fields )
        if 'date' in options:
            board_time = to_datetime(dt.datetime.combine(options['date'], dt.time.max))
        else:
            board_time = to_datetime(dt.datetime.now())
        start = board_time - dt.timedelta(days=1)
        board_entry = history.TimetableEntry( board_time )
        timetable = history.Timetable( start )
        timetable.entries = [ board_entry ]
        builder.fillTicketTimetable(tickets, timetable, desired_fields )

        # renderer = TracMarkupBoardRenderer(self.tt_config);
        renderer = HtmlBoardRenderer(self.tt_config);
        return renderer.render( board_entry.tickets, self.env, formatter )
