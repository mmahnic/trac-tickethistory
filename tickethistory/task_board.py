## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

import time
import os
import StringIO
import math
import traceback
import datetime as dt

from trac.core import implements, TracError
from trac.wiki.macros import WikiMacroBase
from trac.wiki import Formatter
from trac.wiki.api import parse_args
from trac.util.datefmt import from_utimestamp as from_timestamp, to_datetime, to_utimestamp as to_timestamp
from trac.web.chrome import ITemplateProvider, Chrome, add_stylesheet, add_script, add_script_data
from genshi.core import Markup

from tickethistory import options, dbutils, distributor
from tickethistory import ticket_timetable as history

class ColumnInfo:
    def __init__( self, title, states ):
        self.title = title
        self.states = states


class NoteFlag:
    def __init__(self, text=None, style=None ):
        self.text = text
        self.style = style


class NoteFlagProvider:
    def __init__( self ):
        self.extra_fields = ["component"]
        self.stylesheet = None
        self.test_states = [ "testing" ]

    def getFlags( self, ticketInfo ):
        res = []

        status = ticketInfo.value_or( "status", "" )
        if status in self.test_states:
            res.append(NoteFlag("Test", "flag-test"))

        component = ticketInfo.value_or( "component", None )
        if component is not None and len(component) > 0:
            res.append(NoteFlag(component[:6], "flag-component"))

        return res


class SortOrderProvider:
    def __init__( self ):
        self.extra_fields = ["component"]

    def sortTicketInfos( self, tickets ):
        tickets.sort( key=lambda ti: (ti.value_or( "component", "" ), ti.ticket['id']) )


class NoteClassProvider:
    def __init__( self ):
        self.extra_fields = ["priority"]

    def getClasses( self, ticketInfo ):
        res = []

        priority = ticketInfo.value_or( "priority", "" )
        if len( priority ):
            res.append( "priority-{}".format( priority ) )

        return res


class DebugDumpRenderer:
    def __init__( self, timetableConfig ):
        self.tt_config = timetableConfig

    def setFlagProvider( self, flagProvider ):
        pass

    def setSortProvider( self, sortProvider ):
        pass

    def setNoteClassProvider( self, classProvider ):
        pass

    def render( self, tickets, env, formatter ):
        result = ["{{{"]
        board_tickets = sorted( tickets, key=lambda t: t.tid() )
        for t in board_tickets:
            result.append( "Ticket %s" % t.value_or( "id", "?" ) )
            result.append( "  Status '%s'" % t.status )
            result.append( "  Milestone '%s'" % t.milestone )
            result.append( "  Ticket content:" )
            for k,v in t.ticket.iteritems():
                result.append( "     %s: %s" % (k, v) )

        result.append( "}}}" )
        newtext = "\n".join( result )
        out = StringIO.StringIO()
        Formatter(env, formatter.context).format(newtext, out)
        return Markup(out.getvalue())


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

    def setFlagProvider( self, flagProvider ):
        pass

    def setSortProvider( self, sortProvider ):
        pass

    def setNoteClassProvider( self, classProvider ):
        pass

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

    tid_tmpl = '<a class="%(status)s ticket" href="%(href)s" title="%(type)s: %(summary)s (%(status)s)">#%(id)d</a>'

    def __init__( self, timetableConfig, columns=None ):
        self.tt_config = timetableConfig
        self.columns = columns
        self.flagProvider = None
        self.sortProvider = None
        if self.columns is None:
            self.columns = [
                    ColumnInfo( "New", timetableConfig.new_states ),
                    ColumnInfo( "In progress", "*" ),
                    ColumnInfo( "Done", timetableConfig.closed_states ) ]

        # All the unmentioned states go to this column. The defult column is
        # the first column where ColumnInfo.states="*"
        self.defaultColumn = None
        for col in self.columns:
            if type(col.states) == type(""):
                if self.defaultColumn is None and col.states == "*":
                    self.defaultColumn = col
                col.states = []


    def setFlagProvider( self, flagProvider ):
        self.flagProvider = flagProvider


    def setSortProvider( self, sortProvider ):
        self.sortProvider = sortProvider

    def setNoteClassProvider( self, classProvider ):
        self.classProvider = classProvider
        pass


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


    def calculateColumnSizes( self, columns ):
        if len(columns) == 0:
            return []
        return distributor.distributeItems( [len(c) for c in columns], 12, 2, 1 )


    @staticmethod
    def _ticketIdAddr( ticketInfo ):
        return HtmlBoardRenderer.tid_tmpl % ticketInfo.ticket

    def _renderFlags( self, ticket, result ):
        flags = None if self.flagProvider is None else self.flagProvider.getFlags( ticket )
        if flags is not None and len(flags) > 0:
            result.append( '''<div class="flags">''' )
            for f in flags:
                text = f.text if f.text is not None else ""
                style = " " + f.style if f.style is not None else ""
                result.append( '''<div class="flag%s">%s</div>''' % (style, text) )
            result.append( '</div>' )

    def render( self, tickets, env, formatter ):
        add_stylesheet(formatter.req, 'tickethistory/css/tickethistory.css')

        def isInProgress( ticketInfo ):
            ttc = self.tt_config
            status = ticketInfo.value_or( "status", "" )
            return status not in ttc.new_states and status not in ttc.closed_states

        columns = self.splitTicketsIntoColumns( tickets )
        sizes = self.calculateColumnSizes( columns )

        result = ['<div class="tickethist-board">']
        for ic,colTickets in enumerate(columns):
            if self.sortProvider is not None:
                self.sortProvider.sortTicketInfos( colTickets )

            result.append( '<div class="col-%d column">' % sizes[ic] )
            result.append( '<h2 class="column-title">%s</h2>' % self.columns[ic].title )
            result.append( '<div class="column-content">' )
            for t in colTickets:
                nameLink = HtmlBoardRenderer._ticketIdAddr( t )
                estimate = t.value_or(self.tt_config.estimation_field, "")
                if estimate != "": estimate = "(%s)" % estimate
                owner = t.value_or( "owner", "" ) if isInProgress( t ) else ""
                summary = t.value_or( "summary", "" )

                noteClass = ""
                if self.classProvider is not None:
                    noteClass = " ".join( self.classProvider.getClasses( t ) )

                result.append( '''<div class="note-box">''' )
                noteContent = '''
                  <div class="note %s">
                  <span class="note-head">
                    <span class="ticket">%s</span>
                    <span class="estimate">%s</span>
                    <span class="owner">%s</span>
                  </span>
                  &nbsp;%s
                  </div>''' % ( noteClass, nameLink, estimate, owner, summary )
                result.append( noteContent )

                if self.flagProvider is not None:
                    self._renderFlags( t, result )
                result.append( '</div>' ) # note-box

            result.append( '</div>' ) # column-content
            result.append( '</div>' ) # column

        result.append( '</div>' )

        return Markup( "\n".join( result ) )


class TaskBoardOptions(options.OptionRegistry):
    def __init__(self):
        super(TaskBoardOptions, self).__init__([])


class TaskBoardMacro(WikiMacroBase):
    implements(ITemplateProvider)

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('tickethistory', 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('tickethistory', os.path.abspath(resource_filename('tickethistory', 'htdocs')))]

    def expand_macro(self, formatter, name, text, args):
        request = formatter.req
        # self.env.log.debug("TaskBoardMacro TEXT %s", text)
        # self.env.log.debug("TaskBoardMacro ARGS %s", args)

        self.tt_config = history.TimetableConfig()
        retriever = dbutils.MilestoneRetriever(self.env, request)

        optionReg = TaskBoardOptions()
        optionReg.set_macro_params(text)
        optionReg.set_url_params(request.args)
        optionReg.verify()
        options = optionReg.options()
        query_args = optionReg.query_args()

        flagProvider = NoteFlagProvider()
        sortProvider = SortOrderProvider()
        classProvider = NoteClassProvider();

        desired_fields = [self.tt_config.estimation_field, "summary", "owner", "type"]
        desired_fields = desired_fields + self.tt_config.iteration_fields
        desired_fields = desired_fields + flagProvider.extra_fields
        desired_fields = desired_fields + sortProvider.extra_fields
        desired_fields = desired_fields + classProvider.extra_fields
        # self.env.log.debug("TaskBoardMacro OPTIONS %s", options)
        # self.env.log.debug("TaskBoardMacro QUERY %s", query_args)

        isInIteration = self.tt_config.getIsInIteration( query_args );

        builder = history.HistoryBuilder( self.env.get_db_cnx(), isInIteration )
        builder.timestamp_to_datetime = lambda ts: from_timestamp( ts )
        tickets = retriever.retrieve( query_args, desired_fields )
        # self.env.log.debug("TaskBoardMacro TICKETS in milestone: %s", [t['id'] for t in tickets])
        if 'date' in options:
            board_time = to_datetime(dt.datetime.combine(options['date'], dt.time.max))
        else:
            board_time = to_datetime(dt.datetime.now())
        start = board_time - dt.timedelta(days=1)
        board_entry = history.TimetableEntry( board_time )
        timetable = history.Timetable( start )
        timetable.entries = [ board_entry ]
        builder.fillTicketTimetable(tickets, timetable, desired_fields )

        # renderer = DebugDumpRenderer( self.tt_config )
        # renderer = TracMarkupBoardRenderer(self.tt_config)
        renderer = HtmlBoardRenderer(self.tt_config)
        renderer.setFlagProvider( flagProvider )
        renderer.setSortProvider( sortProvider )
        renderer.setNoteClassProvider( classProvider )
        return renderer.render( board_entry.tickets, self.env, formatter )
