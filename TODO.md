TODO
=====

* [ ] Parse the ASIC ID and pretty-print it.
* [x] Loading is still flakey: rare occasions give I/O errors for no reason.
* [ ] Separate the OMAP class with the protocol from the UI; namely, the print() and input()s in .boot()
* [ ] Look up the USB MTU and set it as a default value on ugen.read(len=)
* [ ] Tests
* [ ] Documentation:
  * [ ] how signing works
  * [ ] photos to go with my instructions
  * [ ] Collect a list of "good" boot images and/or instructions on how to build them
* [ ] bsd_ugen_bulk:
  * [ ] Import C ioctl() codes reliably
  * [ ] Write find() to match pyusb's
* [ ] pyusb_bulk:
  * [ ] .close() causes future reads on the same device to break. 
* [x] perhaps OMAP should take the communication port object as an argument (after all, it should work equally well over serial), and main() should be responsible for putting the two together
* [ ] Write various serial port implementations that can be fed to OMAP
* [ ] Build Windows packages (pyfreeze?)
* [ ] Build OS X packages
* [ ] Find and build TI's awesome and stupidly powerful U-Boot version; `chip_upload` sounds like a supppper useful button.