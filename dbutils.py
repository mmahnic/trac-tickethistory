from trac.util.text import unicode_urlencode
from trac.ticket.query import Query
import copy


def _encode_trac_query( query_args ):
    return unicode_urlencode(query_args) \
	.replace('%21=', '!=') \
        .replace('%21%7E=', '!~=') \
        .replace('%7E=', '~=') \
        .replace('%5E=', '^=') \
        .replace('%24=', '$=') \
        .replace('%21%5E=', '!^=') \
        .replace('%21%24=', '!$=') \
        .replace('%7C', '|') \
        .replace('+', ' ') \
        .replace('%23', '#') \
        .replace('%28', '(') \
        .replace('%29', ')')


def get_viewable_tickets(env, req, query_args):
    # set maximum number of returned tickets to 0 to get all tickets at once
    query_args = copy.copy( query_args )
    query_args['max'] = 0
    query_string = _encode_trac_query( query_args )
    env.log.debug("query_string: %s", query_string)
    query = Query.from_string(env, query_string)

    tickets = query.execute(req)

    tickets = [t for t in tickets
               if ('TICKET_VIEW' or 'TICKET_VIEW_CC')
               in req.perm('ticket', t['id'])]

    return tickets


def require_ticket_fields( query_args, fieldnames ):
    for f in fieldnames:
        if not f in query_args:
            query_args[ f + "!" ] = "###"


