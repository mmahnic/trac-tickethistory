## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

from trac.wiki.model import WikiPage
import csv
import time, datetime as dt


class IterationInfo:
    """
    Information about an iteration.
    """

    def __init__(self, name, startdate, enddate):
        self.name = name
        self.startdate = self._parse_date(startdate)
        self.enddate = self._parse_date(enddate)


    def _parse_date( self, datestr ):
        return dt.datetime(*time.strptime(datestr, "%Y-%m-%d")[0:5]).date()


class IterationInfoWikiTable:
    """
    Read the information about iterations from a CSV table in a wiki page.

    The CSV table is enclosed in a preformat blok on the page.  The block
    starts with a line that starts with `{{{` and ends with a line that
    contains only `}}}`.  The CSV delimiter used is a comma (,) and the
    quotation character is a double qoute (").  The table should have the
    following three columns: name,startdate,enddate.  Extra columns are
    ignored.  The dates are written in ISO format: YYYY-MM-DD.  The lines with
    invalid dates are skipped.

    This is an alterntive for not using a real table.
    """
    def __init__(self, env, wikipage):
        self.env = env
        self.wikiPage = wikipage
        self.retrievedVersion = None
        self.iterations = []


    def getIterationList(self):
        self.reloadIterations()
        return self.iterations


    def getIterationByName(self, name):
        self.reloadIterations()
        for i in self.iterations:
            if i.name == name:
                return i
        return None


    def getIterationsByDate(self, date):
        self.reloadIterations()
        res = [ i for i in self.iterations
                if date >= i.startdate and date <= i.enddate ]
        return res


    def reloadIterations(self):
        page = WikiPage(self.env, self.wikiPage)
        if page == None or not page.exists:
            return
        if self.retrievedVersion is not None:
            if self.retrievedVersion >= page.version:
                return
        self.iterations = self.extractIterations(self, page.text)
        self.retrievedVersion = page.version


    def extractIterations(self, text):
        table = []
        inblock = False
        headerSkipped = False
        for line in text.split( "\n" ):
            line = line.strip()
            if not inblock:
                if line.startswith("{{{"):
                    inblock = True
                    continue
            else:
                if line == "}}}":
                    break
                if len(line) > 0:
                    table.append( line )

        iterations = []
        for row in csv.reader(table, delimiter=',', quotechar='"'):
            if len(row) < 3:
                continue
            try:
                iterations.append( IterationInfo( row[0], row[1], row[2] ) )
            except: pass

        return iterations

