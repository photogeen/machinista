"""Static display-only illustrations. Decode each native-size asset once."""
from functools import lru_cache
from pathlib import Path

KINDS=frozenset(('machinista-synth','generic-synth','generic-filter'))

def image(kind):
    if kind not in KINDS:return None
    return _image(kind)

@lru_cache(maxsize=3)
def _image(kind):
    from PIL import Image
    try:
        with Image.open(Path(__file__).resolve().parents[1]/'assets/instrument-art'/(kind+'.png')) as source:
            if source.size!=(448,120):return None
            return source.convert('RGBA')
    except OSError:return None
