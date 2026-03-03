# Mercure Pediatric Leg Length Monitoring Module - Design Proposal

## Goal
Design a monitoring module that supports robust monitoring of the pediatric leg length analysis pipeline while minimizing "bloat" in result storage and system complexity. We will **leverage the existing InfluxDB and Prometheus clients** but refactor the orchestration to be more flexible and efficient.

## Core Philosophy: "Store Raw, Publish Aggregates"

To satisfy the requirement of **decoupling results generation from analysis**, we adopt a two-stage approach:

1.  **Generation Phase (The "Recorder")**: The inference pipeline's *only* monitoring responsibility is to dump the full, raw context (coordinates, ensemble predictions, timings) into a standardized **Monitoring Event Archive** on the filesystem.
2.  **Analysis Phase (The "Processor")**: A separate logical component reads these archives, applies the *current* monitoring logic (e.g., calculating ensemble uncertainty), and publishes the resulting lightweight metrics to the databases.

## What is Stored? (The Monitoring Event Schema)

The **Monitoring Event Archive** is a JSON file containing the complete raw state of a processing session. This allows for full reproducibility and future re-analysis.

### JSON Structure Example

```json
{
  "metadata": {
    "event_id": "uuid-v4",
    "session_id": "1.2.840.113619.2.55.3.2831178555.768",
    "timestamp": "2023-10-27T14:30:00Z",
    "app_version": "0.2.0",
    "model_version": "ensemble_v1"
  },
  "context": {
    "scanner_manufacturer": "GE MEDICAL SYSTEMS",
    "pixel_spacing": [0.143, 0.143],
    "image_size": [2048, 1024],
    "patient_age_group": "8-18",  // Derived, non-PII
    "patient_sex": "F"            // Derived, non-PII
  },
  "timings": {
    "total_processing": 4.25,
    "inference": 3.10,
    "measurement_calculation": 0.05,
    "dicom_generation": 0.55
  },
  "raw_predictions": {
    // CRITICAL: Store raw outputs from EACH model in the ensemble
    "resnet101": {
      "boxes": [[100, 100, 200, 200], ...],
      "labels": [1, 2, ...],
      "scores": [0.98, 0.95, ...]
    },
    "vit_l_16": {
      "boxes": [[102, 101, 202, 201], ...],
      "labels": [1, 2, ...],
      "scores": [0.92, 0.89, ...]
    }
  },
  "derived_results": {
    "femur_length_mm": 450.5,
    "tibia_length_mm": 380.2,
    "total_length_mm": 830.7,
    "confidence_score": 0.95
  },
  "status": {
    "code": "success",
    "errors": []
  }
}
```

### Why this structure?
1.  **`raw_predictions`**: Contains the exact coordinates from every model. This is the source for calculating **Ensemble Uncertainty**. If you change the uncertainty formula later, you can re-run analysis on these files.
2.  **`context`**: Contains `pixel_spacing`, essential for converting pixel coordinates to physical measurements (mm) during re-analysis.
3.  **`derived_results`**: The final values sent to the PACS. Useful for quick sanity checks.

## Architecture

### 1. The `MonitoringEvent` (The Source of Truth)
A standardized JSON structure stored on disk (e.g., `monitoring_events/session_123.json`).

### 2. The `MonitorManager` (The Coordinator)
Refactored to handle the two stages.

*   **Stage 1: `archive_session()`**
    *   Called by `run.py` at the end of inference.
    *   Serializes the `MonitoringEvent` to a local JSONL file (rotated daily).
    *   *This is the only mandatory step.*

*   **Stage 2: `analyze_and_publish()`**
    *   Can be run immediately after archiving (synchronous) or by a background cron job (asynchronous).
    *   Reads the `MonitoringEvent`.
    *   Runs a chain of **Analyzers**.
    *   Dispatches results to **Backends**.

### 3. The Analyzers (The Logic)
Small, focused classes that extract metrics from the raw event.
*   **`PerformanceAnalyzer`**: Extracts latency, throughput.
*   **`UncertaintyAnalyzer`**: Uses the raw ensemble coordinates to calculate variance, disagreement scores, etc. *This logic can change over time without losing data.*
*   **`ClinicalAnalyzer`**: Checks bounds (e.g., "Femur length > 50cm?").

### 4. The Backends (The Destination)
Wrappers around your existing clients. They receive only the *outputs* of the Analyzers.
*   **`InfluxDBBackend`**: Receives time-series metrics (e.g., `uncertainty_score=0.4`).
*   **`PrometheusBackend`**: Receives operational counters (e.g., `studies_processed_total`).

## Configuration Schema (`task.json`)

```json
"monitoring": {
    "enabled": true,
    "mode": "sync", // "sync" (analyze immediately) or "archive_only" (analyze later)
    "archive_path": null, // If null, uses MONITORING_DATA_PATH env var (default: /var/log/mercure/events)
    "backends": {
        "influxdb": { "enabled": true, ... },
        "prometheus": { "enabled": true, ... }
    }
}
```

## Storage Configuration

The location of the **Monitoring Event Archive** is critical.
1.  **Environment Variable**: `MONITORING_DATA_PATH` (defined in `config.env`).
    *   This is the preferred method for containerized deployments.
    *   Example: `/home/data/monitoring-events` (mounted to container).
2.  **Task Config**: `monitoring.archive_path` in `task.json`.
    *   Overrides the environment variable if set.
3.  **Default**: `/var/log/mercure/monitoring_events` if neither is set.

## Implementation Plan

1.  **Define `MonitoringEvent` Schema**: Create a Pydantic model or TypedDict to strictly define what goes into the archive.
2.  **Refactor `MonitorManager`**:
    *   Remove direct metric calculation methods.
    *   Add `create_event(...)` and `save_event(...)`.
    *   Add `process_event(...)` which orchestrates the Analyzers.
3.  **Implement Analyzers**: Move the logic from `metrics_collector.py` into separate Analyzer classes.
4.  **Update `run.py`**: Change calls from `record_metric` to `archive_session`.

This design achieves your goal: **Raw coordinates are stored (in files) for future flexibility, but decoupled from the monitoring DBs to prevent bloat.**
