import os
import struct

messages = {"GET_ID": 0xF0030003, "BOOT": 0xF0030002}
messages = {k: struct.pack("I", v) for k, v in messages.items()}

#extracted by writing a C program that #include <dev/usb/usb.h> and printf'ing. NOT RELIABLE. MIGHT CHANGE BUILD TO BUILD.
USB_SET_SHORT_XFER = 0x80045571 
USB_SET_TIMEOUT = 0x80045572

import fcntl

DEV = "/dev/ugen0.01"

# BEWARE:
#  with ugen(4) bulk endpoints
#  read()s *must* know the *exact* size they are expecting
#  this is because USB is a packet based protocol and ugen does no buffering except for the current packet
#  socket has recvmsg() for this case, where you can say "I don't care, just give me the *next* message"
#  but read()/write() is a streaming API
#  so the OpenBSD devs did the next best thing, which I *think* is: *if* a packet is buffered *then* force the user to request its exact size
# But! There's a way out: USB_SET_SHORT_XFER allows overly-long reads to succeed
#  which turns this into something very very close to SOCK_SEQPACKET, which is just fine with me.

f = open(DEV, "wb+", 0)

# setting SHORT_XFER allows you to overbuffer
# underbuffering is still an I/O error though
# Setting this
fcntl.ioctl(f, USB_SET_SHORT_XFER, struct.pack("I", True)) #<-- we have to 'struct.pack' because ioctl always expects a *pointer*, even if it's just a pointer to an int which it doesn't modify. python's ioctl handles this by taking bytes() objects, extracting them to C buffers temporarily, and returning the value of it after the C ioctl() gets done with it in a new bytes() object

# 
f.write(messages["GET_ID"])

ASIC_ID = f.read(1<<10)
print("ASIC_ID:")
print(" ".join(hex(e) for e in ASIC_ID))

f.write(messages["BOOT"])
f.write(struct.pack("I", 1000))

f.read()

