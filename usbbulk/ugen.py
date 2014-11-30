
import os

if "BSD" in os.uname().sysname:
    import fcntl, struct
    import warnings
    from .base import *
    
    class BulkUSB(BaseBulkUSB):
        """
        wrap BSD's ugen(4) device into a file-like python class.
        
        This class is only good for bulk. If you try to use it on a non-bulk endpoint, the open() will fail.
        
        I wrote this on BSD because, apparently in contrast to every other OS ever,
    when BSD sees a USB device it doesn't recognize, it just you talk to as if
    it were any other unix device file.

        
        Online reference: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man4/ugen.4?query=ugen
        
        """
        
        # DANGEROUS!
        # these ioctl codes were extracted by writing a C program that
        # essentially just did #include <dev/usb/usb.h> + printf().
        # Googling suggests people have done things like ported the _IOW macro to python.
        _USB_SET_SHORT_XFER = 0x80045571 
        _USB_SET_TIMEOUT = 0x80045572

        def __init__(self, vendor, product, endpoint=1):
            """
            
            endpoint defaults to '1' because that's the
            most common endpoint to have a bulk interface.
            """
            super().__init__(vendor, product, endpoint)
            
            warnings.warn("bsd_ugen_bulk does not implement device and endpoint scanning yet; it just assumes that you only have one USB device you want to work with at a time.")
            #TODO: instead we should scan the devices with ioctl()s on /dev/ugen$I.00 for (VENDOR, PRODUCT)
            device = 0
            
            # rewrite (device: USB int id, endpoint: USB int id) to (device: unix device)
            device = "/dev/ugen%d.%02d" % (device, endpoint)
            
            self._dev = open(device, "wb+", 0)
            self._setShortTransfer()
            self._setTimeout(self.timeout)
        
        def read(self, len):
            return self._dev.read(len)
        
        def write(self, data):
            return self._dev.write(data)
        
        def close(self):
            return self._dev.close()
        
        def _setShortTransfer(self, on=True):
            """
            ugen(4) bulk endpoints behave essentially like SOCK_SEQPACKET sockets.
            However, by default, read()s *must* know the *exact* size of the packet
            they are expecting, or else the kernel gives an I/O error.
            This is because USB is a packet based protocol and ugen does no buffering.
            
            socket has recvmsg() for this case, but unless ugen(4) gained a terrible
            ioctl() API for packets, it has to fudge packet semantics into the
            read()/write() streaming semantics. Personally, I think the BSD devs did
            a very good job in squeezing the two together.
            
            But! There's almost a way out: USB_SET_SHORT_XFER allows overly-long
            reads to succeed. So long as your read packets are not unbounded (and
            technically they can't be because USB has upper limits), you can just
            tell read() large numbers that you don't actually expect to see. This is
            just like how with tcpdump you can't set the capture length to infinity
            but 65536--the maximum transfer unit of ip--is just as good.
            
            If you actually need finer control than this you need to not use ugen(4).
            Use libusb instead.
            """
            fcntl.ioctl(self._dev, self._USB_SET_SHORT_XFER,
                        struct.pack("I", on)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object
        
        def setTimeout(self, timeout):
            """
            """
            if timeout is None:
                #  "The value 0 is used to indicate that there is no timeout."
                timeout = 0 #
            fcntl.ioctl(self._dev, self._USB_SET_TIMEOUT,
                        struct.pack("I", timeout)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object

