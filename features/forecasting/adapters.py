"""Adapter from raw backend ledger dicts to LedgerRow.

Fill once the real ledger field names are known.
"""
from .models import LedgerRow


def from_rows(raw):
    raise NotImplementedError("adapter stub — fill once ledger field names are known")
    