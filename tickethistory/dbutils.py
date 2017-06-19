## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

from trac.ticket.query import Query
import copy


def _clean_args( args ):
    return args

def to_query_string( args ):
    return '&'.join('%s=%s' % item for item in args.iteritems())


class Retriever(object):
    """
    Retrieve the tickets from the database using the arguments compatible with
    the TicketQuery macro.
    """

    def __init__(self, env, request):
        self.env = env
        self.request = request
        self.vieableOnly = False


    def get_tickets(self, query_args, extra_columns=None):
        # set maximum number of returned tickets to 0 to get all tickets at once
        query_args = copy.copy( query_args )
        if not 'max' in query_args:
            query_args['max'] = 0
        if extra_columns is not None:
            for f in extra_columns:
                if not f in query_args:
                    query_args[ f + "!" ] = "###"
        self.env.log.debug("Retrieve: %s", query_args)
        query_string = to_query_string( _clean_args(query_args) )

        query = Query.from_string(self.env, query_string)
        return query.execute(self.request)


    def get_viewable_tickets(self, query_args, extra_columns=None):
        tickets = self.get_tickets( query_args, extra_columns )
        tickets = [t for t in tickets
                   if ('TICKET_VIEW' or 'TICKET_VIEW_CC')
                   in self.request.perm('ticket', t['id'])]
        return tickets


    def retrieve( self, query_args, extra_columns=None ):
        if self.vieableOnly:
            return self.get_viewable_tickets( query_args, extra_columns )
        else:
            return self.get_tickets( query_args, extra_columns )


class MilestoneRetriever(Retriever):
    """
    Retrieve the tickets that were at any time part of the milestone from the
    database using the arguments compatible with the TicketQuery macro.  The
    arguments for retrieve() must contain the 'milestone' attribute.
    """

    def __init__(self, env, request):
        super(MilestoneRetriever, self).__init__(env, request)


    def get_ticket_ids_in_milestone( self, milestone ):
        database = self.env.get_db_cnx()
        tid_cursor = database.cursor()
        tid_cursor.execute("SELECT "
            "DISTINCT t.id "
            "FROM ticket t LEFT JOIN ticket_change c "
            "ON c.ticket = t.id "
            "  WHERE (t.milestone=%s OR (field='milestone' AND (c.oldvalue=%s OR c.newvalue=%s) ) )"
            "", [ milestone, milestone, milestone ])

        return sorted( [int(row[0]) for row in tid_cursor] )


    def retrieve( self, query_args, extra_columns=None ):
        milestone = query_args['milestone']
        ids = self.get_ticket_ids_in_milestone( milestone )
        query_args = copy.copy( query_args )
        query_args["id"] = "|".join( ["%d" % tid for tid in ids] )

        return super(MilestoneRetriever, self).retrieve( query_args, extra_columns )


