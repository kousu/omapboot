OMAP44xx bootloader-bootloader, for OpenBSD
=========================================

OMAP is a brand of system-on-chips inside several recent Android phones.

At the lowest layer, it's pretty much just like any other embedded device,
and in particular it needs to be bootstrapped at the factory.
This program implements the lowest level protocol that starts the
bootstrap process in these chips:
* omap4430
* omap????
* ????????
In theory, this lets you completely sidestep the system sitting
on the NAND, making physical access == root access like it should be.

I love getting comments and knowing I'm helping people,
and also feedback on what's broken if I'm not.
So please, don't be shy! Leave me an email or post in
the issue tracker here.

Requirements
-------------

* python3
* pyusb>=1.0.0 or {Open,Net,Free}BSD
* a smartphone that runs on omap4[wikipedialink]()

Installation
------------

This is not published yet, but for now you can install it with setuptools:
```
$ git clone https://github.com/kousu/omapboot
$ cd omapboot
$ python setup.py develop --user
$ omapboot
usage: usbboot [-a] 2ndstage.bin 3rdstage.bin
```

By using 'develop', the script installed to your $PATH gets pointed at cloned folder,
so you can tweak it directly (which you might need to do).
You might need to edit your $PATH, though:
```
$ cat ~/.profile
[...]
export PATH=~/.local/bin:$PATH
[...]
```

Usage
------

Before anything, **MAKE BACKUPS**. I took backups of all my NAND partitions like so:
```
$ adb shell
$ su
# for i in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14; do dd if=/dev/block/mmcblk0p$i of=/sdcard/mmcblk0p$i.img; done
```
and then copied the images off the SD card. This will probably take at least an hour to get everything.
_This requires a rooted Android, of course. In theory having control of the bootloader should allow you to boot an image which just takes backups automagically, but I don't have that built yet_
_Depending on the size of your partitions, you may need to do this in multiple steps_. 

Then, you need to find or make some boot images. In general, this is the most frustrating and difficult part, and I cannot help you with it because every phone is slightly different. You also need to ensure that the [images are signed for your device](https://github.com/swetland/omap4boot/issues/8#issuecomment-64971642).
* If you have taken backups, then two of the images should be 
* [l9 p760 p765 p768 p769](http://forum.xda-developers.com/showthread.php?t=2292828)
* [u-boot / omap4boot for P920/P720/P940 and its variant](http://forum.xda-developers.com/showthread.php?t=1971014)
* @swetland's [omap4boot](https://github.com/swetland/omap4boot) will build generic images, but you need to get the u-boot it builds signed.
* [possibly bad information on rolling your own](http://xda-university.com/as-a-developer/introduction-how-an-android-rom-is-built) from xda-university.
The 2nd stage images are all pretty much identical, so once you find one that works you can just stick with it. It's the U-Boot images that are more interesting; some U-Boots have fastboot; some have S/W update mode; some cryptographically enforce content.

With images in hand, you can boot your device on them by doing the following: 
* Pull all power from your device (i.e. take out the battery and unplug the USB cable)
* Plug in the usb cable with the battery still out. You should see a device attaching and detaching in dmesg(8) or in the Windows Device Manager.
* run the program: `omapboot aboot.bin uboot.bin`
```
[kousu@birdlikeplant omapboot]$ python omapboot.py images/lelus/p940-aboot.2nd images/lelus/p940-u-boot_fastboot.bin 
Waiting for omap44 device. Make sure you start with the battery out.
Uploading x-loader...done.
Giving x-loader a chance to come up...
Received boot banner ("0xAABBCCDD") from x-loader.
Insert battery and press enter to upload u-boot > [ENTER]
Uploading u-boot... done.
```
* Then you should be able to poke at your device with the [fastboot protocol]()
```
[kousu@birdlikeplant omapboot]$ fastboot getvar version
version: 0.5
finished. total time: 0.000s
```

You could also roll your own u-boot images to do whatever you need. 

There's a `-a` command line option which will skip the "Insert battery" line if you think you can be fast enough with your hands. (TODO: document this better).

Troubleshooting
---------------

* Check your cables and try again. This is hardware we're dealing with, afterall.
* If you're on OpenBSD, make sure you have no other ugen(4) devices active (I'll fix this, but right now I just have to say sorry)
* If the device is not responding at all, try uncommenting the ASIC ID lines to ensure you're talking to the right thing
* If the device is dropping you after x-loader uploads, try tweaking `sleep(1)` in `OMAP.boot()` and file a bug report, please.

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

* TI's [flash.exe](https://gforge.ti.com/gf/project/flash) and [poorly named wiki page](http://processors.wiki.ti.com/index.php/Flash_v1.0_User_Guide), particularly the file [pheriphalboot.c](https://gforge.ti.com/gf/project/flash/scmsvn/?action=browse&path=%2Ftrunk%2Fomapflash%2Fhost%2Fpheriphalboot.c) 
* [@swetland's omap4boot](https://github.com/swetland/omap4boot), helped out by [@wkpark](https://github.com/wkpark) and [@dimitry](https://github.com/dmitry-pervushin/usbboot-omap4)
* [Kuisma's every-root guide](http://whiteboard.ping.se/Android/Rooting) (this is really just "how to install your own OS on an ARM system", with rooting an Android as an immediate corrollary).
* [Android's code](https://android.googlesource.com/) -- did you know you can download snippets of Android's code? The entire project is huuuuge, but this site will package any subfolder for you at a click, and with a bit of ingenuity you can get most tools built.
* I would link XDA, but there's nothing decent there that isn't wkpark's stuff.