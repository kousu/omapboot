#!/usr/bin/env python3
"""
omap44xx USB pre-bootloader loader.

See README.md for usage.

TODO:
* [ ] Parse the ASIC ID and pretty-print it.
* [ ] Loading is still flakey: rare occasions give I/O errors for no reason.
  * [ ] Is there any way to contain the OMAP protocol in a class separate from the verrry useful interactive prints?
* [ ] Factoring (of course)
* [ ] Look up the USB MTU and set it as a default value on ugen.read(len=)
* [ ] Tests
* [ ] Documentation:
  * [ ] how signing works
  * [ ] photos to go with my instructions
  * [ ] Collect a list of "good" boot images and/or instructions on how to build them
"""

__author__ = "Nick Guenther"
__email__ = "nguenthe@uwaterloo.ca"

import sys, os
import fcntl, struct
import time

import warnings

class usb_bulk:
    """
    abstract base class
    """
    def __init__(self, vendor, product, endpoint=1, timeout=None):
        """
        endpoint is a 4-bit integer identifying which particular piece of the device this bulk port talks to
        timeout is in milliseconds
        """
        if not (0 <= endpoint < (1<<4)):
            raise ValueError("USB endpoints are only 4 bits long")
        if endpoint == 0:
            raise ValueError("Control endpoints are never bulk endpoints.") #TODO choose a better exception class
        
        if timeout == 0:
            # be defensively consistent with bsd_ugen_bulk
            timeout = None
        
        if timeout is not None:
            if not (0 < timeout < 1<<32):
                raise ValueError("Timeout must be an unsigned 32-bit integer if given.")
        
        self.device = None
        self.endpoint = endpoint
        self.timeout = timeout
    
    def read(self, len):
        raise NotImplementedError
    
    def write(self, data):
        raise NotImplementedError
    
    def close(self):
        raise NotImplementedError

class pyusb_bulk(usb_bulk):
    """
    
    """
    
    import usb as _usb
    
    def __init__(self, vendor, product, endpoint=1, timeout=None):
        """
        
        timeout is in milliseconds; if it's 
        the
        """
        super().__init__(vendor, product, endpoint, timeout)
        
        self._dev = self._usb.core.find(idVendor=vendor, idProduct=product)
        if self._dev is None:
            raise OSError("Unable to find USB Device %04x:%04x" % (vendor, product))
        
        #XXX does this need to "claim" the "interface"? it seems to work without doing that...
        # the pyusb docs suggest that doing this is the correct first step
        # this isn't quite claiming, but maybe it's.. the same?
        self._dev.set_configuration()
        
        # set up the in and out endpoints by bit-twiddling
        # see http://www.beyondlogic.org/usbnutshell/usb5.shtml#EndpointDescriptors for a reference
        # Endpoint Address
        # Bits 0..3b Endpoint Number.
        # Bits 4..6b Reserved. Set to Zero
        # Bits 7 Direction 0 = Out, 1 = In (Ignored for Control Endpoints)
        # It seems like this should be something handled by pyusb already.
        print(self._dev)
        
        # motherfuckers
        # it would be convenient to cache the Endpoints at init
        # but the arg to Endpoint() is a "logical index" which is basically meaningless:
        # it's the index of the endpoint in dev.configurations()[0].interfaces()[0].endpoints()
        # rather than being, say, the USB endpoint ID or at least the bEndpointAddress
        # TODO: patch pyusb so that you write Endpoint(device, endpoint_id, direction) instead
        #
        self._endpoint = endpoint
        self._in = self._usb.core.Endpoint(self._dev, 0b10000000 | endpoint)
        self._out = self._usb.core.Endpoint(self._dev, 0b00000000 | endpoint)
        
    def read(self, len):
        """
        returns a bytes object
        """
        return self._in.read(len, timeout=self.timeout).tobytes()
        #pyusb works in Array objects. Which are totally the future,
        # but are inconsistent with bsd_ugen_bulk
        # and are more obscure than common python.
    
    def write(self, data):
        """
        data should be a bytes object
        """
        return self._out.write(data, timeout=self.timeout) #careful: pyusb returns array objects, but because of the magic of iterators and polymorphism, *hidden inside this call*, data can be a bytes
    
    def close(self):
        del self._in
        del self._out
        
        # *explicitly run the closing code*, which is in usb.core.Device.__del__(),
        # and then defang it so that the gc doesn't get pissy that we've done its work already
        self._dev.__del__()
        self._dev.__del__ = lambda: pass
        # pyusb should use a context manager instead of mucking about with __del__s for this
        # __del__ is *not* the opposite of __init__ and it's *not* the same as a C++ dectructor
        del self._dev 
    

class bsd_ugen_bulk(usb_bulk):
    """
    wrap BSD's ugen(4) device into a file-like python class.
    
    This class is only good for bulk. If you try to use it on a non-bulk endpoint, the open() will fail.
    
    Online reference: http://www.openbsd.org/cgi-bin/man.cgi/OpenBSD-current/man4/ugen.4?query=ugen
    
    TODO:
    * [ ] make .timeout() a property that calls ._setTimeout();
         this is complicated by this chicken-or-egg: self._dev needs to be exist to run _setTimeout, but self.timeout is set by super().__init__() before that happens
         i suppose i could call super().__init__ in the middle of things, but that's... weird
    """
    
    # ioctl codes extracted by writing a C program that #include <dev/usb/usb.h> and printf'ing.
    # NOT RELIABLE. MIGHT CHANGE BUILD TO BUILD. I don't know a good way. Googling suggests people have done things like ported the _IOW macro to python.
    USB_SET_SHORT_XFER = 0x80045571 
    USB_SET_TIMEOUT = 0x80045572

    def __init__(self, vendor, product, endpoint=1, timeout=None):
        """
        
        endpoint defaults to '1' because that's the most common endpoint to have a bulk interface.
        TODO: poll ugens for their vendor:device id so that the API can be "open such and such device"
        """
        super().__init__(vendor, product, endpoint, timeout)
        
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
        fcntl.ioctl(self._dev, self.USB_SET_SHORT_XFER,
                    struct.pack("I", on)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object
    
    def _setTimeout(self, timeout):
        """
        """
        if timeout is None:
            #  "The value 0 is used to indicate that there is no timeout."
            timeout = 0 #
        fcntl.ioctl(self._dev, self.USB_SET_TIMEOUT,
                    struct.pack("I", timeout)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object


usb_bulk = bsd_ugen_bulk #future-proofing that I'll probably never use
usb_bulk = pyusb_bulk


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
        target.write(chunk)
# TODO: attach this to a suitably high-level class in the IO hierarchy




class OMAP4:
    """
    implement and provide a nice API for the bootstrapping protocol that the omap44xx chips run in ROM if booted
    a) with USB plugged in
    b) and no battery
    
    """
    
    
    # notable points:
    # * the protocol is little-endian *for all currently defined devices*, (see: ti's flash[...])
    #   and it's probably not going to change now that TI's given up on it
    
    messages = {"GET_ID": 0xF0030003, "BOOT": 0xF0030002}
    messages = {k: struct.pack("I", v) for k, v in messages.items()}
    locals().update(messages)
    del messages
    
    VENDOR = 0x0451
    PRODUCT = 0xd00f #TODO: this needs to be a list; XXX pyusb has hooks that make it easy to implement this... but openbsd doesn't

    def __init__(self, block=True):
        """
        
        block: whether to fail if the device is not available, or wait for it to become available.
        """
        
        if block:
            # As far as I can tell, without kernel hooks (which are too
            # platform-specific for this code) USB has no way to register
            # event handlers. So I'm stuck with polling:
            while True:
                try:
                    usb_bulk(self.VENDOR, self.PRODUCT).close()
                    break
                except OSError:
                    pass
                time.sleep(0.1)
        
        # stash the USB address for boot()'s use
        # we assume that the same device won't be replugged during the duration of this program 
        self._addr = device, endpoint
        
        # open the USB device
        
        self._dev = usb_bulk(device, endpoint)
        
    def id(self):
        self._dev.write(self.GET_ID)
        id = self._dev.read(1<<10)
        return id #TODO: parse this
    
    def upload(self, fname):
        """
        OMAP uses the world's simplest uploading protocol:
         say how much then say the stuff.
        """
        # content-length header
        size = os.stat(fname).st_size
        self._dev.write(struct.pack("I", size))
        
        # content
        readinto_io(open(fname, "rb"), self._dev)
    
    def boot(self, x_loader, u_boot):
        """
        x_loader and u_boot should be filenames so that we can stat them for their filesizes
         note: you are not obligated to actually provide a u-boot instance. any raw ARM program can in theory be uploaded, so long as its suitable for just dumping into RAM and jumping into
        
        closes the USB device when done, since booting means replacing what this class is designed to talk to
        """
        
        # upload 2nd stage (x-loader) via the 1st stage
        self._dev.write(self.BOOT)
        print("Uploading x-loader...", end="", flush=True);
        self.upload(x_loader)
        print("done.")
        
        # reopen the USB device so that we start talking to x-loader
        self._dev.close()
        
        # IMPORTANT: the 2nd stage needs a moment to orient itself;
        #            reopening too quickly makes things crash, and what "too" means fluctuates a little bit.
        print("Reopening USB port", end="", flush=True)
        for i in range(3):
           print(".", end="", flush=True);
           time.sleep(1)
        
        self._dev = usb_bulk(*self._addr)
        print("done.")
        
        # read x-loader "banner"
        banner = self._dev.read(4)
        banner, = struct.unpack("I", banner) #< the comma is because struct returns a tuple of as many items as you tell it to expect
        assert banner == 0xAABBCCDD, "Unexpected banner `0x%X` from what should have been x-loader." % (notice)
        
        print('Received boot banner ("0x%X") from x-loader.' % (banner,))
        
        # We also need to ensure the battery is in before we continue, because U-Boot will shut down if it finds no battery.
        # This could be rolled together
        input("Insert battery and press enter to upload u-boot > ")
        
        print("Uploading u-boot... ", end="", flush=True);
        self.upload(u_boot)
        print("done.", flush=True);
        
        
        # close the device because there's nothing left to dooo
        self._dev.close()



if __name__ == '__main__':
    assert len(sys.argv) == 3, "usage: usbboot 2ndstage.bin 3rdstage.bin"
    print("Waiting for omap44 device. Make sure you start with the battery out.")
    omap = OMAP4()
    
    # Read the chip ident. This isn't necessary for booting,
    # but it's useful for debugging different peoples' results.
    #ASIC_ID = omap.id()
    #print("ASIC_ID:")
    #print(" ".join(hex(e) for e in ASIC_ID))
    
    omap.boot(sys.argv[1], sys.argv[2])
