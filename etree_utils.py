"""
etree_utils.py — safe shim so your code can do:
    from etree_utils import Element, ElementTree, tostring, iselement, parse, fromstring, SubElement, XML, XMLParser, ElementTree as ET

It prefers lxml.etree (faster, richer) but falls back to the stdlib xml.etree.ElementTree.
"""

# Try lxml first
try:  # pragma: no cover
    from lxml.etree import *  # re-export everything users typically import
    LXML_AVAILABLE = True
except Exception:  # pragma: no cover
    LXML_AVAILABLE = False
    from xml.etree.ElementTree import *  # type: ignore[assignment]

__all__ = [name for name in globals().keys() if not name.startswith("_")]
