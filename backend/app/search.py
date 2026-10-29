"""Turkish- and English-friendly text matching for search.

SQLite's LIKE ignores case for ASCII letters only, so "insan" would not match "İnsan".
Plain Turkish lowercasing is not enough either: it turns the English "AI" into "aı",
which "ai" would no longer match. So both the text and the query are folded to the
same search key: every I/İ/ı becomes "i" and accents are dropped (ş→s, ö→o, …),
which also lets people search without a Turkish keyboard.
"""

import unicodedata

# Dotted and dotless i are separate letters in Turkish; for search they are the same.
_I_VARIANTS = str.maketrans({"I": "i", "İ": "i", "ı": "i"})


def search_fold(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.translate(_I_VARIANTS).lower()
    # NFKD splits "ş" into "s" + a combining cedilla; dropping the combining marks
    # leaves the base letters.
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))
