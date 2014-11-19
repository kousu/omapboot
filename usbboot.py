#!/usr/bin/env python3
"""
omap44xx USB pre-bootloader loader.

See README.md for usage.

TODO:
* [ ] Loading is still flakey: rare occasions give I/O errors for no reason.
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


class ugen:
    """
    wrap BSD's ugen(4) device into a file-like python class.
    """
    
    # ioctl codes extracted by writing a C program that #include <dev/usb/usb.h> and printf'ing.
    # NOT RELIABLE. MIGHT CHANGE BUILD TO BUILD. I don't know a good way. Googling suggests people have done things like ported the _IOW macro to python.
    USB_SET_SHORT_XFER = 0x80045571 
    USB_SET_TIMEOUT = 0x80045572

    def __init__(self, device, endpoint, block=True):
        """
        TODO: poll ugens for their vendor:device id so that the API can be "open such and such device"
        """
        # rewrite (device: USB int id, endpoint: USB int id) to (device: unix device)
        device = "/dev/ugen%d.%02d" % (device, endpoint)

        # ugen(4) provides an almost complete implementation is USB, but only per-device
        # I don't have the ability to register an event handler for "plug in this specific vendor:device pair"
        # 
        # So I'm stuck with polling:
        while True:
            try:
                self._dev = open(device, "wb+", 0)
                break
            except OSError:         # TODO: there are corner cases, like negative endpoints, that fall through the cracks in this liberal slurp
                if block:
                    pass
                else:
                    raise
            time.sleep(0.1)
    
    def read(self, len):
        return self._dev.read(len)
    
    def write(self, data):
        return self._dev.write(data)
    
    def close(self):
        return self._dev.close()
    
    def setShortTransfer(self, on=True):
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
    
    def setTimeout(self, timeout):
        """
        """
        fcntl.ioctl(self._dev, self.USB_SET_TIMEOUT,
                    struct.pack("I", timeout)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object



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

class OMAP:
    """
    implement and provide a nice API for the bootstrapping protocol that the omap44xx chips run in ROM if booted
    a) with USB plugged in
    b) and no battery
    
    notable points:
    * the protocol is little-endian *for all currently defined devices*, and it's probably not going to change now that TI's given up on it
    """
    
    # n
    
    usb_cls = ugen #future-proofing that I'll probably never use
    
    messages = {"GET_ID": 0xF0030003, "BOOT": 0xF0030002}
    messages = {k: struct.pack("I", v) for k, v in messages.items()}
    locals().update(messages)
    del messages

    def __init__(self, device, endpoint, block=True):
        """

        """
        # stash the USB address for boot()
        self._addr = device, endpoint
        
        # open the USB device
        self._dev = OMAP.usb_cls(device, endpoint)
        self._dev.setShortTransfer() #since we don't necessarily know how long things will be
        
    def id(self):
        self._dev.write(self.GET_ID)
        id = self._dev.read(1<<10)
        return id #TODO: parse this
    
    def upload(self, fname):
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
        self._dev.write(self.BOOT)
        self.upload(x_loader)
        print("Uploaded x-loader.",end="")
        # reopen the USB device so that we start talking to x_loader
        # 
        self._dev.close()
        
        # IMPORTANT: give the 2nd stage a moment to orient itself;
        #            reopening too quickly makes things crash, and what "too" means fluctuates a little bit.
        for i in range(3):
           print(".", end="")
           time.sleep(1)
        print(" Now reopening")
        
        self._dev = OMAP.usb_cls(*self._addr)
        notice = self._dev.read(4)
        notice, = struct.unpack("I", notice) #< the comma is because struct returns a tuple of as many items as you tell it to expect
        assert notice == 0xAABBCCDD, "Unexpected notification `%x` from what should be the 2nd stage bootloader, announcing itself ready to download more" % (notice)
        
        self.upload(u_boot)
        
        # close the device because there's nothing left to dooo
        self._dev.close()



if __name__ == '__main__':
    assert len(sys.argv) == 3, "usage: usbboot 2ndstage.bin 3rdstage.bin"
    print("waiting for omap44 device")
    omap = OMAP(0, 1)
    
    # do initial header connect (is this necessary? does the board *expect* this?)
    ASIC_ID = omap.id()
    print("ASIC_ID:")
    print(" ".join(hex(e) for e in ASIC_ID))
    
    omap.boot(sys.argv[1], sys.argv[2])
