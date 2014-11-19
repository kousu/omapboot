
import struct

messages = {"GET_ID": 0xF0030003, "BOOT": 0xF0030002}
messages = {k: struct.pack("I", v) for k, v in messages.items()}

for i in range(16):
	try:
		f = open("/dev/ugen0.%02d"%i, "wb", 0)
		oops = f.write(messages["GET_ID"])
		print("wrote? %d bytes" % oops)
	except Exception as e:
		print("%d failed" %i)
		print(e)

# run with python -i
