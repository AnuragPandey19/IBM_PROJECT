"""Data ingestion, cleaning, splitting."""
from chimera_fd.data.loader import load_ieee_cis, load_sparkov
from chimera_fd.data.splitter import time_based_split

__all__ = ["load_ieee_cis", "load_sparkov", "time_based_split"]
