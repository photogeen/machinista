"""Bounded display-only USB transport: claim interface5, never audio/MIDI/DFU."""
import ctypes as C,ctypes.util
class DisplayUSB:
 def __init__(self,product=0x1600,interface=5):
  if (product,interface) not in ((0x1600,5),(0x1820,6)):raise ValueError('Unsupported color controller transport')
  self.interface=interface
  self.lib=C.CDLL(ctypes.util.find_library('usb-1.0') or 'libusb-1.0.so.0');self.context=C.c_void_p();self.handle=None;self.claimed=False
  signatures={'init':([C.POINTER(C.c_void_p)],C.c_int),'exit':([C.c_void_p],None),'open_device_with_vid_pid':([C.c_void_p,C.c_uint16,C.c_uint16],C.c_void_p),'close':([C.c_void_p],None),'claim_interface':([C.c_void_p,C.c_int],C.c_int),'release_interface':([C.c_void_p,C.c_int],C.c_int),'bulk_transfer':([C.c_void_p,C.c_ubyte,C.c_void_p,C.c_int,C.POINTER(C.c_int),C.c_uint],C.c_int),'error_name':([C.c_int],C.c_char_p)}
  for name,(args,result) in signatures.items():fn=getattr(self.lib,'libusb_'+name);fn.argtypes=args;fn.restype=result
  self.check(self.lib.libusb_init(C.byref(self.context)))
  try:
   self.handle=self.lib.libusb_open_device_with_vid_pid(self.context,0x17cc,product)
   if not self.handle:raise OSError('MK3 display USB unavailable')
   self.check(self.lib.libusb_claim_interface(self.handle,self.interface));self.claimed=True
  except BaseException:self.close();raise
 def check(self,value):
  if value<0:raise OSError(self.lib.libusb_error_name(value).decode())
 def send(self,packet):
  buffer=C.create_string_buffer(packet);done=C.c_int();self.check(self.lib.libusb_bulk_transfer(self.handle,4,buffer,len(packet),C.byref(done),300))
  if done.value!=len(packet):raise OSError('Short MK3 display write')
 def close(self):
  if self.handle:
   if self.claimed:self.lib.libusb_release_interface(self.handle,self.interface)
   self.lib.libusb_close(self.handle);self.handle=None
  if self.context:self.lib.libusb_exit(self.context);self.context=C.c_void_p()
