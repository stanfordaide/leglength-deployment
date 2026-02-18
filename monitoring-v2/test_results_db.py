#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Add mercure-pediatric-leglength to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mercure-pediatric-leglength"))

from monitoring import ResultsDBClient

# Set connection details
os.environ["MONITORING_DB_HOST"] = "172.17.0.1"
os.environ["MONITORING_DB_PORT"] = "9042"
os.environ["MONITORING_DB_NAME"] = "monitoring"
os.environ["MONITORING_DB_USER"] = "monitoring"
os.environ["MONITORING_DB_PASS"] = "monitoring123"

# Test data
test_results = {
    "results": {
        "measurements": {
            "left_femur": 100.5,
            "right_femur": 102.3,
            "left_tibia": 80.2,
            "right_tibia": 81.0
        },
        "models_used": ["rn50adncti", "rn50adkpncti"]
    },
    "metadata": {
        "processing_time": 2.5,
        "timestamp": "2024-02-18T10:00:00Z"
    }
}

# Test storage
client = ResultsDBClient(enabled=True)
if client.enabled:
    print("✅ Client initialized")
    
    # Store test result
    success = client.store_result(
        study_uid="1.2.3.4.5.6.7.8.9.0",
        results_json=test_results,
        series_id="1.2.3.4.5.6.7.8.9.1",
        accession_number="TEST001",
        patient_id="TEST_PATIENT",
        patient_name="Test Patient",
        processing_time_seconds=2.5
    )
    
    if success:
        print("✅ Successfully stored test result")
        
        # Retrieve it
        retrieved = client.get_by_study_uid("1.2.3.4.5.6.7.8.9.0")
        if retrieved:
            print("✅ Successfully retrieved result")
            print(f"   Measurements: {retrieved.get('results', {}).get('measurements', {})}")
        else:
            print("❌ Failed to retrieve result")
    else:
        print("❌ Failed to store result")
    
    client.close()
else:
    print("❌ Client not enabled - check connection settings")
