

try:
    from usbbulk import BulkUSB
except ImportError:
    raise SystemExit("No USB API available.")

import os
import struct

import time

from util import *

class BaseOMAP:
    pass

class OMAP4(BaseOMAP):
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
    
    # USB IDs:
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
                    self._dev = BulkUSB(self.VENDOR, self.PRODUCT)
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
    
    def boot(self, x_loader, u_boot, AUTOFLAG=False):
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
        
        # IMPORTANT: the 2nd stage needs a moment to orient itself;
        #            speaking to it too quickly makes things crash,
        #            and what "too" means fluctuates a little bit.
        print("Giving x-loader a chance to come up", end="", flush=True)
        for i in range(3):
            print(".", end="", flush=True);
            time.sleep(1)
        print()
        
        # read x-loader "banner"
        # By convention(?) this is only printed by x-loaders that are awaiting a u-boot download over USB
        # The NAND x-loader that came with your device won't print it, for example.
        banner = self._dev.read(4)
        banner, = struct.unpack("I", banner) #< the comma is because struct returns a tuple of as many items as you tell it to expect
        assert banner == 0xAABBCCDD, "Unexpected banner `0x%X` from what should have been x-loader." % (notice)
        
        print('Received boot banner ("0x%X") from x-loader.' % (banner,))
        
        # We also need to ensure the battery is in before we continue,
        # because U-Boot will shut down if it finds no battery.
        # (this is the source of the "wait 4 seconds" myth on xda-developer.com's LG-p760 subforum:
        #  if the usb boot doesn't wait for you, you need to time it so that you start with the battery
        #  out so that the OMAP protocol is available, but you put the battery in before U-Boot comes up)
        # Possibly this could replace the sleep() above,
        # but it is useful to be able for the user to see the banner came through properly at the same time they are putting in the bbatter
        # Note: this assumes that all x-loaders you use with this program
        # will be happy to wait indefinitely for you!
        if not AUTOFLAG:
            input("Insert battery and press enter to upload u-boot > ")
        
        print("Uploading u-boot... ", end="", flush=True);
        self.upload(u_boot)
        print("done.", flush=True);
        
        
        # close the device because there's nothing left to dooo
        self._dev.close()
