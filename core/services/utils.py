# core/utils.py
import re

from django.utils import timezone
from datetime import datetime


import math
import numpy as np


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


def make_aware_if_needed(dt):
    if isinstance(dt, datetime) and timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def clean_excel_value(value):
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    if isinstance(value, np.floating) and np.isnan(value):
        return None

    return value

def excel_bool(val):
    if val in [True, 1, "1", "TRUE", "true", "Yes", "yes"]:
        return True
    return False