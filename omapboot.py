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


class bsd_ugen_bulk:
    """
    wrap BSD's ugen(4) device into a file-like python class.
    
    This class is only good for. If you try to use it on a non-bulk endpoint, the open() will fail.
    """
    
    # DANGEROUS!
    # these ioctl codes were extracted by writing a C program that
    # essentially just did #include <dev/usb/usb.h> + printf().
    # Googling suggests people have done things like ported the _IOW macro to python.
    _USB_SET_SHORT_XFER = 0x80045571 
    _USB_SET_TIMEOUT = 0x80045572

    def __init__(self, device, endpoint):
        """
        TODO: poll ugens for their vendor:device id so that the API can be "open such and such device"
        """
        # rewrite (device: USB int id, endpoint: USB int id) to (device: unix device)
        device = "/dev/ugen%d.%02d" % (device, endpoint)
        
        self._dev = open(device, "wb+", 0)
        self._setShortTransfer()
    
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
        fcntl.ioctl(self._dev, self._USB_SET_TIMEOUT,
                    struct.pack("I", timeout)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object


usb_bulk = bsd_ugen_bulk #choose which file-like USB class is the default


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
    PRODUCT = 0xd00f #TODO: this needs to be a list

    def __init__(self, block=True):
        """
        
        block: whether to fail if the device is not available, or wait for it to become available.
        """
        #TODO: get (device, endpoint) from querying the OS's USB stack for (VENDOR, PRODUCT)
        device, endpoint = 0, 1
        
        if block:
            # really, this should happen above when we *query* for the device
            # but querying is, at best, an expensive poll under ugen(4)
            # So I'm stuck with polling:
            while True:
                try:
                    usb_bulk(device, endpoint).close()
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
