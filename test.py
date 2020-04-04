"""
Test for nested try-except clauses
Simple puzzle - assign g[1] to g[5] values of 1 or 2 to make a total of 8
"""
from model import *

g = model( { 'i' : 1 } )

class Done( Exception):
	pass

def doCell():
	if g.i > 5:
		lst = [ g[ n ] for n in range( 1, 6 ) ]
		tot = sum( lst )
		print tot , lst , len( g.trys )
		if tot == 8:
			raise Done
		else:
			raise Clash
	if not g.i in g:
		try:
			g.spec()
			g[ g.i ] = 1
			g.i += 1
			doCell()
		except Clash:
			g.untry()
			g[ g.i ] = 2 # now forced by elimination
			g.i += 1
			doCell()
		except Done:
			print 20 * '--'
			g.untry()
			g[ g.i ] = 2 # now forced by elimination
			g.i += 1
			doCell()
		except Contradiction:
			pass

doCell()
