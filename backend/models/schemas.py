# backend/models/schemas.py
# Pydantic models define the shape of data going in/out of the API.

from pydantic import BaseModel
from typing import List


class DetectionResult(BaseModel):
    product_class: str
    confidence: float
    bbox: List[float]            # [x1, y1, x2, y2] in pixels
    facings_count: int           # how many of this class seen so far in frame
    estimated_total: int         # facings * estimated depth multiplier
    severity: str                 # full / low / critical / empty
