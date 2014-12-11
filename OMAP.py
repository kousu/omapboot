

import os
import struct
from array import array

# monkey-patch array to prettyprint a *byte* array in hex
def tohex(self):
    assert self.typecode == "B", "Only valid on byte arrays"
    return "0x"+str.join('', ("%02X" % e for e in self))
#array.tohex = tohex; del tohex #darn. array is a C extension type so I can't do this because python's a jerk.


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
    
    # References:
    # * TI's OMAP4430 Technical Reference Manual (TRM) Chapter 27: Initialization, available at <http://www.ti.com/product/OMAP4430/technicaldocuments>
    # * TI's Flash.exe/omapflash.exe, especially <https://gforge.ti.com/gf/project/flash>/trunk/omapflash/host/pheriphalboot.c
    # * guesswork
    #
    # Notes:
    # * the protocol is little-endian *for all currently defined devices*, (see: ti's flash[...])
    #   and it's probably not going to change now that TI's given up on it
    
    messages = {"GET_ID": 0xF0030003, "BOOT": 0xF0030002}
    messages = {k: struct.pack("I", v) for k, v in messages.items()}
    locals().update(messages)
    del messages
    
    def __init__(self, port):
        """
        port: a file-like object in read/write mode which
              should be connected to an OMAP device.
        """
        
        self._dev = port
        
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
        self._dev.write(self.GET_ID)
        ASIC = self._dev.read(0xFF)

        def split_ASIC_blocks(ASIC):
            ASIC = array("B", ASIC)
            N = ASIC.pop(0)
            for i in range(N):
                type = ASIC.pop(0)
                length = ASIC.pop(0)
                assert length <= len(ASIC), "Don't overflow! Python will silently let us overflow if we're not careful"
                data, ASIC = ASIC[:length], ASIC[length:]
                assert data.pop(0) == 1, "Fixed value, e.g. as in TRM table 27-19"
                yield type, data
            assert not ASIC, "ASIC should be empty once we've parsed all its blocks"
        
        def parse_ASIC_blocks(ASIC):
            for type, data in split_ASIC_blocks(ASIC):
                # TODO: clean this up with some classes and a nice dictionary lookup
                #print(type, data) #DEBUG
                if type == 0x01:
                    assert len(data) == 4
                    model, ch_enabled, version = data[:2], data[2], data[3]
                    assert model.tobytes() == b"\x44\x30", "model number, written in hex just to be funny"
                    ch_enabled = {0x07: "enabled", 0x17: "disabled"}.get(ch_enabled, "unknown")
                    print("Model:", tohex(model)[2:])
                    print("ROM revision: 0x%02x" % (version,))
                    print("CH:", ch_enabled) #this has something to do with the header format of certain boot images. See the TRM.
                
                ## these next ones were taken from @swetland's usbboot.c. I don't know what they mean.
                elif type == 18:
                   assert len(data) == 20
                   print("IDEN:", tohex(data))
                elif type == 19:
                    # unknown and undocumented
                    assert len(data) == 1
                    print("Undocumented ID subblock 18: %02X"  % (data[0],))
                elif type == 20:
                    assert len(data) == 32
                    print("MPKH:", tohex(data))
                elif type == 21:
                    assert len(data) == 8
                    CRC0, CRC1 = data[:4], data[4:]
                    print("CRC0:", tohex(CRC0))
                    print("CRC0:", tohex(CRC1))
        
        print("recevied ASIC ID banner:")
        parse_ASIC_blocks(ASIC)

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
