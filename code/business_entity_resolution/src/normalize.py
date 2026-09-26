"""Text normalization for entity resolution. Country-agnostic, transliteration-first.

Design is anchored to context/dataset_analysis.md:
  - transliterate Devanagari + fold accents (unidecode) so cross-script / French
    records canonicalize toward the Latin reference (S1).
  - strip legal suffixes for a `name_core` key (they carry no identity signal).
  - sort tokens in the core key so word-order transpositions still block together.
"""
import re
from unidecode import unidecode

# Legal-entity suffixes to drop from the core name (identity-neutral). Generic
# words like group/holdings/enterprises are kept — they distinguish businesses.
LEGAL_SUFFIX = {
    "corp", "corporation", "inc", "incorporated", "ltd", "limited", "pvt",
    "private", "llc", "llp", "plc", "co", "company", "gmbh", "sarl", "sas",
    "sa", "srl", "bv", "ag", "pte", "pl",
}

# Address abbreviation canonicalization (token-level).
ADDR_ABBR = {
    "rd": "road", "st": "street", "ave": "avenue", "av": "avenue",
    "blvd": "boulevard", "ln": "lane", "dr": "drive", "hwy": "highway",
    "ste": "suite", "apt": "apartment", "fl": "floor", "ph": "phase",
    "opp": "opposite", "flr": "floor", "bldg": "building", "sec": "sector",
}

_punct = re.compile(r"[^\w\s]", re.UNICODE)
_ws = re.compile(r"\s+")


def clean(s):
    """Lowercased, transliterated, punctuation-free, whitespace-collapsed string."""
    s = unidecode(s)
    s = s.lower().replace("&", " and ")
    s = _punct.sub(" ", s)
    return _ws.sub(" ", s).strip()


def tokens(s):
    """Token list of the cleaned string."""
    return clean(s).split()


def name_core(s):
    """Blocking key: sorted content tokens with legal suffixes removed.

    Sorting absorbs word-order transposition; suffix removal absorbs
    Corp/Ltd/Pvt variation. Empty when the name is only suffixes/punctuation.
    """
    toks = [t for t in clean(s).split() if t not in LEGAL_SUFFIX]
    return " ".join(sorted(set(toks)))


def name_tokens(s):
    """Content-token set of a name (legal suffixes dropped), for similarity/features."""
    return {t for t in clean(s).split() if t not in LEGAL_SUFFIX}


def addr_tokens(s):
    """Canonicalized address token set (abbreviations expanded)."""
    return {ADDR_ABBR.get(t, t) for t in clean(s).split()}


def demo():
    assert name_core("B+ Retail Inc") == name_core("Retail B")  # suffix + order
    assert name_core("Corp") == "" and name_core("Pvt Ltd") == ""
    assert clean("A & B") == "a and b"
    assert name_core("A & B Co") == name_core("B and A")
    assert "road" in addr_tokens("12 Main Rd") and "street" in addr_tokens("5 Elm St")
    assert name_core("École Française") == name_core("Ecole Francaise")
    print("normalize.demo OK")


if __name__ == "__main__":
    demo()
