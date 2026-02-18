-- Monitoring Database - AI Results Storage
-- Stores results.json from AI inference, queryable by study_id

CREATE TABLE IF NOT EXISTS ai_results (
    id SERIAL PRIMARY KEY,
    study_uid VARCHAR(255) NOT NULL,          -- DICOM StudyInstanceUID (primary lookup)
    study_id VARCHAR(255),                    -- Orthanc study ID (if available)
    series_id VARCHAR(255),                   -- DICOM SeriesInstanceUID
    accession_number VARCHAR(255),            -- DICOM AccessionNumber
    patient_id VARCHAR(255),                  -- DICOM PatientID
    patient_name VARCHAR(255),                -- DICOM PatientName
    study_date DATE,                          -- DICOM StudyDate
    study_description TEXT,                   -- DICOM StudyDescription
    
    -- Full results.json stored as JSONB
    results JSONB NOT NULL,
    
    -- Extracted measurements for easy querying (also in results, but indexed here)
    measurements JSONB,
    
    -- Processing metadata
    processing_time_seconds FLOAT,
    models_used TEXT[],
    timestamp TIMESTAMP DEFAULT NOW(),
    
    -- File paths (for reference)
    input_file_path TEXT,
    output_directory TEXT
);

-- Unique index on study_uid (allows ON CONFLICT updates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_results_study_uid ON ai_results(study_uid);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_ai_results_study_id ON ai_results(study_id);
CREATE INDEX IF NOT EXISTS idx_ai_results_accession ON ai_results(accession_number);
CREATE INDEX IF NOT EXISTS idx_ai_results_series_id ON ai_results(series_id);
CREATE INDEX IF NOT EXISTS idx_ai_results_timestamp ON ai_results(timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_results_patient_id ON ai_results(patient_id);

-- GIN index for JSONB queries (allows querying inside the JSON structure)
CREATE INDEX IF NOT EXISTS idx_ai_results_results_gin ON ai_results USING GIN (results);
CREATE INDEX IF NOT EXISTS idx_ai_results_measurements_gin ON ai_results USING GIN (measurements);

-- Comments
COMMENT ON TABLE ai_results IS 'Stores complete AI inference results (results.json) from leg length analysis';
COMMENT ON COLUMN ai_results.study_uid IS 'DICOM StudyInstanceUID - primary lookup key';
COMMENT ON COLUMN ai_results.study_id IS 'Orthanc study ID (if available)';
COMMENT ON COLUMN ai_results.results IS 'Complete results.json stored as JSONB';
COMMENT ON COLUMN ai_results.measurements IS 'Extracted measurements for easy querying';
