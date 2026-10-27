"""Display-only transliteration; never changes paths, patches or saved names."""
from functools import lru_cache
import unicodedata

_ALIASES=str.maketrans({'‘':"'",'’':"'",'“':'"','”':'"','–':'-','—':'-',
    '−':'-','…':'...','ø':'o','Ø':'O','æ':'ae','Æ':'AE','œ':'oe','Œ':'OE',
    'ß':'ss','ł':'l','Ł':'L','♯':'#','♭':'b','→':'>','←':'<','×':'x','°':' DEG'})

@lru_cache(maxsize=2048)
def display_text(value):
    """Printable LCD text with readable accents and no unknown-glyph markers.

    Real question marks (e.g. confirmation dialogs) remain question marks.
    Characters without a Latin approximation become a space, never '?'.
    """
    value=unicodedata.normalize('NFKD',value.translate(_ALIASES))
    return ''.join(c if ' '<=c<='~' else ' ' for c in value if not unicodedata.combining(c))
