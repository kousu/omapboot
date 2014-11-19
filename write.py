import os
import struct

messages = {"GET_ID": 0xF0030003, "BOOT": 0xF0030002}
messages = {k: struct.pack("I", v) for k, v in messages.items()}

DEV = "/dev/ugen0.01"

# BEWARE:
#  with ugen(4) bulk endpoints
#  read()s *must* know the *exact* size they are expecting
#  this is because USB is a packet based protocol and ugen does no buffering except for the current packet
#  socket has recvmsg() for this case, where you can say "I don't care, just give me the *next* message"
#  but read()/write() is a streaming API
#  so the OpenBSD devs did the next best thing


f = open(DEV, "wb+", 0)
oops = f.write(messages["GET_ID"])

durp = f.read(81)
print("got:")
print(repr(durp))

