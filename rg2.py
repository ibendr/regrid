"""
"regrid" is intended to be a program that will take a list of solutions to a crossword and attempt to piece together the original grid.

In general, this is type of problem does not have to have a unique solution. However, conventional professionally set crosswords will always have enough intersections to dictate a unique solution.

At the very least, we are assuming a conventional approach to numbering of spots - i.e. any adjacent run of live cells must be considered a spot, spots are labelled in the usual order.

Version 1 focused on possible points of intersection between words, so starting with first down entry recursively looked at possible intersections with grid as so far established. This meant not tackling the possible head-cell assignments in order.

Version 2, which hopefully will adapt better to blank solutions (i.e. lengths only), will instead work from the top-left corner of the grid across in rows, trying assignments for each cell. This way, head cells will be assigned in order.

The possibilities for each cell will be:
	- undetermined
	- blocked
	- live - headcell status undetermined
	- live but not headcell
	- live and head-cell (n)
With the latter two options, there is also a letter assignment if solutions given. Cells ahead of 'current' cell are only ever marked block or live - we only consider head-cell status on current cell.

As the procedure encounters each cell:
	if undetermined:
		Time-saver: if too close to boundary for next head-cell assignment, force block
		(Should only need to check right boundary - when starting new row we'll check whether we
		still have enough height for remaining vertical clues)
		POSIT assignment of live, consequently making it a head-cell.
		(For cell to be undetermined, it is not part of a word starting left or above)
		
	if block -> continue (no checking needed)
	if (already) live ->
		check previous cell in each direction (i.e. left and above)
		if previous is live,* not head-cell for that direction
		if next head-cell thereby legal, POSIT assigning it:
			for each direction it operates in, consequently assign all characters of
			the solution, including block in subsequent cell
		*(OR - for across - if next already committed as block. This will get checked very soon by positing,
		so not a big time-saver to put in separate pre-check)

Backing up after contradiction:
	undo all changes since last posit
	if last posit was making cell live, now it's a block (forced)
	if last posit was making live cell a head-cell, make it plain live (forced)...
		consequently for each direction of head-cell make next cell as block
		if this is both directions, then this is a lone cell -> contradiction

Whereas ver 1 used coordinates ( row , offset ) relative to head-cell 1, ver 2 will be absolute to grid. Note first live cell must be a head-cell

Two objects in model:
dimensions: posits? or handle that outside main search structure?
grid: 2D array of entries (special character for [unassigned], blocks, variable letters)
heads: list of assignments of head-cell coords
Could be one big dictionary, as keys are coordinate tuples for grid and integers for heads

Other data maintained:
current cell (coordinates)
next head-cell, and it's direction/s and length/s
flag set when next-head-cell is across and right boundary too close to fit it in

reason for each cells status?
	- either posit, forced by earlier posit, or forced by elimination
	- all come down to being consequent of a particular posit

Assigning grid content is where we detect contradictions (trying to reassign), whereas with our algorithm head-cell assignments should never be re-assignments.
"""

from model import *

class HeadClash( Exception ):
    pass
class OutOfSpace( Exception ):
    pass
class HitBorder( Exception ):
    pass
class Solution( Exception ):
    pass
SearchExceptions = ( Clash , Contradiction , HeadClash , OutOfSpace , HitBorder , Solution )

# coordinates will be (y,x) to inherit appropriate comparisons for < , >
dirs = 0,1
dirLabels = "Down:" , "Across:"
AtoZ = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
X = '='
verb = 2
ticks = 0
tickSpace = 1	# how often (in ticks) to wait for user prompt
def quit(*a):
    rprt(*a)
    raise Exception("User Quit")
def rprt(*a):
    it.report( )
    print it.grid.__dict__
def prIt(*a):
    it.report( )
def clScr(*a):
    print "\033[2J"
commands = {
    'p': prIt,
    'c': clScr,
    'r': rprt,
    'q': quit
    }
prCount = 0

def incVector( v , maxes , minim = 0 ):
    # assumes vector has dimension given by global dirs
    # look for least-significant coordinate not maxed out, increment it
    for d in dirs[ :: -1 ]:
	if v[ d ] >= maxes[ d ]:
	    v[ d ] = minim
	else:
	    v[ d ] += 1
	    break
    else:
	# all maxed out!
	return True  

def tick( force = False ):
    """
    Count passing iterations, give user chance to interact
    """
    global ticks, tickSpace, commands
    ticks += 1
    if force or ( tickSpace and not ( ticks % tickSpace ) ):
	doPrompt()
def doPrompt():
    global ticks, tickSpace, commands
    inp = raw_input( "%4d:" % ticks )
    if inp:
	# entering a number changes the frequency of stopping
	if inp.isdigit():
	    tickSpace = int( inp )
	else:
	    inpw = inp.split()
	    if inpw:
		if inpw[ 0 ] in commands:
		    commands[ inpw[ 0 ] ]( inpw )
		else:
		    #general purpose...
		    try:
			exec( inp , globals() )
		    except Exception as e:
			print "Error: %s" % e
		doPrompt() #keep taking commands until none entered


def prn( v , m ):
    # print message, only if verbosity >= v
    # all screen output should come through here (if only to keep track)
    global verb
    if verb >= v:
	#if isinstance( m , solSet ):
	    #return m.prGrid()
	print m

def readSolnsLines( L ):
    # from lines of text, read solutions and return as pair of lists of ( n, str ) pairs
    out = ( [ ] , [ ] )
    cur = -1
    for l in L:
	# stop when blank line reached
	if not l:
	    break
	# label - switch list
	if l in dirLabels:
	    cur = dirLabels.index( l )
	else:
	    if cur > -1:
		# read number, then take all alpha as word
		i , n = 0  , 0
		while i < len( l ) and l[ i ].isdigit():
		    n = 10 * n + int( l[ i ] )
		    i += 1
		s = ''.join( [ c for c in l[i:] if c.isalpha() ] )
		#if n and len(s):
		out[ cur ].append( ( n , s.upper() ) )
    return out

class solSet:
    def __init__( I , s ):
	# Initialise with list of lines or filename
	if isinstance( s , str ):
	    s = file( s ).read().splitlines()
	I.src = s
	I.sols = readSolnsLines( s )
	# do dictionary versions of the solution lists
	I.sold = map( dict , I.sols )
	prn( 2 , I.sold )
	I.lblsbyd = map( set , map ( dict.keys , I.sold ) )
	I.lbls = I.lblsbyd[ 0 ].union( I.lblsbyd[ 1 ] )
	I.dblbls = I.lblsbyd[ 0 ].intersection( I.lblsbyd[ 1 ] )
	#I.lbls = set( I.sold[ 0 ].keys() + I.sold[ 1 ].keys() )
	I.lrb = (0,1,1)
	I.lblR = range( 1 , max( I.lbls ) + 1 )
	if I.lbls != set( I.lblR ):
	    # Missing spot numbers - raise alarm
	    prn ( 0 , "Missing spot numbers - " )
	    prn ( 0 , sorted( set( I.lblR ) - I.lbls ) )
	# check for mismatched first letters
	for n in I.dblbls:
	    if I.sold[ 0 ][ n ][ 0 ] != I.sold[ 1 ][ n ][ 0 ]:
		prn( 0 , "FATAL: mismatched clues - " )
		prn( 0 , "%d: %s , %s" )
		I.ok = False
		return
	# heads array - covers whole range to I.maxN
	# and each entry is dictionary with keys being directions,
	#	(only has entries for directions it is a head cell for)
	# 	values solution + block character
	# headLens - each entry is array with a length for each direction
	# headLenMax - max of headLens for this and subsequent head-cells in final direction (Down)
	maxm = I.lblR[ -1 ] + 1 
	I.heads 	= maxm * [ None ]
	I.headLens 	= maxm * [ None ]
	I.headMaxLen	= maxm * [ None ]
	I.headTotLen	= maxm * [ None ] # total characters left in first direction (Across) clues
	I.totLen = 0  # total of lengths in first direction
	I.maxLen = 0  # maximum length in final direction (i.e. Down), == I.headLenMax[ 1 ]
	for n in I.lblR[ :: -1 ]:
	    dic = dict( [ ( d , I.sold[ d ][ n ] + X ) for d in dirs if n in I.sold[ d ] ] )
	    I.heads[ n ] = dic
	    I.headLens[ n ] = [ len( dic.get( d , " " ) ) - 1 for d in dirs ]
	    I.headMaxLen[ n ] = I.maxLen = max( ( I.maxLen , I.headLens[ n ][ 0 ] ) )
	    I.headTotLen[ n ] = I.totLen = I.totLen + I.headLens[ n ][ -1 ]
	#I.prep( )
	#I.search()
    def prep( I , *sizes ):
	I.sizes = sizes # By forcing a contradiction when we spread beyond a size limit, we stop
	I.siz0 = sizes[ 0 ] #  the search from wandering off into irrelevant territory.
	          # If we fully exhaust search space, we can try again with a more generous limit
	I.totCells = reduce( int.__mul__ , sizes ) + 1
	g = I.grid = model( {
		'sizes'      : sizes ,		# dimensions of grid
		'nextHeadN'  : 1 ,		# index of next head cell to assign
		'nextHead'   : I.heads[ 1 ] , 	#  ... and content ( dictionary { d : word } )
		'nextHeadLs' : I.headLens[ 1 ] , # length (or 0) of word in each direction
		'maxLenLeft' : I.maxLen ,	# maximum remaining length of final direction (Down) answers
		'totLenLeft' : I.totLen ,		# total remaining length of first direction (Across) answers
		'curCell'    : [ 1 for d in dirs ] , # current cell to consider
		#'blocks'     : 0 ,		# count of blocked cells
		'cellsLeft'  : I.totCells
		})
	g.curCell[ - 1 ] = 0
	# Set boundaries - a bit inefficient but it's a one-off
	cell = [ 0 for d in dirs ]
	while 1:
	    if min( cell ) == 0 or min( [ s - c for s,c in zip( sizes, cell ) ] ) < 0:
		g[ cell ] = X
	    # look for least-significant coordinate not maxed out, increment it
	    for d in dirs[ :: -1 ]:
		if cell[ d ] > sizes[ d ]:
		    cell[ d ] = 0
		else:
		    cell[ d ] += 1
		    break
	    else:
		# all maxed out!
		break
	return
    def search( I , *sizes ):
	I.prep( *sizes )
	I.nextCell( )
    def nextCell( I ):
	g = I.grid
	cell = g.curCell[ : ]
	if incVector( cell , I.sizes , 1 ):
	    # all cells done
	    if g.nextHeadN > I.lblR[ -1 ]:
		# all heads assigned - success!
		I.report()
		tick( True ) # force pause
		raise Solution
	    else:
		# shouldn't get to here!
		raise OutOfSpace
	g.cellsLeft -= 1
	if g.cellsLeft < g.totLenLeft:
	    I.report()
	    print g.cellsLeft , g.totLenLeft
	    tick( True )
	    raise OutOfSpace( dirLabels[ 1 ] )
	g.curCell = cell # new assignment so tracked
	#print cell[ 0 ] , g.maxLens , g.sizes[ 0 ]
	if cell[ 0 ] + g.maxLenLeft > g.sizes[ 0 ] + 1:
	    raise OutOfSpace( dirLabels[ 0 ] )
	old = g[ cell ]
	if old == X:
	    # easiest case - already committed as a block
	    I.nextCell()
	# for live or potentially live, check head cell possibilities
	# get coords of previous and next cell in each direction
	prv , nxt = [ [ [ cell[ e ] + i * ( e == d ) for e in dirs ] for d in dirs ] for i in -1, +1 ]
	prn( 3 , "%s %s %s" % ( prv , cell , nxt ) )
	okds = [ ] ; frcd = False ; okok = True
	for d in dirs:
	    # OK to be head cell this direction if previous cell is a block
	    if g[ prv[ d ] ] == X:
		gn = g[ nxt[ d ] ]
		# (and next not yet blocked)
		if gn != X:
		    #if prv[ d ] + g.nextHeadLs[ d ] <= sizes[ d ]:
		    okds.append( d )
		    # and if next cell already live, head cell forced
		    if gn:
			frcd = True
			# but don't break because we want to check all legalities
	# check legal in any required directions
	for d in g.nextHead:
	    if not d in okds:
		okok = False
		break
	if old:
		# Assigned live cell, see if it could / should be head cell
		if frcd:
		    # then force it if it goes
		    if okok:
			# still need to cut off in eligible directions it's not a head cell for
			for d in okds:
			    if not d in g.nextHead:
				g[ nxt[ d ] ] = X
			I.makeHead()
			I.nextCell()
		    # and call a clash if it doesn't
		    else:
			raise HeadClash( g.nextHeadN , cell )
	        else:
		    if okok:
			# speculate head
			g.spec()
			try:
			    # still need to cut off in eligible directions it's not a head cell for
			    for d in okds:
				if not d in g.nextHead:
				    g[ nxt[ d ] ] = X
				    g.blocks += 1
			    I.makeHead()
			    I.nextCell()
			except SearchExceptions as ex:
			    prn( 2 , ex )
			    tick()
			    # head cell lead to clash, so make it not
			    g.untry()
			    #make not head - commit block after in any direction with block before
			    for d in okds:
				g[ nxt[ d ] ] = X
			    I.nextCell()
		    else:
			# not head cell
			#make not head - commit block after in any direction with block before
			for d in okds:
			    g[ nxt[ d ] ] = X
			I.nextCell()
	else:
	    # unassigned cell - NB if live it MUST be head cell
	    if okok:
		# speculate live
		g.spec()
		try:
		    # still need to cut off in eligible directions it's not a head cell for
		    for d in okds:
			if not d in g.nextHead:
			    g[ nxt[ d ] ] = X
		    I.makeHead()
		    I.nextCell()
		except SearchExceptions as ex:
		    prn( 2 , ex )
		    tick()
		    g.untry()
		    # can't be head cell -> can't be live -> block
		    g[ cell ] = X
		    I.nextCell() 
	    else:
		# can't be head cell -> can't be live -> block
		g[ cell ] = X
		I.nextCell()
    def makeHead( I ):
	"""
	Make the current cell a head-cell
	"""
	global ticks
	g = I.grid
	cell = g.curCell
	n = g.nextHeadN
	head = g.nextHead
	# Put head-cell n at position z = (y,x)
	prn ( 2 , ( "%d " + "." * len( g.trys ) + "Head %d at %s" ) % ( ticks , n , cell ) )
	tick()
	prn( 3 , head )
	prn( 3 , g.__dict__ )
	# Now assign letters of word(s), including post- block
	for d in head:
	    if g.nextHeadLs[ d ] + cell[ d ] > I.sizes[ d ] + 1:
		raise HitBorder
	for d in head:
	    cell1 = cell[ : ]
	    for c in head[ d ]:
		g[ cell1 ] = c
		cell1[ d ] += 1
	n += 1
	g.nextHeadN = n
	if n < len( I.heads ):
	    g.nextHead = I.heads[ n ]
	    g.nextHeadLs = I.headLens[ n ]
	    g.maxLenLeft = I.headMaxLen[ n ]
	    g.totLenLeft = I.headTotLen[ n ]
	else:
	    g.nextHead = { 1: X }
	    g.nextHeadLs = [ 0 , 1 ]
	    g.maxLenLeft = 0
	    g.totLenLeft = 0
	I.report()
    def report( I , force=True ):
	global prCount
	prCount += 1
	if not force:
	    if prCount > 100 and ( prCount % 10 ):
		return
	    if prCount > 1000 and ( prCount % 100 ):
		return
	print "\033[2J\033[0;0H"
	for y in range( 1 , I.sizes[ 0 ] + 1 ):
		for x in range( 1 , I.sizes[ 1 ] + 1 ):
		    print I.grid.get( (y,x) , '.' ),
		print
	print
    # probably obsolete code from ver 1

	
fout = "test-out"
#testing
it = solSet("sol2")
print it.sold
#it.prGrid()
#print it.indd
#print it.xsd
go = lambda y=15,x=15:it.search(y,x)
go()
