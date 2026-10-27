"""Small libusb transport for the full MK1; no third-party Python dependency.

Only claims 17cc:0808 interface zero. Detaches/re-attaches that device's caiaq
kernel driver; it never resets the USB bus or modifies another controller.
All calls have bounded timeouts. Caller must keep this off the audio thread.
"""
import ctypes as C
import ctypes.util
import warnings
from app.mk1_protocol import VID,PID

class Mk1USB:
    def __init__(self):
        self.lib=C.CDLL(ctypes.util.find_library('usb-1.0') or 'libusb-1.0.so.0')
        signatures={
          'init':([C.POINTER(C.c_void_p)],C.c_int),
          'exit':([C.c_void_p],None),
          'open_device_with_vid_pid':([C.c_void_p,C.c_uint16,C.c_uint16],C.c_void_p),
          'close':([C.c_void_p],None),
          'kernel_driver_active':([C.c_void_p,C.c_int],C.c_int),
          'detach_kernel_driver':([C.c_void_p,C.c_int],C.c_int),
          'attach_kernel_driver':([C.c_void_p,C.c_int],C.c_int),
          'claim_interface':([C.c_void_p,C.c_int],C.c_int),
          'release_interface':([C.c_void_p,C.c_int],C.c_int),
          'set_interface_alt_setting':([C.c_void_p,C.c_int,C.c_int],C.c_int),
          'bulk_transfer':([C.c_void_p,C.c_ubyte,C.c_void_p,C.c_int,C.POINTER(C.c_int),C.c_uint],C.c_int),
          'error_name':([C.c_int],C.c_char_p)}
        for name,(args,result) in signatures.items():
            fn=getattr(self.lib,'libusb_'+name);fn.argtypes=args;fn.restype=result
        self.context=C.c_void_p();self.handle=None;self.detached=self.claimed=False
        self.check(self.lib.libusb_init(C.byref(self.context)))
        try:
            self.handle=self.lib.libusb_open_device_with_vid_pid(self.context,VID,PID)
            if not self.handle:raise OSError('MK1 unavailable or USB permission denied')
            if self.lib.libusb_kernel_driver_active(self.handle,0)==1:
                self.check(self.lib.libusb_detach_kernel_driver(self.handle,0));self.detached=True
            self.check(self.lib.libusb_claim_interface(self.handle,0));self.claimed=True
            self.check(self.lib.libusb_set_interface_alt_setting(self.handle,0,1))
        except BaseException:self.close();raise
    def check(self,result):
        if result<0:raise OSError(self.lib.libusb_error_name(result).decode())
        return result
    def write(self,endpoint,data):
        if endpoint not in (1,8):raise ValueError('invalid MK1 output endpoint')
        buffer=C.create_string_buffer(data);done=C.c_int()
        self.check(self.lib.libusb_bulk_transfer(self.handle,endpoint,buffer,len(data),C.byref(done),200))
        if done.value!=len(data):raise OSError('short MK1 USB write')
    def read(self,endpoint,timeout=10):
        if endpoint not in (0x81,0x84):raise ValueError('invalid MK1 input endpoint')
        buffer=C.create_string_buffer(512);done=C.c_int()
        result=self.lib.libusb_bulk_transfer(self.handle,endpoint,buffer,512,C.byref(done),timeout)
        if result==-7:return b''
        self.check(result);return buffer.raw[:done.value]
    def close(self):
        if self.handle:
            if self.claimed:self.lib.libusb_release_interface(self.handle,0)
            if self.detached:
                self.lib.libusb_set_interface_alt_setting(self.handle,0,0)
                result=self.lib.libusb_attach_kernel_driver(self.handle,0)
                if result<0:warnings.warn('MK1 kernel reattach: '+self.lib.libusb_error_name(result).decode())
            self.lib.libusb_close(self.handle);self.handle=None
        if self.context:self.lib.libusb_exit(self.context);self.context=C.c_void_p()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
