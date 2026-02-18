"""
PostgreSQL client for storing AI inference results.

Part of the monitoring module for pediatric leg length analysis.
Stores results.json in PostgreSQL JSONB format, queryable by study_uid (DICOM StudyInstanceUID).
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import Json
    from psycopg2.pool import SimpleConnectionPool
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)


class ResultsDBClient:
    """
    Client for storing and retrieving AI inference results.
    
    Usage:
        from monitoring import ResultsDBClient
        
        client = ResultsDBClient()
        client.store_result(study_uid="1.2.3.4.5", results_json={...})
        results = client.get_by_study_uid("1.2.3.4.5")
    """
    
    def __init__(self, enabled: bool = True):
        """
        Initialize database client.
        
        Args:
            enabled: If False, all operations are no-ops (for testing/development)
        """
        self.enabled = enabled and psycopg2 is not None
        self.pool = None
        
        if not self.enabled:
            if not psycopg2:
                logger.debug("psycopg2 not available - results DB disabled")
            else:
                logger.debug("Results DB client disabled")
            return
        
        # Get connection details from environment
        host = os.getenv("MONITORING_DB_HOST", "172.17.0.1")
        port = int(os.getenv("MONITORING_DB_PORT", "9042"))
        dbname = os.getenv("MONITORING_DB_NAME", "monitoring")
        user = os.getenv("MONITORING_DB_USER", "monitoring")
        password = os.getenv("MONITORING_DB_PASS", "monitoring123")
        
        try:
            # Create connection pool (min 1, max 5 connections)
            self.pool = SimpleConnectionPool(
                1, 5,
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password
            )
            logger.info(f"Results DB client initialized: {host}:{port}/{dbname}")
        except Exception as e:
            logger.warning(f"Failed to initialize Results DB client: {e}")
            self.enabled = False
            self.pool = None
    
    def _get_conn(self):
        """Get a connection from the pool."""
        if not self.enabled or not self.pool:
            return None
        try:
            return self.pool.getconn()
        except Exception as e:
            logger.error(f"Failed to get DB connection: {e}")
            return None
    
    def _put_conn(self, conn):
        """Return a connection to the pool."""
        if self.pool and conn:
            try:
                self.pool.putconn(conn)
            except Exception as e:
                logger.error(f"Failed to return DB connection: {e}")
    
    def store_result(
        self,
        study_uid: str,
        results_json: Dict[str, Any],
        study_id: Optional[str] = None,
        series_id: Optional[str] = None,
        accession_number: Optional[str] = None,
        **metadata
    ) -> bool:
        """
        Store a results.json in the database.
        
        Args:
            study_uid: DICOM StudyInstanceUID (required, primary key)
            results_json: Complete results.json dictionary
            study_id: Orthanc study ID (optional)
            series_id: DICOM SeriesInstanceUID (optional)
            accession_number: DICOM AccessionNumber (optional)
            **metadata: Additional metadata (patient_id, patient_name, etc.)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        if not study_uid:
            logger.error("store_result: study_uid is required")
            return False
        
        conn = self._get_conn()
        if not conn:
            return False
        
        try:
            cur = conn.cursor()
            
            # Extract measurements from results if available
            measurements = None
            if isinstance(results_json, dict):
                results_data = results_json.get('results', {})
                if isinstance(results_data, dict):
                    measurements = results_data.get('measurements', {})
            
            # Extract metadata from results_json if not provided
            metadata_dict = results_json.get('metadata', {}) if isinstance(results_json, dict) else {}
            
            # Prepare data
            data = {
                'study_uid': study_uid,
                'study_id': study_id or metadata_dict.get('study_id'),
                'series_id': series_id or metadata_dict.get('series_id'),
                'accession_number': accession_number or metadata_dict.get('accession_number'),
                'patient_id': metadata.get('patient_id') or metadata_dict.get('patient_id'),
                'patient_name': metadata.get('patient_name') or metadata_dict.get('patient_name'),
                'study_date': metadata.get('study_date') or metadata_dict.get('study_date'),
                'study_description': metadata.get('study_description') or metadata_dict.get('study_description'),
                'results': Json(results_json),  # Store full JSON as JSONB
                'measurements': Json(measurements) if measurements else None,
                'processing_time_seconds': metadata.get('processing_time_seconds') or metadata_dict.get('processing_time_seconds'),
                'models_used': metadata.get('models_used') or metadata_dict.get('models_used') or [],
                'input_file_path': metadata.get('input_file_path') or metadata_dict.get('input_file'),
                'output_directory': metadata.get('output_directory') or metadata_dict.get('output_directory'),
            }
            
            # Insert or update (ON CONFLICT handles re-processing)
            query = """
                INSERT INTO ai_results (
                    study_uid, study_id, series_id, accession_number, patient_id, patient_name,
                    study_date, study_description, results, measurements,
                    processing_time_seconds, models_used, input_file_path, output_directory
                ) VALUES (
                    %(study_uid)s, %(study_id)s, %(series_id)s, %(accession_number)s, %(patient_id)s, %(patient_name)s,
                    %(study_date)s, %(study_description)s, %(results)s, %(measurements)s,
                    %(processing_time_seconds)s, %(models_used)s, %(input_file_path)s, %(output_directory)s
                )
                ON CONFLICT (study_uid) DO UPDATE SET
                    study_id = EXCLUDED.study_id,
                    results = EXCLUDED.results,
                    measurements = EXCLUDED.measurements,
                    processing_time_seconds = EXCLUDED.processing_time_seconds,
                    models_used = EXCLUDED.models_used,
                    timestamp = NOW()
            """
            
            cur.execute(query, data)
            conn.commit()
            cur.close()
            
            logger.info(f"Stored results for study_uid={study_uid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store results for study_uid={study_uid}: {e}")
            conn.rollback()
            return False
        finally:
            self._put_conn(conn)
    
    def get_by_study_uid(self, study_uid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve results by study_uid (DICOM StudyInstanceUID).
        
        Args:
            study_uid: DICOM StudyInstanceUID
        
        Returns:
            Results dictionary or None if not found
        """
        if not self.enabled:
            return None
        
        conn = self._get_conn()
        if not conn:
            return None
        
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT results FROM ai_results WHERE study_uid = %s",
                (study_uid,)
            )
            row = cur.fetchone()
            cur.close()
            
            if row:
                return row[0]  # results is JSONB, psycopg2 returns as dict
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve results for study_uid={study_uid}: {e}")
            return None
        finally:
            self._put_conn(conn)
    
    def get_by_study_id(self, study_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve results by study_id (Orthanc study ID).
        
        Args:
            study_id: Orthanc study ID
        
        Returns:
            Results dictionary or None if not found
        """
        if not self.enabled:
            return None
        
        conn = self._get_conn()
        if not conn:
            return None
        
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT results FROM ai_results WHERE study_id = %s",
                (study_id,)
            )
            row = cur.fetchone()
            cur.close()
            
            if row:
                return row[0]  # results is JSONB, psycopg2 returns as dict
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve results for study_id={study_id}: {e}")
            return None
        finally:
            self._put_conn(conn)
    
    def get_by_accession(self, accession_number: str) -> list:
        """
        Retrieve all results for an accession number.
        
        Args:
            accession_number: DICOM AccessionNumber
        
        Returns:
            List of results dictionaries
        """
        if not self.enabled:
            return []
        
        conn = self._get_conn()
        if not conn:
            return []
        
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT results FROM ai_results WHERE accession_number = %s ORDER BY timestamp DESC",
                (accession_number,)
            )
            rows = cur.fetchall()
            cur.close()
            
            return [row[0] for row in rows]  # Extract results from tuples
            
        except Exception as e:
            logger.error(f"Failed to retrieve results for accession={accession_number}: {e}")
            return []
        finally:
            self._put_conn(conn)
    
    def close(self):
        """Close the connection pool."""
        if self.pool:
            self.pool.closeall()
            logger.debug("Results DB connection pool closed")
