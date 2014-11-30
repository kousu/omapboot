from . import pyusb
from . import ugen

__all__ = ["BulkUSB"]

if hasattr(pyusb, 'BulkUSB'):
    BulkUSB = pyusb.BulkUSB

if hasattr(ugen, 'BulkUSB'):
    BulkUSB = ugen.BulkUSB