## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

from trac.wiki.api import parse_args

class OptionRegistry(object):
    """
    Combine the options from various sources:
        - trac.ini
        - macro parameteres
        - url
    The options contain two sets of entries: real options and query arguments.
    The list of real option names is set in the constructor.
    """

    def __init__(self, realOptions=[]):
        self.iniParams = None
        self.macroParams = None
        self.urlParams = None
        self.realOptions = set(realOptions) if realOptions is not None else set()

    @staticmethod
    def _parseArgs(text, strict):
        options = {}
        for line in text.strip().split("\n"):
            _, args = parse_args(line.strip(), strict)
            options.update( args )
        return options

    def get_parameter_sets(self):
        return (self.iniParams, self.macroParams, self.urlParams)

    def set_ini_params( self, params, useStrictParsing=False ):
        if type(params) == type("") or type(params) == unicode:
            self.iniParams = OptionRegistry._parseArgs(params, useStrictParsing)
        else:
            self.iniParams = params

    def set_macro_params( self, params, useStrictParsing=False ):
        if type(params) == type("") or type(params) == unicode:
            self.macroParams = OptionRegistry._parseArgs(params, useStrictParsing)
        else:
            self.macroParams = params

    def set_url_params( self, params, useStrictParsing=False ):
        if type(params) == type("") or type(params) == unicode:
            self.urlParams = OptionRegistry._parseArgs(params, useStrictParsing)
        else:
            self.urlParams = params

    def all_arguments( self ):
        options = {}
        for params in self.get_parameter_sets():
            if params is not None:
                options.update(params)
        return options

    def options( self ):
        options = {}
        for params in self.get_parameter_sets():
            if params is not None:
                for k,v in params.iteritems():
                    if k in self.realOptions:
                        options[k] = v
        return options

    def query_args( self ):
        options = {}
        for params in self.get_parameter_sets():
            if params is not None:
                for k,v in params.iteritems():
                    # "page" is in the url params by default, but breaks Query.
                    if k == "page":
                        continue
                    if k not in self.realOptions:
                        options[k] = v
        return options

    def verify(self):
        pass
