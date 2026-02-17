"""
Monitoring event schema definition.
"""

from typing import Dict, Any, List, Optional, Union, TypedDict
from datetime import datetime

class Metadata(TypedDict):
    event_id: str
    session_id: str
    timestamp: str
    app_version: str
    model_version: str
    config_snapshot: Dict[str, Any]

class Context(TypedDict):
    scanner_manufacturer: str
    pixel_spacing: List[float]
    image_size: List[int]
    patient_age_group: str
    patient_sex: str
    study_id: str
    series_id: str
    accession_number: str

class Timings(TypedDict):
    total_processing: float
    inference: float
    measurement_calculation: float
    dicom_generation: float
    # Allow for other custom timings
    stages: Dict[str, float]

class ModelPrediction(TypedDict):
    boxes: List[List[float]]
    labels: List[int]
    scores: List[float]

class LegResults(TypedDict):
    femur_length_mm: Optional[float]
    tibia_length_mm: Optional[float]
    total_length_mm: Optional[float]

class DerivedResults(TypedDict):
    left: LegResults
    right: LegResults
    # Allow for other custom metrics
    metrics: Dict[str, Union[float, int, str]]

class Status(TypedDict):
    code: str  # 'success', 'failed', 'skipped'
    errors: List[str]

class MonitoringEvent(TypedDict):
    metadata: Metadata
    context: Context
    timings: Timings
    raw_predictions: Dict[str, ModelPrediction]
    derived_results: DerivedResults
    status: Status

# Mercure Result Schema (for result.json)
class MercureResult(TypedDict, total=False):
    """
    Schema for result.json expected by Mercure.
    """
    __mercure_notification: Dict[str, str] # Optional notification trigger
    # Any other fields are allowed and archived by Mercure
    event: MonitoringEvent 
