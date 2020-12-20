class Clash( Exception ):
    pass
class Contradiction ( Exception ):
    pass
class model(dict):
    """
    A dictionary used as a model when attempting to solve a puzzle. All assignments are tracked, and can be undone.
    Reassigning a value raises a clash.
    Some properties can also be tracked, but reassignment is OK for them.
    The 'acts' are tuples ( name , value , oldValue ) for properties and just ( key , value ) for values.
    None is reserved as value returned for unassigned keys, so shouldn't be one of the possible values.
    done: move tracked properties to being fields (means no name clash allowed) simplifying acts TODO: test it!
    """
    def __init__( I , tracked , autoUntry = False ):
	"""tracked is either -
	- a list of property names that are tracked, and reverted when backtracking, or
	- a dictionary of initial property values (keys are names) for tracked properties
	   (this initial assignment is not listed in acts)
	"""
	dict.__init__( I )
	if isinstance( tracked , dict ):
	    for nam in tracked:
		dict.__setattr__( I , nam , tracked[ nam ] )
	    I.__dict__['tracked'] = tracked.keys()
	else:
	    I.tracked = tracked
	I.acts = []
	I.trys = []
	I.auto = autoUntry
    #def __getattr__( I , nam ):
	#if nam in I.__dict__['tracked']:
	##if nam=='tracked' or nam in I.tracked:
	    #return dict.__getitem__( I , nam )
	#if nam in I.__dict__:
	    #return I.__dict__[ nam ]
    def __setattr__( I , nam , val ):
	old = I.__dict__.get( nam )
	# do nothing if new value same as old
	if old != val:
	    dict.__setattr__( I , nam , val )
	    if nam in I.tracked:
		#dict.__setitem__( I , nam , val )
		I.acts.append( ( nam , val , old , True ) )
		I.onChange( nam , val , old , True )
    def __missing__( I , key ):
	# Unassigned keys return None instead of raising Key Error
	pass
    # as a convenience when working with coordinates in lists, we
    # allow key to be a list and convert to tuple
    def __getitem__( I , key ):
	if isinstance( key , list ):
	    key = tuple( key )
	return dict.__getitem__( I , key )
    def __contains__( I , key ):
	if isinstance( key , list ):
	    key = tuple( key )
	return dict.__contains__( I , key )
    def __setitem__( I , key , val ):
	if isinstance( key , list ):
	    key = tuple( key )
	old = I.get( key )
	# do nothing if new value same as old
	if old != val:
	    if old == None:
		dict.__setitem__( I , key , val )
		I.acts.append( ( key , val , old ) )
		I.onChange( key , val , old , False )
	    else:
		if I.auto:
		    I.untry()
		raise Clash( key , old , val , len( I.acts ) )
    def spec( I ):
	# commence a speculation - marks where in the acts list something is being tried
	I.trys.append( len( I.acts ) )
    def untry( I ):
	if I.trys:
	    targ = I.trys.pop()
	    while len( I.acts ) > targ:
		I.unact( * I.acts.pop( ) )
	else:
	    raise Contradiction
    def unact( I , key , val , old, attr = False ):
	if attr:
	    dict.__setattr__( I , key, old )
	else:
	    if old == None:
		del I[ key ]
	    else:
		dict.__setitem__( I , key , old )
	I.onChange( key , val , old , attr , True )
    def onChange( I , key , val , old , attr=False , rev=False ):
	# for subclasses to override to respond to changes to data
	pass
