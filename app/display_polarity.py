"""Final logical LCD polarity, independent of hardware pixel packing and LEDs."""
_INVERT=bytes(i^1 for i in range(256))
def pixels(frame,inverted=False):
    return bytes(frame).translate(_INVERT) if inverted else frame
