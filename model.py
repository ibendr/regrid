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
	    I.tracked = tracked.keys()
	else:
	    I.tracked = tracked
	I.acts = []
	I.trys = []
	I.auto = autoUntry
    def __getattr__( I , nam ):
	if nam in I.__dict__:
	    return I.__dict__[ nam ]
    def __setattr__( I , nam , val ):
	old = I.__getattr__( nam )
	# do nothing if new value same as old
	if old != val:
	    dict.__setattr__( I , nam , val )
	    if nam in I.tracked:
		I.acts.append( ( nam , val , old ) )
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
		I.acts.append( ( key , val ) )
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
    def unact( I , nam , val , old = None ):
	if old:
	    dict.__setattr__( I , nam , old )
	else:
	    del I[ nam ]
