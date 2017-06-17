from genshi.core import Markup
from trac.wiki.macros import WikiMacroBase
from trac.wiki import Formatter
from trac.wiki.api import parse_args
from trac.util.datefmt import from_utimestamp as from_timestamp, to_datetime, to_utimestamp as to_timestamp

import datetime as dt
import time

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

        result = []
        for ic,colTickets in enumerate(columns):
            result.append( '<div class="col-4" style="float: left; width: 30vw">' )
            result.append( env.base_url )
            result.append( '<h2 class="columnTitle">%s</h2>' % self.columnTitles[ic] )
            for t in colTickets:
                # address = env.href( 'ticket', t.tid() )
                nameLink = ticketIdAddr( t )
                estimate = t.value_or(self.tt_config.estimation_field, "")
                if estimate != "": estimate = "(%s)" % estimate
                owner = t.value_or( "owner", "" ) if isInProgress( t ) else ""
                summary = t.value_or( "summary", "" )
                noteContent = '''<div class="ticket-note"
                        style="width: 14.5vw; height: 7vh; overflow: hidden; border: 1px solid black;">
                    <span style="background-color:#f0f0f0; font-size:120%%"> %s %s %s </span>
                    &nbsp;%s
                    </div>''' % ( nameLink, estimate, owner, summary )
                result.append( noteContent )
            result.append( '</div>' )

        return Markup( "\n".join( result ) )


class TaskBoardMacro(WikiMacroBase):
    revision = "$Rev$"
    url = "$URL$"

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

    def expand_macro(self, formatter, name, text, args):
        req = formatter.req

        import ticket_timetable as listers
        import dbutils
        self.tt_config = listers.TimetableConfig()

        options = self._verify_options( self._parse_options( text ) )
        query_args = self._extract_query_args( options )
        milestone = query_args['milestone']
        desired_fields = [self.tt_config.estimation_field, "summary", "owner"]
        dbutils.require_ticket_fields( query_args, desired_fields )

        lister = listers.CTicketListLoader( self.env.get_db_cnx() )
        lister.exec_ticket_query = lambda x, args: dbutils.get_viewable_tickets( self.env, req, args )
        lister.timestamp_to_datetime = lambda ts: from_timestamp( ts )
        tickets = lister.queryTicketsInMilestone( milestone, query_args )
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
