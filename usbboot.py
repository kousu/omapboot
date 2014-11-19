"""
omap44xx USB pre-bootloader loader.

omap44xx is the chip inside several recent LG Android phones. Look it up on Wikipedia: [....]
This program lets you completely sidestep the bootloaders in NAND,
   which should make it possible to do anything to
    and this is the way the systems come installed from the factory.



usage:
 pull all power from your device (i.e. take out the battery and unplug the USB cable)
 plug in the usb cable with the battery still out. You should see the device attaching and detaching in dmesg
 during (TODO: detect when the device is attached to avoid this awkwardness)

WARNING: there's *signing* issues (? I think?? @wkpark can help with this)
 - the 1st stage knows signing keys which its manufacturer burned into it
 ..except if that's true, how is it possible for signing keys to get updated, as ping.se complained about with his HTC?

depends on BSD's ugen(4) devices, so will *not* work on Linux, Windows or Mac
 (but actually it shouldn't be toooooo hard to abstract into a class hierarchy OMAP.{read,write}(),
 abstracting over {usb,serial}x{windows,linux,bsd,os x}, but if I'm going to do that I might as well just use libusb)

Terminology:
 1st stage: the burned-in ROM bootloader, which implements the protocol that this script speaks to
 2nd stage: the small bootstrap bootloader whose usual job is to load the 3rd stage. also called "aboot" and "x-loader", for some reason.
 3rd stage: the larger bootloader, always always some version of U-Boot, which knows how to boot Linux and/or NetBSD and/or etc
 


 boot.img: a simply packed kernel+ramdisk (mkbootimg in the android sources can make this, and ping.se's unmkbootimg can tear it apart)
 recovery.img: an alternate boot.img which is meant to be similar; doesn't always actually do what it says it should.
 system.img: wh
 NAND: a type of solid state storage; all omap devices on the market come with a NAND chip where all data beyond the 1st stage is kept.

"""
import sys, os
import fcntl, struct
import time





# BEWARE:
#  with ugen(4) bulk endpoints
#  read()s *must* know the *exact* size they are expecting
#  this is because USB is a packet based protocol and ugen does no buffering except for the current packet
#  socket has recvmsg() for this case, where you can say "I don't care, just give me the *next* message"
#  but read()/write() is a streaming API
#  so the OpenBSD devs did the next best thing, which I *think* is: *if* a packet is buffered *then* force the user to request its exact size

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
# But! There's a way out: USB_SET_SHORT_XFER allows overly-long reads to succeed
#  which turns this into something very very close to SOCK_SEQPACKET, which is just fine with me.
~        
        setting SHORT_XFER allows you to *overbuffer*: you can set read() values that are much larger than you expect to make sure you get everything in a packet

        underbuffering is still an I/O error though
        Setting this
        """

        fcntl.ioctl(self._dev, self.USB_SET_SHORT_XFER,
                    struct.pack("I", on)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object
    
    def setTimeout(self, timeout):
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
