"""
"regrid" is intended to be a program that will take a list of solutions to a crossword and attempt to piece together the original grid.

In general, this is type of problem does not have to have a unique solution. However, conventional professionally set crosswords will always have enough intersections to dictate a unique solution.

At the very least, we are assuming a conventional approach to numbering of spots - i.e. any adjacent run of live cells must be considered a spot, spots are labelled in the usual order.

Version 1 focused on possible points of intersection between words, so starting with first down entry recursively looked at possible intersections with grid as so far established. This meant not tackling the possible head-cell assignments in order.

Version 2, which hopefully will adapt better to blank solutions (i.e. lengths only), will instead work from the top-left corner of the grid across in rows, trying assignments for each cell. This way, head cells will be assigned in order.

TODO:
	- backtracking after solution (if we want to find more)
	- option to enforce rotational symmetry
	- fasterise

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
		consequently for each direction of head-cell make next cell a block
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
import ticker
from ticker import tick

ticker.NS = globals( )

class HeadClash( Exception ):
    pass
class OutOfSpace( Exception ):
    pass
class HitBorder( Exception ):
    pass
class Solution( Exception ):
    pass
SearchExceptions = ( Clash , HeadClash , OutOfSpace , HitBorder , Solution )
class UserQuit( Exception ):
    pass

def quit(*a):
    #rprt(*a)
    raise UserQuit
def rprt(*a):
    #it.report( )
    print s.__dict__
def prIt(*a):
    for l in s.export( ):
	print l
    pass
def clScr(*a):
    print "\033[2J"
def export(*a):
    fn = raw_input ('Export to file-name:')
    if not fn:
	# blank filename - abort
	return
    if fn == '.':
	fn = it.srcFile
    #make new file only if filename preceded by '!'
    nw = ( fn[ 0 ] == '!' )
    f = file( fn[ nw : ] , "aw"[ nw ] )
    if not nw:
	f.write( '\n' )
    for l in s.export( ):
	f.write( l + '\n' )
    f.close( )

ticks = 0
tickSpace = 1	# how often (in ticks) to wait for user prompt
commands = {
    'p': prIt,
    'c': clScr,
    'r': rprt,
    'x': export,
    'q': quit
    }

# coordinates will be (y,x) to inherit appropriate comparisons for < , >
dirs = 0,1
dirLabels = "Down:" , "Across:"
AtoZ = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
X = '='
it = None
s = None
verb = 2

class gridSearch( model ):
    def __init__( I , sol , * sizes ):
	"""sol is the solSet (solutions set) that we will be modelling for)"""
	initials = {
	    'sols'	: sol ,
	    'sizes'	: sizes ,		# dimensions of grid
	    #'totCells'	: reduce( int.__mul__ , sizes ) + 1 ,
	    'siz0'	: sizes[ 0 ] ,		# shorthand
	    'nextHeadN'	: 1 ,			# index of next head cell to assign
	    'nextHead'	: sol.heads[ 1 ] , 	#  ... and content ( dictionary { d : word } )
	    'nextHeadLs': sol.headLens[ 1 ] ,	# length (or 0) of word in each direction
	    'maxLenLeft': sol.maxLen ,		# maximum remaining length of final direction (Down) answers
	    'curCell'	: [ 1 for d in dirs ] , # current cell to consider (starts one back)
	    'monitor'	: [ 1 , 1 ]		# where to display on screen (or None not to)
	    }
	model.__init__( I , initials )
	# Set boundaries - a bit inefficient but it's a one-off
	cell = [ 0 for d in dirs ]
	sizesPlus = [ size + 1 for size in sizes ]
	while 1:
	    if not min( cell ) or not min( [ s - c for s,c in zip( sizesPlus, cell ) ] ):
		I[ cell ] = X
	    if incVector( cell , sizesPlus ):
		break
	I.doMonitor( )
	#I.doCell( )
    def onChange( I , *arg ):
	if I.monitor:
	    I.doMonitor( *arg )
    def doMonitor( I , key = None , val = None , old = None , attr = False , label = False ):
	if key:
	    if attr:
		if key in I.tracked:
		    i = I.tracked.index( key )
		    #y = I.monitor[ 0 ] + I.sizes[ 0 ] + 1 + ( i / 3 )
		    #x = I.monitor[ 1 ] + I.sizes[ 0 ] + 28 + ( i % 3 )
		    y = I.monitor[ 0 ] + 3 + i
		    x = I.monitor[ 1 ] + 2 * I.sizes[ 1 ] + 8
		    old, val = str( old or '' ), str( val )
		    spc = max( len ( old ) - len( val ) , 0 ) * ' '
		    if label:
			print ( "\033[%d;%dH%-10s : %s%s" % ( y , x , key , val , spc ) )
		    else:
			print ( "\033[%d;%dH%s%s" 	  % ( y , x + 13  , val , spc ) )
	    else:
	    #if isinstance( key , tuple ):
		y = key[ 0 ] + I.monitor[ 0 ]
		x = 2 * key[ 1 ] + I.monitor[ 1 ]
		#v = I.get( key , " " )
		print ( "\033[%d;%dH%s" % ( y , x , val ) )
	else:
	    # used for refreshing entire display
	    print "\033[2J"
	    for key in I.keys( ):
		I.doMonitor( key , I[ key ] )
	    for nam in I.tracked:
		I.doMonitor( nam , I.__dict__[ nam ] , None , True , True )
    def nextCell( I ):
	cell = I.curCell[ : ]
	if incVector( cell , I.sizes , 1 ):
	    # all cells done
	    if I.nextHeadN > I.sols.lblR[ -1 ]:
		# all heads assigned - success!
		#I.report()
		tick( True ) # force pause
		raise Solution
	    else:
		# shouldn't get to here!
		raise OutOfSpace
	I.curCell = cell # new assignment so tracking works
	if cell[ 0 ] + I.maxLenLeft > I.sizes[ 0 ] + 1:
	    raise OutOfSpace( dirLabels[ 0 ] )
    def doCell( I ):
	# This is now only recursive when it has to be - i.e. to generate a new layer of try / except
	# work out what positing if any we need to do. Any forced moves we just go ahead and do,
	# but if it's time to posit we put it in that variable and it's all handled in one place
	posit = None
	while not posit:
	    cell = I.curCell
	    old = I[ cell ]
	    # if already committed as a block we have nothing to do
	    if old != X:
		# for live or potentially live, check head cell possibilities
		# get coords of previous and next cell in each direction
		prv , nxt = [ [ [ cell[ e ] + i * ( e == d ) for e in dirs ] for d in dirs ] for i in -1, +1 ]
		okds = [ ] ; frcd = False ; okok = True
		for d in dirs:
		    # OK to be head cell this direction if previous cell is a block
		    if I[ prv[ d ] ] == X:
			nx = I[ nxt[ d ] ]
			# (and next not yet blocked)
			if nx != X:
			    okds.append( d )
			    # and if next cell already live, head cell forced
			    if nx:
				frcd = True
				# but don't break because we want to check all legalities
		# check legal in any required directions
		for d in I.nextHead:
		    if not d in okds:
			okok = False
			break
		if old:
		    # Assigned live cell, see if it could / should be head cell
		    if frcd:
			# if forced, then force it ... if it goes
			if okok:
			    ## still need to cut off in eligible directions it's not a head cell for
			    #for d in okds:
				#if not d in I.nextHead:
				    #I[ nxt[ d ] ] = X
			    I.makeHead( okds , nxt )
			# and call a clash if it doesn't
			else:
			    raise HeadClash( I.nextHeadN , cell )
		    else:
			# live - posit a head if we can
			if okok:
			    # speculate head
			    posit = I.makeHead
			else:
			    # can't be head cell
			    I.makeNotHead( okds , nxt )
		else:
		    # unassigned cell - NB if we make it live it MUST be head cell
		    if okok:
			posit = I.makeLiveHead
		    else:
			I[ cell ] = X
	    if not posit:
		I.nextCell( )
	#exiting loop - we must have a posit to do
	I.spec()
	try:
	    posit( okds , nxt )
	    I.nextCell( )
	    if I.doCell():
		raise UserQuit
	except SearchExceptions as ex:
	    #prn( 2 , ex )
	    tick()
	    I.untry()
	    posit.undo( I , okds , nxt )
	    I.nextCell( )
	    if I.doCell():
		raise UserQuit
	except KeyboardInterrupt:
	    tick( True )
	    I.untry()
	    # By undoing effects of last try but NOT doing opposite posit
	    # or advancing cell we will end up going back to last try and
	    # starting it again
	    if I.doCell():
		raise UserQuit
	except UserQuit:
	    return True
    def makeNotHead( I , okds , nxt ):
	for d in okds:
	    I[ nxt[ d ] ] = X	
    def makeBlock( I , okds , nxt ):
	I[ I.curCell ] = X
    def makeHead( I , okds , nxt ):
	# Make the current cell a head-cell
	# still need to cut off in eligible directions it's not a head cell for
	for d in okds:
	    if not d in I.nextHead:
		I[ nxt[ d ] ] = X
	cell = I.curCell
	n = I.nextHeadN
	head = I.nextHead
	#prn ( 2 , ( "%d " + "." * len( I.trys ) + "Head %d at %s" ) % ( ticks , n , cell ) )
	tick()
	prn( 3 , head )
	# Now assign letters of word(s), including post- block
	for d in head:
	    if I.nextHeadLs[ d ] + cell[ d ] > I.sizes[ d ] + 1:
		raise HitBorder
	for d in head:
	    cell1 = cell[ : ]
	    for c in head[ d ]:
		I[ cell1 ] = c
		cell1[ d ] += 1
	n += 1
	I.nextHeadN = n
	sol = I.sols
	if n < len( sol.heads ):
	    I.nextHead = sol.heads[ n ]
	    I.nextHeadLs = sol.headLens[ n ]
	    I.maxLenLeft = sol.headMaxLen[ n ]
	else:   #TODO: announce solution here
	    #This is where all words have been placed in the grid - NOTE
	    # SOLUTION? For now, letting it run to check on
	    # remaining cells, BUT they should all be OK. Any as
	    # unallocated need to be made blocks, but that shouldn't
	    # create any issues. Word just placed can't have created
	    # new chunks of adjacent live cells, because we already
	    # marked as blocks ones under live non-head-cells.
	    I.nextHead = { 1: X }
	    I.nextHeadLs = [ 0 , 1 ]
	    I.maxLenLeft = 0
	#I.report()
    def makeLiveHead( I , *a ):
	return I.makeHead( *a )
    makeLiveHead.undo = makeBlock
    makeHead.undo = makeNotHead
    def export( I , term='|' ):
	return [ ''.join( [ s[ ( y + 1 , x + 1 ) ] for x in range( I.sizes[ 1 ] ) ] ) + term for y in range( I.sizes[ 0 ] ) ]

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

def prn( v , m ):
    # print message, only if verbosity >= v
    # all screen output should come through here (if only to keep track)
    global verb
    if verb >= v:
	#if isinstance( m , solSet ):
	    #return m.prGrid()
	print m

def readInt( s , i=0 , skip=False ):
    """
    Read leading integer from string s[ i: ]
    - not fussy about rest ( like int() is )
    - returns ( answer , j ) where j is index of next character in string
    - use skip=True to skip leading non-digits
    """
    n = 0
    if skip:
	while i < len( s ) and not s[ i ].isdigit():
	    i += 1
    while i < len( s ) and s[ i ].isdigit():
	n = 10 * n + int( s[ i ] )
	i += 1
    return ( n , i )
    
def readSolnsLines( L , allOneChar = None ):
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
		n , i = readInt( l )
		# if allOneChar, look out for this being questions file,
		# so ignore question and pluck enum from end
		if allOneChar:
		    #print "->%s<-" % l
		    if l[ -1 ] == ')' and '(' in l:
			while '(' in l[ i : ]: #get last
			    i = l.index( '(' , i ) + 1
			#break into seperate numbers and add up
			ln = 0
			while i < len( l ):
			    prn( 5 , ( n , ln , l[ i: ] ) )
			    ln1 , i = readInt( l , i , True )
			    ln += ln1
			if ln:
			    prn( 3 , ( n , l[ -10: ] , ln ) )
			    out[ cur ].append( ( n , ln * allOneChar ) )
			    continue
		s = ''.join( [ c for c in l[i:] if c.isalpha() ] )
		if n and s:
			if allOneChar:
				s = len( s ) * allOneChar
			else:
				s = s.upper()
			out[ cur ].append( ( n , s ) )
    return out

class solSet:
    def __init__( I , s , allOneChar = None ):
	# Initialise with list of lines or filename
	I.srcFile = None
	if isinstance( s , str ):
	    I.srcFile = s
	    s = file( s ).read().splitlines()
	I.src = s
	I.sols = readSolnsLines( s , allOneChar )
	prn( 3 , I.sols )
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
	I.maxLen = 0  # maximum length in final direction (i.e. Down), == I.headLenMax[ 1 ]
	for n in I.lblR[ :: -1 ]:
	    dic = dict( [ ( d , I.sold[ d ][ n ] + X ) for d in dirs if n in I.sold[ d ] ] )
	    I.heads[ n ] = dic
	    I.headLens[ n ] = [ len( dic.get( d , " " ) ) - 1 for d in dirs ]
	    I.headMaxLen[ n ] = I.maxLen = max( ( I.maxLen , I.headLens[ n ][ 0 ] ) )
	    #I.headTotLen[ n ] = I.totLen = I.totLen + I.headLens[ n ][ -1 ]
	#I.prep( )
	#I.search()

	
fout = "test-out"
#testing
def go (y=15,x=15,allOneChar=None,fin="sol2"):
	global it,s;
	it = solSet(fin,allOneChar)
	print it.sold
	s = gridSearch(it,y,x)
	s.doCell()
verb=0
def go1():
    go (13,13,'o',"01AUG8.new")
#it.prGrid()
#print it.indd
#print it.xsd
#go1()
def g(f,s=13):
    go(s,s,'o',f)
