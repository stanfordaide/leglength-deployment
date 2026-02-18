# Testing Results Database Storage

## Prerequisites

1. **Monitoring stack running** (includes PostgreSQL):
   ```bash
   cd monitoring-v2
   make start
   # Or from project root:
   make monitoring-start
   ```

2. **Database initialized**: The schema is automatically created on first start via `init.sql`

3. **AI module dependencies**: Ensure `psycopg2-binary` is installed:
   ```bash
   cd mercure-pediatric-leglength
   pip install psycopg2-binary
   ```

## Test 1: Verify Database is Running

```bash
# Check if PostgreSQL container is running
docker ps | grep monitoring-postgres

# Check database connection
docker exec -it monitoring-postgres psql -U monitoring -d monitoring -c "\dt"
# Should show: ai_results table
```

## Test 2: Test ResultsDBClient Directly

Create a test script `test_results_db.py`:

```python
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Add mercure-pediatric-leglength to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mercure-pediatric-leglength"))

from monitoring import ResultsDBClient

# Set connection details
os.environ["MONITORING_DB_HOST"] = "172.17.0.1"  # Or your Docker gateway IP
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
        study_uid="1.2.3.4.5.6.7.8.9.0",  # Test StudyInstanceUID
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
```

Run it:
```bash
python test_results_db.py
```

## Test 3: Test with Actual AI Module

1. **Ensure Mercure is configured** with `results_db` settings in `mercure.json`:
   ```json
   "results_db": {
       "enabled": true,
       "host": "172.17.0.1",
       "port": 9042,
       "database": "monitoring",
       "user": "monitoring",
       "password": "monitoring123"
   }
   ```

2. **Process a study** through Mercure (or manually trigger the AI module)

3. **Check database**:
   ```bash
   docker exec -it monitoring-postgres psql -U monitoring -d monitoring -c "SELECT study_uid, accession_number, timestamp FROM ai_results ORDER BY timestamp DESC LIMIT 5;"
   ```

## Test 4: Query Results

Use the query tool:
```bash
cd monitoring-v2
python query_results.py <study_uid>
python query_results.py --study-id <orthanc_study_id>
python query_results.py --accession <accession_number>
```

## Troubleshooting

### Connection refused
- Check if PostgreSQL is running: `docker ps | grep postgres`
- Verify port 9042 is accessible: `telnet localhost 9042`
- Check Docker gateway IP: `docker exec <container> ip route | grep default`

### Authentication failed
- Verify credentials in `monitoring-v2/.env`
- Check database logs: `docker logs monitoring-postgres`

### Module not found
- Ensure `psycopg2-binary` is installed in the AI module environment
- Check Python path includes `mercure-pediatric-leglength`

### No study_uid in task.json
- Verify Mercure is generating task.json with `study.study_uid`
- Check task.json in the processing folder
