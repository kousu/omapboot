#!/usr/bin/env python3
"""
omap44xx USB pre-bootloader loader.

See README.md for usage.

TODO:
* [ ] Parse the ASIC ID and pretty-print it.
* [ ] Loading is still flakey: rare occasions give I/O errors for no reason.
  * [ ] Is there any way to contain the OMAP protocol in a class separate from the verrry useful interactive prints?
* [ ] Factoring (of course)
* [ ] Import C ioctl() codes reliably
* [ ] Look up the USB MTU and set it as a default value on ugen.read(len=)
* [ ] Tests
* [ ] Documentation:
  * [ ] how signing works
  * [ ] photos to go with my instructions
  * [ ] Collect a list of "good" boot images and/or instructions on how to build them

Credits:
* Brian Swetland, for the original version <https://github.com/swetland/omap4boot>
* Dmitry Pervushin, for clues <https://github.com/dmitry-pervushin/usbboot-omap4>
* Won Kyu Park, the Windows version and the clues that finally put this together.
* Nick Guenther, for python port.
* Texas Instruments, for publishing their canon, even though omapflash is spaghetticode from hell <https://gforge.ti.com/gf/project/flash/>
"""

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
        
        self.device = None #device *address* (a 8-bit integer)
        self.endpoint = endpoint #endpoint address (a 4-bit integer)
        self.timeout = timeout #either None or a 32-bit integer in milliseconds
    
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
        # --> No, we don't. Device.{read,write}() implicitly claim it every time.
        # the pyusb docs suggest that doing this is the correct first step
        # this isn't quite claiming, but maybe it's.. the same?
        self._dev.set_configuration()
        
        
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
    
    # DANGEROUS!
    # these ioctl codes were extracted by writing a C program that
    # essentially just did #include <dev/usb/usb.h> + printf().
    # Googling suggests people have done things like ported the _IOW macro to python.
    _USB_SET_SHORT_XFER = 0x80045571 
    _USB_SET_TIMEOUT = 0x80045572

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
        fcntl.ioctl(self._dev, self._USB_SET_SHORT_XFER,
                    struct.pack("I", on)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object
    
    def _setTimeout(self, timeout):
        """
        """
        if timeout is None:
            #  "The value 0 is used to indicate that there is no timeout."
            timeout = 0 #
        fcntl.ioctl(self._dev, self.USB_SET_TIMEOUT,
                    struct.pack("I", timeout)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object


# pick an API accord to what OS we find ourselves on
# XXX this overwrites the Abstract Base Class!!!
usb_bulk = pyusb_bulk # default
if "BSD" in os.uname().sysname:
    usb_bulk = bsd_ugen_bulk


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
                    self._dev = usb_bulk(self.VENDOR, self.PRODUCT)
                    break
                except OSError:
                    pass
                time.sleep(0.1)
         
        
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
        #self._dev.close()
        #self._dev._dev.reset()
        
        # IMPORTANT: the 2nd stage needs a moment to orient itself;
        #            reopening too quickly makes things crash, and what "too" means fluctuates a little bit.
        print("Reopening USB port", end="", flush=True)
        for i in range(3):
           print(".", end="", flush=True);
           time.sleep(1)
        
        # XXX pyusb has 'Device.reset()'. Maybe it's better to provide that instead of close()? But then the object is less file-like...
        # I could always write a reset() for ugen as well
        # 
        
        #self._dev = usb_bulk(self.VENDOR, self.PRODUCT)
        print("done.")
        
        # read x-loader "banner"
        # By convention(?) this is only printed by x-loaders that are awaiting a u-boot download over USB
        # The NAND x-loader that came with your device won't print it, for example.
        banner = self._dev.read(4)
        banner, = struct.unpack("I", banner) #< the comma is because struct returns a tuple of as many items as you tell it to expect
        assert banner == 0xAABBCCDD, "Unexpected banner `0x%X` from what should have been x-loader." % (notice)
        
        print('Received boot banner ("0x%X") from x-loader.' % (banner,))
        
        # We also need to ensure the battery is in before we continue,
        # because U-Boot will shut down if it finds no battery.
        # Possibly this could replace the sleep() above,
        # but it is useful to be able for the user to see the banner came through properly at the same time they are putting in the bbatter
        # Note: this assumes that all x-loaders you use with this program
        # will be happy to wait indefinitely for you!
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
