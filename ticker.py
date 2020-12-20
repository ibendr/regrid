ticks = 0
tickSpace = 1	# how often (in ticks) to wait for user prompt
promptPos = "\033[18;1H"

def tick( force = False ):
    """
    Count passing iterations, give user chance to interact
    """
    global ticks, tickSpace, commands
    ticks += 1
    if force or ( tickSpace and not ( ticks % tickSpace ) ):
	print promptPos ,
	#doPrompt()
	exec( prmptCode , NS )
def doPrompt():
    #global commands
    inp = raw_input( "%4d:" % ticker.ticks )
    if inp:
	# entering a number changes the frequency of stopping
	if inp.isdigit():
	    ticker.tickSpace = int( inp )
	else:
	    inpw = inp.split()
	    if inpw:
		if inpw[ 0 ] in commands:
		    commands[ inpw[ 0 ] ]( inpw )
		else:
		    #general purpose...
		    try:
			exec( inp ) #, NS )
		    except Exception as e:
			print "Error: %s" % e
		exec( ticker.prmptCode , ticker.NS ) #keep taking commands until none entered
prmptCode = doPrompt.__code__
