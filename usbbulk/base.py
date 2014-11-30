
class BaseBulkUSB:
    """
    abstract base class for file-like bulk-USB endpoint wrappers.
    Bulk USB is one of USB's four transfer modes
    and the only one that makes sense as a filestream.
    
    The mapping isn't perfect. Short reads are likely to crash
    and USB devices can be "reset" which isn't 100% the same as reopened.
    
    implementations should support the unimplemented methods below,
     and 
    """
    def __init__(self, vendor, product, endpoint=1):
        """
        endpoint is a 4-bit integer identifying which particular piece of the device this bulk port talks to
        timeout is in milliseconds
        """
        if not (0 <= endpoint < (1<<4)):
            raise ValueError("USB endpoints are only 4 bits long")
        if endpoint == 0:
            raise ValueError("Control endpoints are never bulk endpoints.") #TODO choose a better exception class
        
        self._timeout = None
        
        self.device = None #??
        self._endpoint = endpoint #endpoint address (a 4-bit integer)
    
    def read(self, len):
        raise NotImplementedError
    
    def write(self, data):
        raise NotImplementedError
    
    def close(self):
        raise NotImplementedError
    
    def device(self):
        "return device *address* (a 8-bit integer)"
        raise NotImplementedError
    
    @property
    def endpoint(self):
        "read-only endpoint address (a 4-bit integer)"
        "this is *not* the same as bEndpointAddress, which is an 8 bit integer but really only uses one of those 4 extra bits to declare the direction, which is really just overengineering"
        return self._endpoint
    
    def setTimeout(self, timeout):
        """
        a timeout of None means infinity
        """
        if timeout == 0:
            # be defensively consistent with bsd_ugen_bulk
            timeout = None
        
        if timeout is not None:
            if not (0 < timeout < 1<<32):
                raise ValueError("Timeout must be an unsigned 32-bit integer if given.")
        
        self._timeout = timeout
    
    timeout = property(lambda self: self._timeout, lambda self, value: self.setTimeout(value))
