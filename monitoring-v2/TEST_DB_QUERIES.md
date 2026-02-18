# Database Testing Queries

## Connect to Database

```bash
docker exec -it monitoring-postgres psql -U monitoring -d monitoring
```

Or run queries directly:
```bash
docker exec -it monitoring-postgres psql -U monitoring -d monitoring -c "YOUR_QUERY_HERE"
```

## 1. Check if Table Exists

```sql
\dt
-- Should show: ai_results

-- Or check table structure:
\d ai_results
```

## 2. View Table Schema

```sql
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'ai_results'
ORDER BY ordinal_position;
```

## 3. Insert Test Data

```sql
INSERT INTO ai_results (
    study_uid,
    study_id,
    series_id,
    accession_number,
    patient_id,
    patient_name,
    study_date,
    study_description,
    results,
    measurements,
    processing_time_seconds,
    models_used,
    input_file_path,
    output_directory
) VALUES (
    '1.2.3.4.5.6.7.8.9.0',  -- study_uid (DICOM StudyInstanceUID)
    'orthanc-study-123',      -- study_id (Orthanc ID, optional)
    '1.2.3.4.5.6.7.8.9.1',  -- series_id (DICOM SeriesInstanceUID)
    'TEST001',                -- accession_number
    'TEST_PATIENT_001',       -- patient_id
    'Test^Patient',           -- patient_name
    '2024-02-18',            -- study_date
    'EXTREMITY BILATERAL BONE LENGTH',  -- study_description
    '{
        "results": {
            "measurements": {
                "left_femur": 100.5,
                "right_femur": 102.3,
                "left_tibia": 80.2,
                "right_tibia": 81.0,
                "left_total": 180.7,
                "right_total": 183.3,
                "difference": 2.6
            },
            "models_used": ["rn50adncti", "rn50adkpncti"],
            "confidence_scores": [0.95, 0.92, 0.88, 0.91]
        },
        "metadata": {
            "processing_time": 2.5,
            "timestamp": "2024-02-18T10:00:00Z",
            "input_file": "/path/to/input.dcm"
        }
    }'::jsonb,  -- results (full JSONB)
    '{
        "left_femur": 100.5,
        "right_femur": 102.3,
        "left_tibia": 80.2,
        "right_tibia": 81.0
    }'::jsonb,  -- measurements (extracted)
    2.5,        -- processing_time_seconds
    ARRAY['rn50adncti', 'rn50adkpncti'],  -- models_used
    '/tmp/input.dcm',  -- input_file_path
    '/tmp/output'      -- output_directory
);
```

## 4. Query by study_uid (Primary Lookup)

```sql
SELECT 
    study_uid,
    accession_number,
    patient_name,
    study_date,
    processing_time_seconds,
    timestamp,
    results->'results'->'measurements' as measurements
FROM ai_results
WHERE study_uid = '1.2.3.4.5.6.7.8.9.0';
```

## 5. Query by Orthanc study_id

```sql
SELECT 
    study_uid,
    study_id,
    accession_number,
    patient_name,
    timestamp
FROM ai_results
WHERE study_id = 'orthanc-study-123';
```

## 6. Query by Accession Number

```sql
SELECT 
    study_uid,
    accession_number,
    patient_name,
    study_date,
    timestamp
FROM ai_results
WHERE accession_number = 'TEST001'
ORDER BY timestamp DESC;
```

## 7. Query by Series ID

```sql
SELECT 
    study_uid,
    series_id,
    accession_number,
    timestamp
FROM ai_results
WHERE series_id = '1.2.3.4.5.6.7.8.9.1';
```

## 8. Query JSONB Fields (Measurements)

```sql
-- Get all studies with left_femur > 100
SELECT 
    study_uid,
    accession_number,
    measurements->>'left_femur' as left_femur,
    measurements->>'right_femur' as right_femur
FROM ai_results
WHERE (measurements->>'left_femur')::float > 100.0;
```

## 9. Query Inside results JSONB

```sql
-- Get measurements from nested JSON
SELECT 
    study_uid,
    accession_number,
    results->'results'->'measurements'->>'left_femur' as left_femur,
    results->'results'->'measurements'->>'right_femur' as right_femur,
    results->'results'->'measurements'->>'difference' as difference
FROM ai_results
WHERE results->'results'->'measurements'->>'difference' IS NOT NULL;
```

## 10. List Recent Results

```sql
SELECT 
    study_uid,
    accession_number,
    patient_name,
    study_date,
    processing_time_seconds,
    timestamp
FROM ai_results
ORDER BY timestamp DESC
LIMIT 10;
```

## 11. Count Results by Date

```sql
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as count
FROM ai_results
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

## 12. Get Full Result JSON

```sql
-- Get complete results.json for a study
SELECT 
    study_uid,
    accession_number,
    results
FROM ai_results
WHERE study_uid = '1.2.3.4.5.6.7.8.9.0';
```

## 13. Update Existing Result (Re-processing)

```sql
-- Update results for a study (ON CONFLICT will handle this automatically in code)
UPDATE ai_results
SET 
    results = '{"results": {"measurements": {"left_femur": 101.0}}}'::jsonb,
    timestamp = NOW()
WHERE study_uid = '1.2.3.4.5.6.7.8.9.0';
```

## 14. Delete Test Data

```sql
-- Delete test record
DELETE FROM ai_results WHERE study_uid = '1.2.3.4.5.6.7.8.9.0';

-- Or delete all test data
DELETE FROM ai_results WHERE accession_number LIKE 'TEST%';
```

## 15. Check Indexes

```sql
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'ai_results';
```

## 16. View Table Statistics

```sql
SELECT 
    COUNT(*) as total_records,
    MIN(timestamp) as oldest_record,
    MAX(timestamp) as newest_record,
    AVG(processing_time_seconds) as avg_processing_time
FROM ai_results;
```

## 17. Search by Patient Name

```sql
SELECT 
    study_uid,
    accession_number,
    patient_name,
    patient_id,
    study_date
FROM ai_results
WHERE patient_name ILIKE '%test%'
ORDER BY timestamp DESC;
```

## 18. Get Studies with Specific Models

```sql
SELECT 
    study_uid,
    accession_number,
    models_used
FROM ai_results
WHERE 'rn50adncti' = ANY(models_used);
```

## Quick One-Liners

```bash
# Count total records
docker exec -it monitoring-postgres psql -U monitoring -d monitoring -c "SELECT COUNT(*) FROM ai_results;"

# List all study_uids
docker exec -it monitoring-postgres psql -U monitoring -d monitoring -c "SELECT study_uid, accession_number, timestamp FROM ai_results ORDER BY timestamp DESC LIMIT 5;"

# Check if table exists
docker exec -it monitoring-postgres psql -U monitoring -d monitoring -c "\d ai_results"

# View recent results
docker exec -it monitoring-postgres psql -U monitoring -d monitoring -c "SELECT study_uid, accession_number, timestamp FROM ai_results ORDER BY timestamp DESC LIMIT 10;"
```
