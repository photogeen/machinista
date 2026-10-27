"""Maschine+ controller mode; independent ownership/settings, shared color UI."""
from app.mk3_session import Mk3Session
from app.mk3_surface import Mk3Surface

class PlusSurface(Mk3Surface):
    source='plus'

class PlusSession(Mk3Session):
    source='plus';surface_type=PlusSurface
    product=0x1820;display_interface=6;device_name='Maschine+'
