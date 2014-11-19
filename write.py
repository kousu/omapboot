import os
import struct

messages = {"GET_ID": 0xF0030003, "BOOT": 0xF0030002}
messages = {k: struct.pack("I", v) for k, v in messages.items()}

DEV = "/dev/ugen0.01"

# in posix instead??
f = os.open(DEV, os.O_RDWR) # | os.O_NONBLOCK)
oops = os.write(f, messages["GET_ID"]) #<-- this is pissing the chip off. if it's commented out the read hangs. in, the read crashes, 
# which must be because the chip is EPIPE'ing
#print("wrote? %d bytes" % oops)
print(f)

durp = os.read(f, 81)
print("got:")
print(repr(durp))


raise SystemExit(0)

f = open(DEV, "wb+", 0)
oops = f.write(messages["GET_ID"])
print("wrote? %d bytes" % oops)
print(f)

durp = f.read()
print("got:")
print(repr(durp))

