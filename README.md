OMAP44xx bootloader-bootloader, for OpenBSD
=========================================

omap44xx is a set of system-on-chip inside several recent Android phones.

At the lowest layer, it's pretty much just like any other embedded device,
and in particular it needs to be bootstrapped at the factory.
This program implements the low level protocol that starts the bootstrap process
and thus, in theory, lets you completely sidestep the probably 
locked-down system that came on the NAND.

I love getting comments and knowing I'm helping people,
and also feedback on what's broken if I'm not.
So please, don't be shy, you can bug me by email or in
the issue tracker here.

Requirements
-------------

* {Open,Net,Free}BSD
* python3
* a smartphone that runs on omap4[wikipedialink]()

I wrote this on BSD because, apparently in contrast to every other OS ever,
when BSD sees a USB device it doesn't recognize, it just you talk to as if
it were any other unix device file. I could port this to other systems,
but it overlaps with [omap4boot/usbboot.c]() which is supposed to run on Windows and Linux.


Usage
------


If you are able, **MAKE BACKUPS**. For example, with root, I took backups of all my NAND partitions like so:
```
 [ ... ]
```

Then, you need to find or make some boot images. This is the most frustrating and difficult part, and I cannot help you with it because every phone is slightly different. Poke around [xda].
You will probably use a fixed 2nd stage image, and vary your U-Boot images.
You also need to ensure that the [images are signed for your device]().

* pull all power from your device (i.e. take out the battery and unplug the USB cable)
* plug in the usb cable with the battery still out. You should see a device attaching and detaching in [dmesg(8)](). It has USB vendor id 0x0451 (aka Texas Instruments) and product id 0xd00f or _____
* run the program: `omapboot aboot.bin uboot.bin`
* the next time the device attaches, omapboot will catch it and boot the images.
* from there, you can go on and poke at your device through U-Boot: depending on the build you have, you have access to a USB serial console command prompt and/or fastboot. If you're sharp, you can roll your own u-boot images to do whatever you need.

Terminology
-----------


* <u>NAND<u>: a type of solid state storage; all omap devices on the market come with a NAND chip where all data beyond the 1st stage is kept.
* <u>1st stage</u>: the very lowest level bootloader, at the same level as the BIOS in a PC, which implements the protocol that this script speaks to. This is burned-in to the ROM; it does not sit on a NAND partition.
* <u>2nd stage</u>: the small bootstrap bootloader whose job is to load the 3rd stage. Also called "aboot" and "x-loader", for some reason. This intermediate loader is a quirk of the OMAP system; most computers have a ROM bootloader, a disk bootloader, and a kernel--though actually, this three stage system should be familiar to BSD users. **Only on the systems that I've seen**, the NAND partition for this is named "x-loader" (and so that's the name you'd use if you want to flash it). In principle, you could subvert this to do something besides loading the 3rd stage.
* <u>3rd stage</u>: the larger bootloader, always always some version of U-Boot, which knows how to boot Linux and/or NetBSD and/or etc. The NAND partition is named "u-boot".
* <u>boot</u>: in the context of Android, a simply packed kernel+ramdisk created by [mkbootimg]().  ping.se's [unmkbootimg]() can tear it apart.
* <u>recovery.img</u>: an alternate boot.img which is meant to be like Windows Startup Repair; a lot of rooting guides methods have as their goal the installation of a "recovery", like [ClockworkMod]()
* <u>system.img</u>: where the Android system lives. If you know unix, think of boot as /boot, and system as /usr ((XXX is this accurate?))
* <u>vendor.img</u>: this is meant to be where all the bloatware that a cellphone carrier stuffs onto your phone goes. whether it actually gets used for that is up to the vendor. Sort of like /opt
* <u>cache.img</u>: Android is written in java, and java takes a long time to compile. Compiled files get put here. Clearing the cache (XXX is this accurate?)
* <u>userdata.img</u>: like /home. But unlike /home, at the Android layer, apps get separate folders and cannot see each other's area (TODO: link a good explanation of how android jailing works). Some devices set aside a subfolder here for an "internal SD card", which apps _can_ share.



References
----------

* [TI's flash.exe]() and [wiki pages]()
* [@swetland's omap4boot](), helped out by [@wkpark]() and [@dimitry]()
* XDA: 
* [ugen(4)]()
* [ping's every-root guide]() (this is really just "how to install your own OS on an ARM system", with rooting an Android as an immediate corrollary).
* [] (did you know you can download pieces of Android's code? This site will package any subfolder for you at a click)