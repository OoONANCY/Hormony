"""Map the many ways labs print a test name onto one code + canonical name, so charts and comparisons line up."""
from __future__ import annotations

import re
from typing import Optional, Tuple

# code, canonical name, aliases (matched on a normalised name: lowercase, letters/digits/spaces only)
_ANALYTES = [
    ("P4", "Progesterone", ["progesterone", "prog", "p4", "serum progesterone"]),
    ("E2", "Estradiol", ["estradiol", "oestradiol", "e2", "estradiol e2", "oestradiol e2", "17 beta estradiol"]),
    ("TSH", "TSH", ["tsh", "thyroid stimulating hormone", "thyrotropin", "tsh 3rd generation", "ultrasensitive tsh"]),
    ("FT4", "Free T4", ["free t4", "ft4", "free thyroxine", "t4 free"]),
    ("FT3", "Free T3", ["free t3", "ft3", "free triiodothyronine", "t3 free"]),
    ("T4", "Total T4", ["total t4", "t4", "thyroxine", "t4 total"]),
    ("T3", "Total T3", ["total t3", "t3", "triiodothyronine", "t3 total"]),
    ("LH", "LH", ["lh", "luteinizing hormone", "luteinising hormone"]),
    ("FSH", "FSH", ["fsh", "follicle stimulating hormone"]),
    ("PRL", "Prolactin", ["prolactin", "prl"]),
    ("TT", "Testosterone", ["testosterone", "total testosterone", "testosterone total"]),
    ("FTT", "Free testosterone", ["free testosterone", "testosterone free"]),
    ("DHEAS", "DHEA-S", ["dhea s", "dheas", "dhea sulfate", "dhea sulphate", "dehydroepiandrosterone sulfate"]),
    ("SHBG", "SHBG", ["shbg", "sex hormone binding globulin"]),
    ("AMH", "AMH", ["amh", "anti mullerian hormone", "anti mullerian hormone amh"]),
    ("CORT", "Cortisol", ["cortisol", "serum cortisol", "morning cortisol"]),
    ("FER", "Ferritin", ["ferritin", "serum ferritin"]),
    ("IRON", "Iron", ["iron", "serum iron"]),
    ("TSAT", "Transferrin saturation", ["transferrin saturation", "tsat", "iron saturation"]),
    ("B12", "Vitamin B12", ["vitamin b12", "b12", "vit b12", "cobalamin", "cyanocobalamin"]),
    ("FOL", "Folate", ["folate", "folic acid", "serum folate"]),
    ("VITD", "Vitamin D (25-OH)", ["vitamin d", "25 oh vitamin d", "25 hydroxy vitamin d", "vitamin d 25 oh",
                                    "25 oh d", "vitamin d3", "25 hydroxyvitamin d"]),
    ("HB", "Hemoglobin", ["hemoglobin", "haemoglobin", "hb", "hgb"]),
    ("GLU", "Glucose", ["glucose", "fasting glucose", "fasting blood sugar", "fbs", "blood glucose"]),
    ("INS", "Insulin", ["insulin", "fasting insulin"]),
    ("HBA1C", "HbA1c", ["hba1c", "glycated hemoglobin", "glycated haemoglobin", "a1c", "hemoglobin a1c"]),
    ("CRP", "CRP", ["crp", "c reactive protein", "hs crp", "hscrp"]),
]
_LOOKUP = {alias: (code, name) for code, name, aliases in _ANALYTES for alias in aliases}


def _key(name: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", name.lower())          # "Oestradiol (E2)" -> "oestradiol"
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def normalize(name: str) -> Tuple[Optional[str], str]:
    """(code, canonical name) for a known test, else (None, the name as printed)."""
    key = _key(name)
    for candidate in (key, _key(re.sub(r"[()]", " ", name)), key.removeprefix("serum ").removeprefix("plasma ")):
        if candidate in _LOOKUP:
            return _LOOKUP[candidate]
    return None, name.strip()
