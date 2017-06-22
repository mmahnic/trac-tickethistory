from ..iterationinfo import *
import traceback

tests=[]
def test( fn ):
    tests.append(fn)
    return fn

def runTests():
    for t in tests:
        print t
        try: t()
        except Exception as e:
            print e
            traceback.print_exc()
        print

@test
def shouldReadCsvFromWikiText():
    table = IterationInfoWikiTable(None, "Test")
    text ="""
{{{ Wiki CSV table
name,startdate,enddate
SprintOne,2017-06-19,2017-06-23
SprintTwo,2017-06-26,2017-06-30
}}}"""
    iterations = table.extractIterations( text )
    if len(iterations) != 2:
        raise Exception( "Expected 2 iterations" )
    if iterations[0].name != "SprintOne":
        raise Exception( "Expected SprintOne" )
    if iterations[1].name != "SprintTwo":
        raise Exception( "Expected SprintTwo" )

runTests()
