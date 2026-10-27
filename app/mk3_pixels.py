"""Optional native display-only acceleration; portable fallback stays valid."""
import os
import ctypes as C
from pathlib import Path
try:
 if os.environ.get('MACHINISTA_MK3_NATIVE')!='1':raise OSError('Native display acceleration pending reboot investigation')
 lib=C.CDLL(str(Path(__file__).resolve().parents[1]/'build/mk3_pixels.so'))
 lib.machinista_rgb565.argtypes=[C.c_char_p,C.c_void_p,C.c_size_t,C.c_int];lib.machinista_rgb565.restype=None
 lib.machinista_mk3_runs.argtypes=[C.c_char_p,C.c_size_t,C.c_void_p,C.c_size_t];lib.machinista_mk3_runs.restype=C.c_size_t
except (OSError,AttributeError):lib=None

def pack(rgb,invert=False):
 if lib is None:return None
 if len(rgb)%3:raise ValueError('Invalid RGB image')
 out=C.create_string_buffer(len(rgb)//3*2)
 lib.machinista_rgb565(rgb,out,len(rgb)//3,int(invert));return out.raw

def encode(pixels):
 if lib is None:return None
 if len(pixels)%4:raise ValueError('Invalid pixel-pair data')
 out=C.create_string_buffer(len(pixels)*2+4)
 count=lib.machinista_mk3_runs(pixels,len(pixels),out,len(out))
 if not count:raise ValueError('MK3 encoder capacity')
 result=out.raw[:count]
 return result if len(result)<len(pixels)+4 else None
