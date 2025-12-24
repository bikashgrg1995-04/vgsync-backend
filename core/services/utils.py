# core/utils.py
import re

def extract_item_no(value):
    """
    Extract actual item_no from Excel cell.
    Handles:
    - BP-123
    - Brake Pad (BP-123)
    - extra spaces
    """
    if not value:
        return ""
    value = str(value).strip()
    match = re.search(r"\((.*?)\)", value)
    if match:
        return match.group(1).strip()
    return value
