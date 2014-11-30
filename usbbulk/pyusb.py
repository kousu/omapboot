

try:
    import usb.core #old pyusbs are incompatible and do not have this module
    # TODO: check version explicitly. 
    
    from .base import *

    class BulkUSB(BaseBulkUSB):
        """
        pyusb is essentially just a wrapper around libusb
        it has one other 'backend' but its API is sooo close.
        """
        
        def __init__(self, vendor, product, endpoint=1):
            """
            
            timeout is in milliseconds; if it's 
            the
            """
            super().__init__(vendor, product, endpoint)
            
            self._dev = usb.core.find(idVendor=vendor, idProduct=product)
            if self._dev is None:
                raise OSError("Unable to find USB Device %04x:%04x" % (vendor, product))
            
            #XXX does this need to "claim" the "interface"? it seems to work without doing that...
            # the pyusb docs suggest that doing this is the correct first step
            # this isn't quite claiming, but maybe it's.. the same?
            self._dev.set_configuration()
            
            # Device.{read,write}() implicitly calls libusb_claim_interface as needed.
            
            
        def read(self, len):
            """
            returns a bytes object
            """
            # we need to turn bit 7 of the bEndpointAddress on to indicate 'IN'
            # see http://www.beyondlogic.org/usbnutshell/usb5.shtml#EndpointDescriptors for a reference
            return self._dev.read(0b10000000 | self.endpoint,
                                  len, timeout=self.timeout).tobytes()
            #pyusb works in Array objects. Which are totally the future,
            # but are inconsistent with bsd_ugen_bulk
            # and are more obscure than common python.
        
        def write(self, data):
            """
            data should be a bytes object
            """
            return self._dev.write(self.endpoint, data, timeout=self.timeout) #careful: pyusb returns array objects, but because of the magic of iterators and polymorphism, *hidden inside this call*, data can be a bytes
        
        def close(self):
            
            # *explicitly run the closing code*, which is in usb.core.Device.__del__(),
            # and then defang it so that the gc doesn't get pissy that we've done its work already
            self._dev.__del__()
            self._dev.__del__ = lambda: None
            # pyusb should use a context manager instead of mucking about with __del__s for this
            # __del__ is *not* the opposite of __init__ and it's *not* the same as a C++ dectructor
            del self._dev 
        

except ImportError:
    pass

