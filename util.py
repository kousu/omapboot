def readinto_io(self, target, chunksize=4096):
    """
    A missing idiom.
    
    As with all I/O, you will need to tune chunksize to your use case:
     too small is going to be dominated by overhead
     too large is going to be dominated by blocking to wait for buffering to happen
    
    Inspired by python-requests's request.iter_content()
    """
    while True:
        chunk = self.read(chunksize)
        if not chunk: break
        amt = target.write(chunk)
        #print("wrote",amt,"bytes") #DEBUG
# TODO: attach this to a suitably high-level class in the IO hierarchy

