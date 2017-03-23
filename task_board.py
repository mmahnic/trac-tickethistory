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
        self.estimation_field = "tm_estimate"
        self.closed_states = [ "closed" ]
        self.new_states = [ "new" ]
        req = formatter.req

        import ticket_timetable as listers
        import dbutils

        options = self._verify_options( self._parse_options( text ) )
        query_args = self._extract_query_args( options )
        milestone = query_args['milestone']
        dbutils.require_ticket_fields( query_args, [self.estimation_field, "summary"] )

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
        lister.fillTicketTimetable(tickets, timetable, [self.estimation_field, "summary"] )

        result = []
        result.append( "||= New =||= In progress =||= Done =||= Summary =||" )
        line_new  = "|| %s || || || %s ||"
        line_wip  = "|| || %s || || %s ||"
        line_done = "|| || || %s || %s ||"
        board_tickets = sorted( board_entry.tickets, key=lambda t: t.tid )
        for t in board_tickets:
            if t.status in self.new_states: lineformat = line_new
            elif t.status in self.closed_states: lineformat = line_done
            else: lineformat = line_wip
            estimate = t.value.get(self.estimation_field)
            estimate = ( "(%s)" % estimate ) if estimate is not None else ""
            summary = t.value.get("summary") or ""
            result.append( lineformat % ( "#%d %s" % ( t.tid, estimate ), summary ) )
            # result.append( lineformat % ( t.value ) )

        newtext = "\n".join( result )
        out = StringIO.StringIO()
        Formatter(self.env, formatter.context).format(newtext, out)
        return Markup(out.getvalue())
