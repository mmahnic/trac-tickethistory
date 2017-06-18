import copy
import re

class TimetableConfig:
    def __init__(self):
        self.closed_states = [ "closed" ]
        self.new_states = [ "new" ]
        self.estimation_field = "tm_estimate"

class TicketInfo:
    def __init__(self, ticket, time, status, milestone):
        self.time = time
        self.ticket = ticket
        self.status = status
        self.milestone = milestone
        self.value = {} # other fields

    def tid( self ):
        return self.ticket['id'] if self.ticket is not None else None

    def value_or( self, name, default=None):
        return self.value[name] if name in self.value else default

    def __repr__(self):
        return "(T %s, %s, %s, %s)" % ( self.tid(), self.status, self.time, len(self.value) )


class TimetableEntry:
    def __init__(self, endtime):
        self.endtime = endtime # end of the period
        self.tickets = [] # list of TicketInfo
        self.debug = {}


class Timetable:
    def __init__(self, startTime=None):
        self.startTime = startTime
        self.endTime = None
        self.entries = []

    def sort( self ):
        self.entries.sort(key=lambda e: e.endtime)
        times = [ e.endtime for e in self.entries if e.endtime is not None ]
        self.endTime = times[-1] if len(times) > 0 else None
        startTime = times[0] if len(times) > 0 else None
        if startTime is not None:
            if self.startTime is None or startTime < self.startTime:
                self.startTime = startTime

    def getEntryForTime( self, time ):
        if time < self.startTime:
            return self.entries[0]
        if time > self.endTime:
            return None
        for t in self.entries:
            if time <= t.endtime:
                return t
        return None

    def _propagateTicketInfoForward( self ):
        prev_entry = None
        for entry in self.entries:
            if prev_entry is not None:
                prev_tickets = { t.tid() : t for t in prev_entry.tickets }
                curr_tickets = { t.tid() : t for t in entry.tickets }
                for tid,t in prev_tickets.items():
                    if tid not in curr_tickets:
                        entry.tickets.append( copy.copy( t ) )
            prev_entry = entry


class CTicketListLoader:
    def __init__(self, database):
        self.database = database

	def invalid(msg) : raise Exception( msg )

        # exec_ticket_query should call trac.ticket.query.Query.execute and return its results.
        self.exec_ticket_query = lambda self, query_args: invalid( "exec_ticket_query not set" )
        self.timestamp_to_datetime = lambda tstamp: invalid( "timestamp_to_datetime not set" )


    def getTicketIdsInMilestone( self, milestone ):
        tid_cursor = self.database.cursor()
        tid_cursor.execute("SELECT "
            "DISTINCT t.id "
            "FROM ticket t LEFT JOIN ticket_change c "
            "ON c.ticket = t.id "
            "  WHERE (t.milestone=%s OR (field='milestone' AND (c.oldvalue=%s OR c.newvalue=%s) ) )"
            "", [ milestone, milestone, milestone ])

        return sorted( [int(row[0]) for row in tid_cursor] )


    # @Returns the result of self.exec_ticket_query for the tickets
    def queryTicketsInMilestone( self, milestone, query_args ):
        ids = self.getTicketIdsInMilestone( milestone )
        query_args = copy.copy( query_args )
        query_args["id"] = "|".join( ["%d" % tid for tid in ids] )
        query_args['milestone!'] = "###"

        return self.exec_ticket_query(self, query_args)


    # @p tickets - a list of dictionaries as returned by trac.ticket.query.Query.execute
    # @p timetable - Timetable with a list of TimetableEntry instances
    # @p fieldNames - a list of fields to register in TicketInfo.field (status
    #    and milestone will be added automatically)
    def fillTicketTimetable( self, tickets, timetable, fieldNames ):
        if len(tickets) == 0 or len(timetable.entries) == 0:
            return
        timetable.sort()
        fields = set( fieldNames )
        fields.add( 'milestone' )
        fields.add( 'status' )
        fields.discard( 'id' )
        historySettings = self._HistorySettings( fields )

        for t in tickets:
            history = self._collectTicketHistory( t, historySettings )
            self._generateTicketInfo( t, history, timetable )

        timetable._propagateTicketInfoForward()


    class _HistorySettings:
        def __init__(self, fields):
            self.fields = fields
            self.ticket_query_sql = None

            rxvalidfiled = re.compile( '^[A-Za-z0-9._]+$' )
            sql_field_list = ", ".join( ["'%s'" % f for f in fields if rxvalidfiled.match(f) is not None] )
            self.ticket_query_sql = ( "SELECT "
                    "DISTINCT c.field as field, c.time AS time, c.oldvalue as oldvalue, c.newvalue as newvalue "
                    "FROM ticket t, ticket_change c "
                    "WHERE t.id = %%s and c.ticket = t.id and (c.field in (%s))"
                    "ORDER BY c.time ASC" % ( sql_field_list ) )


    # Collect history for a single ticket.
    def _collectTicketHistory( self, ticket, historySettings ):
        t = ticket
        creation_time = t['time']
        settings = historySettings
        fields = settings.fields

        history_cursor = self.database.cursor()
        history_cursor.execute( settings.ticket_query_sql, [t['id']]  )

        earliest = { f : None for f in fields }
        latest = { f : t.get(f) for f in fields }
        # for every change register the new state { field:value }
        history = { creation_time : { f : None for f in fields } }

        # collect history for the ticket
        for row in history_cursor:
            row_field, row_time, row_old, row_new = row
            event_time = self.timestamp_to_datetime(row_time)
            if not event_time in history:
                history[event_time] = {}
            history[event_time][row_field] = row_new
            if earliest[row_field] is None:
                earliest[row_field] = row_old

        # project missing values into creation_time
        for f in fields:
            if f not in history[creation_time] or history[creation_time][f] is None:
                history[creation_time][f] = earliest[f] if earliest[f] is not None else latest[f]

        return history


    # Add history entries for a single ticket to the timetable.
    def _generateTicketInfo( self, ticket, history, timetable ):
        def addTicketToTimetableEntry( ticket, time, state, tt_entry ):
            state = copy.copy( state ) # clone
            ticket_info = TicketInfo( ticket, time, state['status'], state['milestone'] )
            del state['status']
            del state['milestone']
            ticket_info.value = state;
            tt_entry.tickets.append( ticket_info )

        state = {}
        prev_entry = None
        for hist_time in sorted(history.keys()):
            entry = timetable.getEntryForTime(hist_time)
            if entry == None:
                break
            if entry != prev_entry:
                if prev_entry is not None:
                    addTicketToTimetableEntry( ticket, hist_time, state, prev_entry )
                prev_entry = entry
            state_change = history[hist_time]
            state.update( state_change )

        if prev_entry != None:
            addTicketToTimetableEntry( ticket, hist_time, state, prev_entry )

