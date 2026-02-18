# Results JSON Structure

The `results` column in the `ai_results` table stores the complete JSON structure saved to `result.json`. Here's the full structure:

## Top-Level Structure

```json
{
  "metadata": { ... },
  "configuration": { ... },
  "results": { ... }
}
```

## 1. `metadata` Section

```json
{
  "metadata": {
    "version": "v0.2.0",
    "module": "LPCH Pediatric Leg Length Analysis",
    "timestamp": "2024-02-18 10:00:00",
    "processing_time_seconds": 2.5,
    "input_file": "/path/to/input.dcm",
    "input_filename": "input.dcm",
    "series_id": "1.2.3.4.5.6.7.8.9.1",
    "accession_number": "ACC123456",
    "output_directory": "/path/to/output",
    "models_used": ["rn50adncti", "rn50adkpncti"]
  }
}
```

## 2. `configuration` Section

Contains all configuration parameters used for processing:

```json
{
  "configuration": {
    "models": ["rn50adncti", "rn50adkpncti"],
    "series_offset": 1000,
    "femur_threshold": 0.2,
    "tibia_threshold": 0.2,
    "total_threshold": 1.0,
    "confidence_threshold": 0.0,
    "results_db": {
      "enabled": true,
      "host": "172.17.0.1",
      "port": 9042,
      ...
    }
  }
}
```

## 3. `results` Section (Inference Results)

This contains the actual AI inference output:

### Single Model Mode

```json
{
  "results": {
    "boxes": [[x1, y1, x2, y2], ...],  // Bounding box coordinates for each detected landmark
    "scores": [0.95, 0.92, ...],        // Confidence scores for each detection
    "labels": [1, 2, 3, ...],           // Point labels (1-8 for anatomical landmarks)
    "measurements": {
      "left_femur": 100.5,              // mm
      "right_femur": 102.3,             // mm
      "left_tibia": 80.2,               // mm
      "right_tibia": 81.0,              // mm
      "left_total": 180.7,              // mm
      "right_total": 183.3,             // mm
      "difference": 2.6                 // mm
    },
    "issues": [],                       // Any problems or warnings
    "uncertainties": {},                // Empty for single model
    "point_statistics": {},             // Empty for single model
    "dicom_metadata": {
      "pixel_spacing": [0.1, 0.1],
      "slice_thickness": null,
      ...
    },
    "output_files": {
      "result_json": "/path/to/result.json",
      "qa_output": "/path/to/qa_output.dcm",
      "qa_table_output": "/path/to/qa_table_output.dcm",
      "qa_table_jpeg": "/path/to/qa_table_output.jpg"
    }
  }
}
```

### Ensemble Mode (Multiple Models)

```json
{
  "results": {
    "boxes": [[x1, y1, x2, y2], ...],
    "scores": [0.95, 0.92, ...],
    "labels": [1, 2, 3, ...],
    "measurements": {
      "left_femur": 100.5,
      "right_femur": 102.3,
      ...
    },
    "uncertainties": {
      "per_point_std": [0.5, 0.3, ...],  // Standard deviation per landmark
      "per_point_mean": [100.2, 102.1, ...],
      "overall_uncertainty": 0.4
    },
    "point_statistics": {
      "detection_counts": [8, 8, 7, ...],  // How many models detected each point
      "agreement_scores": [0.95, 0.92, ...]
    },
    "individual_model_predictions": {
      "rn50adncti": {
        "boxes": [[...], ...],
        "scores": [...],
        "labels": [...]
      },
      "rn50adkpncti": {
        "boxes": [[...], ...],
        "scores": [...],
        "labels": [...]
      }
    },
    "dicom_metadata": { ... },
    "output_files": { ... }
  }
}
```

## Landmark Labels (1-8)

The `labels` array uses these codes:
- 1: Left femur proximal
- 2: Left femur distal
- 3: Left tibia proximal
- 4: Left tibia distal
- 5: Right femur proximal
- 6: Right femur distal
- 7: Right tibia proximal
- 8: Right tibia distal

## Querying the JSON in PostgreSQL

### Get full JSON
```sql
SELECT results FROM ai_results WHERE study_uid = 'YOUR_STUDY_UID';
```

### Get measurements only
```sql
SELECT 
    study_uid,
    accession_number,
    results->'results'->'measurements' as measurements
FROM ai_results
WHERE study_uid = 'YOUR_STUDY_UID';
```

### Get specific measurement
```sql
SELECT 
    study_uid,
    results->'results'->'measurements'->>'left_femur' as left_femur,
    results->'results'->'measurements'->>'right_femur' as right_femur
FROM ai_results
WHERE study_uid = 'YOUR_STUDY_UID';
```

### Get processing metadata
```sql
SELECT 
    study_uid,
    results->'metadata'->>'timestamp' as processing_timestamp,
    results->'metadata'->>'processing_time_seconds' as processing_time,
    results->'metadata'->'models_used' as models_used
FROM ai_results
WHERE study_uid = 'YOUR_STUDY_UID';
```

### Get configuration used
```sql
SELECT 
    study_uid,
    results->'configuration'->'models' as models,
    results->'configuration'->>'femur_threshold' as femur_threshold
FROM ai_results
WHERE study_uid = 'YOUR_STUDY_UID';
```

### Pretty print full JSON
```sql
SELECT jsonb_pretty(results) 
FROM ai_results 
WHERE study_uid = 'YOUR_STUDY_UID';
```

### Find studies with specific measurements
```sql
-- Find studies with leg length difference > 5mm
SELECT 
    study_uid,
    accession_number,
    results->'results'->'measurements'->>'difference' as difference
FROM ai_results
WHERE (results->'results'->'measurements'->>'difference')::float > 5.0;
```

### Get all measurements for a patient
```sql
SELECT 
    study_uid,
    accession_number,
    results->'results'->'measurements' as measurements,
    results->'metadata'->>'timestamp' as timestamp
FROM ai_results
WHERE patient_id = 'PATIENT_123'
ORDER BY (results->'metadata'->>'timestamp')::timestamp DESC;
```
