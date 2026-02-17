"""
Metric Calculators
------------------
This file contains the logic for extracting metrics from raw monitoring events.
To add a new metric:
1. Define a function that takes an `event` (dict) and returns a dictionary of metrics.
2. Add your function to the `CALCULATORS` list at the bottom.
"""

from typing import Dict, Any, List

def calculate_operational_metrics(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts basic operational metrics like processing time and status.
    """
    metrics = {}
    
    # 1. Status (0=Fail, 1=Success)
    status_code = event.get('status', {}).get('code', 'unknown')
    metrics['success'] = 1 if status_code == 'success' else 0
    metrics['failure'] = 1 if status_code == 'failed' else 0
    
    # 2. Processing Time
    timings = event.get('timings', {})
    if 'total_processing' in timings:
        metrics['processing_duration_seconds'] = timings['total_processing']
        
    return metrics

def calculate_clinical_metrics(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts clinical metrics like confidence scores and measurements.
    """
    metrics = {}
    derived = event.get('derived_results', {})
    
    # 1. Confidence Score
    if 'confidence_score' in derived:
        metrics['model_confidence'] = derived['confidence_score']
        
    # 2. Measurements (Example: Total Length)
    # Note: We flatten the structure for easier DB ingestion (e.g. InfluxDB fields)
    for side in ['left', 'right']:
        side_data = derived.get(side, {})
        if side_data and side_data.get('total_length_mm'):
            metrics[f'{side}_total_length_mm'] = side_data['total_length_mm']
            
    return metrics

def calculate_uncertainty_metrics(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example of a more complex calculator.
    Here you could implement custom logic to calculate uncertainty 
    from the 'raw_predictions' field if you wanted to.
    """
    metrics = {}
    
    # Example: Just checking if we have raw predictions
    raw_preds = event.get('raw_predictions', {})
    metrics['ensemble_member_count'] = len(raw_preds)
    
    # TODO: Add your custom variance/DDS calculation here using raw_preds
    
    return metrics

# =============================================================================
# REGISTER YOUR CALCULATORS HERE
# =============================================================================
CALCULATORS = [
    calculate_operational_metrics,
    calculate_clinical_metrics,
    calculate_uncertainty_metrics
]
