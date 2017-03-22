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
	lbls = set( I.sold[ 0 ].keys() + I.sold[ 1 ].keys() )
	I.maxN = max( lbls )
	if lbls != set( range( 1 , I.maxN + 1 ) ):
	    # Missing spot numbers - raise alarm
	    print "Missing spot numbers - "
	    print set( range( 1 , I.maxN + 1 ) ) - lbls
	I.prep( )
	I.grid = { } # set of assignments of letter or block to coordinates, or values to other variables
	    # coords (y,x) with y > 0 are the actual grid, y=0,x>0 are head-cell placements
	    #  any spots with (y>=0) are assumed to be assign-once, so
	    #		- an attempt to reassign raises contradiction
	    #		- undoing an assignment merely means deleting
	    # spots with y < 0 can be reassigned, and need to be restored to old value on undo.
	#I.live = [ ] # set of coordinates of live cells in grid - i.e. where
		# a letter is assigned (from a word in one or other direction)
		# and for which there are still live possibilities for an intersecting word
		# in the other direction.
		# In fact we could have a more complex structure -
		#  dictionary with coords as keys into lists of possible intersections (initially
		#  taken from our earlier-prepared xsd lists)
		# Note that each 'pssible intersection' with a word already fixed on the grid
		# implies another quite specific head-cell assignment, easily computed.
		# If these are included in our list, then with each new assignment of a head-cell
		# it is easy to cull out other intersection possibilities using the same one
	I.acts = [ ] # list of grid assignments as ( y , x , v )
	I.trys = [ ] # list of speculated assignments (as index in I.acts)
	I.cont = [ ] # Contradictions as ( try , [ desc ] ) where try is last speculation at time of contradiction
	I.ok = True # == (not I.cont)
	
	# And let's go...
	
	I.setV( 'live' , [] ) # we need to be able to undo actions here
	
	# Next version - use -y grid coordinates for live intersection lists.
	# a coordinate has a list (possibly empty?) iff it's in exactly one word.
	# The list itself is just ( n , z ) tuples (the z's will all have one coordinate the same)
	
	# "Try" putting head-cell 1 at (1,0)
	I.tryH( 1 , (1,0) )

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
    def head( I , n ):
	# shorthand to fetch head-cell n if assigned
	return I.grid.get( (0,n) )
    def bust( I , desc = '?' ):
	# 'raise' contradiction
	I.ok = False
	i = I.trys[ -1 ]
	I.cont.append( ( i , desc ) )
	return i
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
		# Use natural ordering of pairs - that's why we put row first!
		# (Although if we broke it up we could demand 
		if ( m == n ) or ( m < n and z1 >= z ) or ( m > n and z1 <= z ):
		    return (m,z1)
	# Above could yet be quicker, assuming existing assignments consistent.
	# We should only need to look for largest m < n and smallest m > n

	
    def tryH( I , n , z ):
	# Put head-cell n at position z = (y,x)
	# check for ordering issues - look at other head-cell assignments
	mz1 = I.testH( n , z )
	if mz1:
		return I.bust( ( "Head sequence:" , (n,z) , mz1 ) )
	# Assign the head-cell
	I.trys.append( len( I.acts ) )
	I.setV( ( 0 , n ) , z )
	#heads = [ ( x0 , v ) for ( ( y0 , x0 ) , v ) in I.grid.items() if y0 == 0 and x0 > 0 ]
	#for ( m, z1 ) in heads:
	    #if ( m < n and z1 >= z ) or ( m > n and z1 <= z ):
		## contradiction by label-ordering rules
	# Now assign letters of word(s), including pre- and post- block
	for d in 0,1:
	    e = 1-d
	    z1 = list( z )
	    z1[ e ] -= 1 # backup one spot for block before
	    if n in I.sold[ d ]:
		top = d and not z1[ 0 ] # detect top of grid
		if top:
		    z1[ e ] += 1 # undo backing up and don't do lead block
		s = X * ( not top ) + I.sold[ d ][ n ] + X
		for c in s:
		    if I.setV( tuple( z1 ) , c ):
			return I.cont[ -1 ]
		    z1[ e ] += 1
		# intersection possibilities to add and subtract 
		# subtractions are any intersection cells we have just intersected
		# additions are a subet of all the original hypothetical intersectins of the word added
		live = I.grid[ 'live' ]
		newLive = dict( live ) # clone it
		#xsAdd = []
		#xsSub = []
		xs = I.xsd[ d ][ n ]
		#print d , n , xs
		for i,xl in enumerate( xs ):
		    z1[ e ] = z[ e ] + i  # set z1 to coords of cell
		    z1[ d ] = z[ d ] # should be unnecessary but best be safe
		    tz1 = tuple( z1 )
		    # if the cell was already listed with live intersections, it must've been an
		    # already assigned cell that we just intersected, so it will now have no further
		    # intersection possibilities - flag them for removal
		    if tz1 in live:
			del newLive[ tz1 ]
			#xsSub += live[ z1 ]
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
			if xsAdd:
			    newLive[ tz1 ] = xsAdd
		I.setV( 'live' , newLive )
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
		# Note - if we have text after already and X before,
		# the above will raise the contradiction
		## And vice-versa - safe to assume z2 on actual grid
		#if	z2 in I.grid and ( I.grid.get( z2 ) in AtoZ:
		    ## letter assigned to cell after, so ...
		    #if e or z1[ 0 ]:
			#pass
			## for now, no way to flag being a live cell other than assigning text.
	I.prGrid()
    def untry( I ):
	# back up (after contradiction)
	# Provision for storing the reasoning sequence leading to contradiction?
	targ = I.trys.pop() # where we're undoing back to on the acts list
	while len( I.acts ) > targ:
	    z , v , w = I.acts.pop()
	    if w:
		I.grid[ z ] = w
	    else:
		del I.grid[ z ]
	# eliminate the possibility that was tried? Handle elsewhere I think.
    def prGrid( I ):
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
	print

	
	
#testing
it = solSet("sol1")
print it.sold
#it.prGrid()
#print it.indd
#print it.xsd
