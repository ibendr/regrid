"""
"regrid" is intended to be a program that will take a list of solutions to a crossword and attempt to piece together the original grid.

In general, this is type of problem does not have to have a unique solution. However, conventional professionally set crosswords will always have enough intersections to dictate a unique solution.

At the very least, we are assuming a conventional approach to numbering of spots - i.e. any adjacent run of live cells must be considered a spot, spots are labelled in the usual order.

In order to optimise the search, we will focus on possible points of intersection between words. Two points are worth noting here:

(i) in theory, a program fulfilling our requirements could also be used to reconstruct a (blank) grid using only the lengths of the answers (useful e.g. to construct a grid from only a clue list), simply by using a notional set of solutions with all the same character. However, our approach is very much based on the assumption that our strongest hints are coming from the letters given, so it would [probably] be better to develop a different algorithm for that scenario.

(ii) our procedure very much assumes a fully connected grid. It is possible to have non-connected grids whose geometry still dictates a particular layout. Again, a different approach would be needed for that scenario.

We will use a coordinate system ( row , offset ) relative to head-cell 1, which we will define to be at ( 1 , 0 ). (A "head-cell" is a cell which is the head of at least one spot, and therefore is labelled with a number.) Head-cell 1 will always be the left-most live cell in the top row, so the first coordinate 'row' (vertical position or 'y') is absolute, while the second coordinate 'offset' (horizontal position or 'x') is _relative_ to head-cell 1, whose horizontal position is unknown to begin with.

Prior to the recursive part of the solution search, we do some preparatory analysis....

(i) make an index of occurrences of each letter in the DOWN solutions.
	i.e. for each letter from A to Z, a list of 'places' it occurs as ( n , i ) pairs,
	n = which down-spots (by label number) and i = position in word ( 0-based (?) )

(ii) for each ACROSS solution, for each position in the word, list all the possible intersections.
	Use index from (i) to get an initial list of candidates, and then cull according to some
	position rules. Basically an across clue can only intersect with Down solutions...
		
	- with a smaller label-number, intersecting at position i > 0
	- with immediately subsequent numbers at position i = 0
	    e.g. 8 Across can intersect 9 Down's first letter (i.e. 9 Down's head-cell is in 8 Across),
		and only if it does, it can intersect 10 Down's first letter at a later spot in 8 Across.

(iii) use table from (ii) to build its inverse table - i.e. available intersections for Down solutions

Then the recursive procedure -

We start with a 'grid' consisting of 1 Across and / or 1 Down.

For each positions in each word in the grid we maintain a list of possible intersections.
We have a list of the 'live' positions - not yet intersected but with a non-empty list of intersection possibilities.

Our speculative step is to choose a possible intersection and try implementing it by adding that word to the grid.
"""

dirLabels = "Across:" , "Down:"
AtoZ = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
X = '='
verb = 1
ticks = 0
prCount = 0

def prn( v , m ):
    # print message, only if verbosity >= v
    # all screen output should come through here (if only to keep track)
    global verb
    if verb >= v:
	if isinstance( m , solSet ):
	    return m.prGrid()
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
		s = ''.join( [ c for c in l if c.isalpha() ] )
		#if n and len(s):
		out[ cur ].append( ( n , s.upper() ) )
    return out

def readSolnsFile( fn ):
    # read solutions from named file
    return readSolnsLines( file( fn ).read().splitlines() )

class solSet:
    def __init__( I , s ):
	# Initialise with list of lines or filename
	if isinstance( s , str ):
	    s = file( s ).read().splitlines()
	I.src = s
	I.sols = readSolnsLines( s )
	I.sold = map( dict , I.sols )
	prn( 1 , I.sold )
	lbls = set( I.sold[ 0 ].keys() + I.sold[ 1 ].keys() )
	I.lrb = (0,1,1)
	I.maxN = max( lbls )
	if lbls != set( range( 1 , I.maxN + 1 ) ):
	    # Missing spot numbers - raise alarm
	    prn ( 0 , "Missing spot numbers - " )
	    prn ( 0 , set( range( 1 , I.maxN + 1 ) ) - lbls )
	I.prep( )
	prn( 3 , I.xsd )
	#I.search()

    def search( I , maxw=15 , maxh = 15 ):
	global ticks
	ticks = 0
	I.maxW = maxw # By forcing a contradiction when we spread beyond a size limit, we stop
	I.maxH = maxh #  the search from wandering off into irrelevant territory.
	          # If we fully exhaust search space, we can try again with a more generous limit
	I.grid = { } # set of assignments of letter or block to coordinates, or values to other variables
	    # coords (y,x) with y > 0 are the actual grid, y=0,x>0 are head-cell placements
	    #  any spots with (y>=0) are assumed to be assign-once, so
	    #		- an attempt to reassign raises contradiction
	    #		- undoing an assignment merely means deleting
	    # spots with y < 0 can be reassigned, and need to be restored to old value on undo.
	I.lives = [ ] # set of coordinates of live cells in grid - NOT auto-maintained,
		    # call updateLives() to make it accurate
		    # Details of live intersections for a cell (y,x) are stored at grid[ (-y,x) ]
	I.acts = [ ] # list of grid assignments as ( y , x , v )
	I.trys = [ ] # list of speculated assignments (as index in I.acts)
	I.cont = [ ] # Contradictions as ( try , [ desc ] ) where try is last speculation at time of contradiction
	I.ok = True # == (not I.cont)
	# And let's go...
	# "Try" putting head-cell 1 at (1,0)
	I.putH( 1 , (1,0) )
	while I.ok:
	    # check if we're done
	    if I.freeHeads():
		# if not - speculate!
		try:
		    I.spec()
		except KeyboardInterrupt:
		    break
	    while not I.ok:
		prn( 2 ,  I.cont.pop() )
		if I.trys:
		    # if there is at least one unforced move to undo
		    I.ok = True
		    I.untry()
		    ( a , ( z , h ) ) = I.trys.pop()
		    ntz = (-z[0],z[1])
		    live0 = I.grid[ ntz ]
		    prn( 4 ,  live0 )
		    I.setV( ntz , [ h1 for h1 in live0 if h1 != h ] )
		    I.updateLives()
		else:
		    return


    def prep( I ):
	# Make indeces of where letters A to Z occur in the solutions
	# This is not highly optimised but happens quickly anyway
	I.inds = [ [ ( a , [ (n,i) for (n,s) in I.sols[ d ] for (i,c) in enumerate(s) if c==a ] ) \
		    for a in AtoZ ] for d in 0,1 ]
	I.indd = map( dict , I.inds )
	I.xsd = { }, { }
	# build lists of intersection possibilities for each letter of each across word
	for (m,s) in I.sols[ 0 ]:
	    # from above : n < m
	    xs = [ [ (n,i) for (n,i) in I.indd[ 1 ][ c ] if n < m and i > 0 ] for c in s ]
	    # and add head-cells in the word (excluding it's own)
	    i , n = 1 , m + 1  # earliest possible spot for next head-cell, possible label
	    while i < len( s ) and n in I.sold[ 1 ]:
		# next head-cell is down - possibly from this word - list it for all matching spots
		c = I.sold[ 1 ][ n ][ 0 ] # first letter of down solution
		i2 = 0
		for j in range( i , len( s ) ):
		    if s[ j ]== c:
			xs[ j ].append( (n,0) )
			# mark first occurrence, to move i
			i2 = i2 or j + 1
		n += 1 # now check the next head-cell, but...
		i = i2 or len( s ) # ...if no occurrence we're done
	    I.xsd[ 0 ][ m ] = xs	
	# Tabulate possible intersections for down solutions by referring to the one we did for across
	# But use the letter index as starting point.
	for (n,t) in I.sols[ 1 ]:
	    I.xsd[ 1 ][ n ] = [ [ (m,j) for (m,j) in I.indd[ 0 ][ c ] \
			if (n,i) in I.xsd[ 0 ][ m ][ j ] ] for i,c in enumerate( t ) ]
    def spec( I ):
	# try something!
	# list coords with non-empty lists of intersections
	#lives = sorted( [ ( I.grid[ z ] , (-z[0],z[1]) , z ) for z in I.grid if z[0] < 0 and I.grid[ z ] ] )
	#if not lives:
	    #print( "no live intersections left" )
	    #I.untry
	prn( 2 , I.livesz )
	sc , z , ntz = I.lives[ 0 ]
	n , z1 = I.grid[ ntz ][ 0 ]
	I.trys.append( ( len( I.acts ) , ( z , ( n , z1 ) ) ) )
	I.putH( n , z1 )
    def head( I , n ):
	# shorthand to fetch head-cell n if assigned
	return I.grid.get( (0,n) )
    def heads( I ):
	return [ ( n , I.grid[ (0,n) ] ) for n in range( 1 , I.maxN + 1 ) if (0,n) in I.grid ]
    def freeHeads( I ):
	return [ n for n in range( 1 , I.maxN + 1 ) if not (0,n) in I.grid ]
    def nextFreeHead( I ):
	# lowest unassigned head-cell number, or None if all done
	for n in range( 1 , I.maxN + 1 ):
	    if not (0,n) in I.grid:
		return n
    def done( I ):
	return not I.nextFreeHead( )
    def bust( I , desc = '?' ):
	global verb
	# 'raise' contradiction
	I.ok = False
	i = I.trys and I.trys[ -1 ]
	I.cont.append( ( i , desc ) )
	prn( 2 , I ) # calls I.prGrid() - hopefully
	prn( 2 , "[ %s ] %s" % ( i,desc ) )
	return i
    def isBlok( I , z ):
	return z[ 0 ] == 0 or ( z in I.grid and I.grid[ z ] == X )
    def setBlok( I , z ):
	if z[ 0 ]:
	    I.setV( z , X )
    def setNotHead( I , (y,x) ):
	if   I.isBlok( (y-1,x) ):
	    I.setBlok( (y+1,x) )
	if   I.isBlok( (y,x-1) ):
	    I.setBlok( (y,x+1) )
    def setNotHeadSweep( I , n ):
	# called when heads n, n+1 both assigned, to 'sweep' through
	# any live cells in between, calling setNotHead
	z0 = I.head( n )
	z1 = I.head( n + 1)
	for z in I.grid.keys():
	    if z0 < z < z1 and I.grid[ z ] != X:
		I.setNotHead( z )
    def clearHead( I , n ):
	# remove any intersection possibilities assigning head-cell n
	#  ( or conflicting with it by ordering )
	z = I.head( n )
	for z2 in I.grid:
	    if z2[ 0 ] < 0:
		live = I.grid[ z2 ]
		#print live
		out = [ h2 for h2 in live if I.nzmz1( (n,z) , h2 ) ]
		if out:
		    rem = sorted( set( live ) - set( out ) )
		    I.setV( z2 , rem )
		
    def setV( I , z , v ):
	# Set the value of a grid-cell or variable - see notes about I.grid dictionary above
	# No action required if that value already (keeps action pile neater too)
	w = I.grid.get( z ) # will be None if not z in I.grid
	#print z,v,w
	if w != v:
	    # Assign unless it's a grid spot already assigned otherwise
	    if w == None or isinstance( z , str ) or z[ 0 ] < 0:
		# new grid spots or reassignable variables
		I.acts.append( ( z , v , w ) )
		I.grid[ z ] = v
		if v==None:
		    del I.grid[ z ]
	    else:
		return I.bust( ( "reassign" , z , v , w ) )

    def testH( I , n , z ):
	# Test the position z for head-cell n for legality purely by
	# the sequencing requirement (and not being already assigned)
	# (Consistent with previous assignment still illegal. We use this
	# test to cull out candidates for subsequent assignments, so
	# we cull ones we've already done as well as ones that clash.)
	for m in range( 1 , I.maxN + 1 ):
	    z1 = I.grid.get( (0,m) )
	    if z1:
		## Use natural ordering of pairs - that's why we put row first!
		## (Although if we broke it up we could demand 
		#if ( m == n ) or ( m < n and z1 >= z ) or ( m > n and z1 <= z ):
		if I.nzmz1( (n,z) , (m,z1) ):
		    return (m,z1)
	# Above could yet be quicker, assuming existing assignments consistent.
	# We should only need to look for largest m < n and smallest m > n
    #def nzmz1( I , *arg ):
	#print arg
    def nzmz1( I , (n,(y,x)) , (m,(v,u)) ):
	return ( m == n ) or \
	    ( m < n and ( v > y or ( v == y and u > x + n - m ) ) ) or \
	    ( m > n and ( v < y or ( v == y and u < x - n + m ) ) )
    def putH( I , n , z ):
	global verb , ticks
	# Put head-cell n at position z = (y,x)
	ticks += 1
	prn ( 1 , ( "%d" + "." * len( I.trys ) + "Head %d at %s" ) % ( ticks , n , z ) )
	# check for ordering issues - look at other head-cell assignments
	mz1 = I.testH( n , z )
	## Note if we're doing the lowest-numbered head still free
	#nfh = ( n == I.nextFreeHead() )
	# Assign the head-cell
	I.setV( ( 0 , n ) , z )
	#I.trys.append( len( I.acts ) - 1 )
	if mz1:
		return I.bust( ( "Head sequence:" , (n,z) , mz1 ) )
	# Now assign letters of word(s), including pre- and post- block
	for d in 0,1:
	    e = 1-d
	    z1 = list( z )
	    z1[ e ] -= 1 # backup one spot for block before
	    #print I.sold[ d ]
	    if n in I.sold[ d ]:
		top = d and not z1[ 0 ] # detect top of grid
		if top:
		    z1[ e ] += 1 # undo backing up and don't do lead block
		s = X * ( not top ) + I.sold[ d ][ n ] + X
		prn( 3 , s )
		for c in s:
		    if I.setV( tuple( z1 ) , c ):
			return I.cont[ -1 ]
		    z1[ e ] += 1
		# intersection possibilities to add and subtract 
		xs = I.xsd[ d ][ n ]
		for i,xl in enumerate( xs ):
		    z1[ e ] = z[ e ] + i  # set z1 to coords of cell
		    z1[ d ] = z[ d ] # should be unnecessary but best be safe
		    tz1 = ( - z1[ 0 ], z1[ 1 ] ) # how we address the live-intersection lists
		    # if the cell was already listed with live intersections, it must've been an
		    # already assigned cell that we just intersected, so it will now have no further
		    # intersection possibilities - flag them for removal
		    if tz1 in I.grid:
			I.setV( tz1 , None )
		    else:
			xsAdd = [ ]
			for (m,j) in xl:
			    # For each possible intersection, compute where it would place head-cell
			    z2 = z1[ : ]
			    z2[ d ] = z[ d ] - j
			    #print ((m,j),z2),
			    # and list it if that is a legal assignment
			    if not I.testH( m , tuple( z2 ) ):
				xsAdd.append( ( m , tuple( z2 ) ) )
			#if xsAdd: # add even if empty - it marks being in single word
			I.setV( tz1 , xsAdd )
		#I.setV( 'live' , newLive )
	    else:
		# no word in this direction might imply block
		#   if there's a block before, or top of grid,
		#   then can't be text cell after
		z2 = list( z )
		z2[ e ] += 1 # cell after
		z2 = tuple( z2 )
		if	( e == 0 and z1[ 0 ] == 0 ) or \
			( I.grid.get( tuple( z1 ) ) == X ):
			# move to cell after and place block
		    I.setV( z2 , X )
	# At this point, the word is safely into the grid without clashes - if there's
	#  a contradiction already implied, it's via impossibility of subsequent assignments.
	# In other words, if this was the last word to go in, we're done and don't need these further checks.
	if I.ok and I.done():
	    prn( 1 , I )
	    #if verb:
		#I.prGrid( True )
	    return
	# see if we've got consecutive heads assigned, in which case we may
	# have cells that now can't be head-cells, which may in turn force some block allocations
	prn( 3 , I.grid )
	if I.head( n-1 ):
	    I.setNotHeadSweep( n-1 )
	if I.head( n+1 ):
	    I.setNotHeadSweep( n )
	# clear out any other live intersections with same head (even if consistent)
	I.clearHead( n )
	I.updateLives( )
	prn( 2 , I )
    def spotScore( I , n , (y,x) ):
	# A measure of the maximum expansion of boundaries caused by a word placement
	l , r , b = I.lrb
	l1 = x
	r1 = x + ( ( n in I.sold[ 0 ] ) and len( I.sold[ 0 ][ n ] ) )
	b1 = y + ( ( n in I.sold[ 1 ] ) and len( I.sold[ 1 ][ n ] ) )
	out = ( max( 0 , l - l1 , r1 - r , b1 - b ) , y , n , x )
	prn( 4 , out )
	return out
    def updateLrb( I ):
	# Update left, right, bottom bounds of grid.
	# Low values inclusive, high exclusive
	#   i.e. x values for text-cells are range( l , r ) being [ l , ... , r-1 ]
	zs = [ z for z in I.grid if z[ 0 ] > 0 and I.grid[ z ] in AtoZ ]
	if zs:
	    l = min( [ x for (y,x) in zs ] )
	    r = max( [ x for (y,x) in zs ] ) + 1
	    b = max( [ y for (y,x) in zs ] ) + 1
	    I.lrb = l,r,b
	else:
	    I.lrb = 0,1,1
	prn( 2 , I.lrb )
	if ( r - l ) > I.maxW or ( b - 1 ) > I.maxH:
	    I.bust( "Hit grid boundary L: %d , R: %d , B: %d " % I.lrb )
    def updateLives( I ):
	I.updateLrb( )
	I.lives = sorted( [ ( I.spotScore( *I.grid[ z ][ 0 ] ), (-z[0],z[1]) , z ) \
		    for z in I.grid if z[0] < 0 and I.grid[ z ] ] )
	I.livesz = [ z for ( sc,z,nz ) in I.lives ]
	if not I.lives:
	    rem = len( I.freeHeads() )
	    if not rem:
		raise
	    msg = "no more live intersections - %d words remain" % rem
	    prn( 1 , msg )
	    I.bust( msg )
    def untry( I ):
	# back up (after contradiction)
	# Provision for storing the reasoning sequence leading to contradiction?
	targ = I.trys[ -1 ][ 0 ] # where we're undoing back to on the acts list
	while len( I.acts ) > targ:
	    z , v , w = I.acts.pop()
	    if w == None:
		del I.grid[ z ]
	    else:
		I.grid[ z ] = w
	# eliminate the possibility that was tried? Handle elsewhere I think.
    def prGrid( I , force=False ):
	global prCount
	prCount += 1
	if not force:
	    if prCount > 100 and ( prCount % 10 ):
		return
	    if prCount > 1000 and ( prCount % 100 ):
		return
	# Recalculate minimum & maximum x coord and max y
	zs = [ z for z in I.grid.keys() if isinstance( z , tuple ) ]
	xs = [ x for (y,x) in zs if y > 0 ]
	if xs:
	    l , r = min( xs ) , max( xs )
	    b = max( [ y for (y,x) in zs ] )
	    for y in range( 0 , b + 1 ):
		print
		for x in range( l , r + 1 ):
		    print I.grid.get( (y,x) , '.' ),
	I.lrb = l , r , b
	print

	
	
#testing
it = solSet("sol2")
print it.sold
#it.prGrid()
#print it.indd
#print it.xsd
go = lambda *x:it.search(*x)
