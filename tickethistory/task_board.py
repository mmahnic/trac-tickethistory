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

class TracMarkupBoardRenderer:
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
    def __init__( self, timetableConfig ):
        self.tt_config = timetableConfig
        self.columnTitles = [ "New", "In progress", "Done" ]

    def splitTicketsIntoColumns( self, tickets ):
        tnew = []
        twip = []
        tdone = []
        for t in tickets:
            if t.status in self.tt_config.new_states: tnew.append( t )
            elif t.status in self.tt_config.closed_states: tdone.append( t )
            else: twip.append( t )
        return (tnew, twip, tdone)

    def render( self, tickets, env, formatter ):
        tmpl = '<a class="%(status)s ticket" href="%(href)s" title="%(type)s: %(summary)s (%(status)s)">#%(id)d</a>'
        def ticketIdAddr( ticketInfo ):
            return tmpl % ticketInfo.ticket
        def isInProgress( ticketInfo ):
            ttc = self.tt_config
            return t.status not in ttc.new_states and t.status not in ttc.closed_states

        columns = self.splitTicketsIntoColumns( tickets )

        result = ['<div class="tickethist-board">']
        for ic,colTickets in enumerate(columns):
            result.append( '<div class="col-4 column">' )
            result.append( env.base_url )
            result.append( '<h2 class="column-title">%s</h2>' % self.columnTitles[ic] )
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

        import ticket_timetable as listers
        import dbutils
        self.tt_config = listers.TimetableConfig()
        retriever = dbutils.MilestoneRetriever(self.env, request)

        add_stylesheet(request, 'tickethistory/css/tickethistory.css')

        options = self._verify_options( self._parse_options( text ) )
        query_args = self._extract_query_args( options )
        # milestone = query_args['milestone']
        desired_fields = [self.tt_config.estimation_field, "summary", "owner"]
        # dbutils.require_ticket_fields( query_args, desired_fields )

        lister = listers.CTicketListLoader( self.env.get_db_cnx() )
        # lister.exec_ticket_query = lambda x, args: dbutils.get_viewable_tickets( self.env, request, args )
        lister.timestamp_to_datetime = lambda ts: from_timestamp( ts )
        # tickets = lister.queryTicketsInMilestone( milestone, query_args )
        tickets = retriever.retrieve( query_args, desired_fields )
        if 'date' in options:
            board_time = to_datetime(dt.datetime.combine(options['date'], dt.time.max))
        else:
            board_time = to_datetime(dt.datetime.now())
        start = board_time - dt.timedelta(days=1)
        board_entry = listers.TimetableEntry( board_time )
        timetable = listers.Timetable( start )
        timetable.entries = [ board_entry ]
        lister.fillTicketTimetable(tickets, timetable, desired_fields )

        # renderer = TracMarkupBoardRenderer(self.tt_config);
        renderer = HtmlBoardRenderer(self.tt_config);
        return renderer.render( board_entry.tickets, self.env, formatter )
