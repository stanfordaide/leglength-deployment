"""
Metrics collector that formats data for both InfluxDB and Prometheus backends.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import psutil
import os
import calendar
import numpy as np
import uuid

from .events import MonitoringEvent, Metadata, Context, Timings, ModelPrediction, DerivedResults, Status, LegResults

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import pydicom
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False


class MetricsCollector:
    """Collects and formats metrics for both InfluxDB and Prometheus."""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize metrics collector.
        
        Args:
            config: Metrics configuration dictionary
            logger: Logger instance
        """
        self.logger = logger
        self.config = config
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # Configuration options
        self.include_system_metrics = config.get('include_system_metrics', True)
        self.include_model_metrics = config.get('include_model_metrics', True)
        self.collection_interval = config.get('collection_interval', 10)
        
        # System monitoring
        self.process = psutil.Process()
        
        self.logger.debug("Metrics collector initialized")
    
    def _extract_dicom_metadata(self, dicom_path: str) -> Dict[str, Any]:
        """Extract metadata from DICOM file for tagging."""
        metadata = {}
        
        if not PYDICOM_AVAILABLE:
            return metadata
            
        try:
            ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
            
            # Patient information
            metadata['patient_id'] = getattr(ds, 'PatientID', 'unknown')
            metadata['patient_gender'] = getattr(ds, 'PatientSex', 'unknown').upper()
            
            # Calculate age group from patient age
            patient_age = getattr(ds, 'PatientAge', None)
            if patient_age:
                try:
                    # PatientAge format: "025Y" or "030M" etc.
                    age_value = int(patient_age[:3])
                    age_unit = patient_age[3]
                    
                    if age_unit == 'Y':  # Years
                        age_years = age_value
                    elif age_unit == 'M':  # Months
                        age_years = age_value / 12
                    else:
                        age_years = None
                        
                    if age_years is not None:
                        metadata['patient_age'] = int(age_years)
                        if age_years <= 2:
                            metadata['patient_age_group'] = '0-2'
                        elif age_years <= 8:
                            metadata['patient_age_group'] = '2-8'
                        elif age_years <= 18:
                            metadata['patient_age_group'] = '8-18'
                        else:
                            metadata['patient_age_group'] = '18+'
                    else:
                        metadata['patient_age_group'] = 'unknown'
                        
                except (ValueError, IndexError):
                    metadata['patient_age_group'] = 'unknown'
            else:
                metadata['patient_age_group'] = 'unknown'
            
            # Study and series information
            metadata['study_id'] = getattr(ds, 'StudyInstanceUID', 'unknown')
            metadata['series_id'] = getattr(ds, 'SeriesInstanceUID', 'unknown')
            metadata['accession_number'] = getattr(ds, 'AccessionNumber', 'unknown')
            
            # Scanner information
            metadata['scanner_manufacturer'] = getattr(ds, 'Manufacturer', 'unknown')
            metadata['pixel_spacing'] = float(getattr(ds, 'PixelSpacing', [0.0, 0.0])[0])
            
        except Exception as e:
            self.logger.debug(f"Failed to extract DICOM metadata: {e}")
            
        return metadata
    
    def _get_temporal_tags(self, timestamp: float) -> Dict[str, str]:
        """Generate temporal tags from timestamp."""
        dt = datetime.fromtimestamp(timestamp)
        
        # Time of day
        hour = dt.hour
        if 6 <= hour < 12:
            time_of_day = 'morning'
        elif 12 <= hour < 18:
            time_of_day = 'afternoon'
        elif 18 <= hour < 24:
            time_of_day = 'evening'
        else:
            time_of_day = 'night'
        
        # Day type
        day_type = 'weekend' if dt.weekday() >= 5 else 'weekday'
        
        # Week of month (1-based)
        week_of_month = f"week{((dt.day - 1) // 7) + 1}"
        
        return {
            'time_of_day': time_of_day,
            'day_of_week': dt.strftime('%A').lower(),
            'week_of_month': week_of_month,
            'month': dt.strftime('%B').lower(),
            'year': str(dt.year),
            'day_type': day_type
        }
    
    def _extract_table_level_features(self, individual_preds: Dict[str, Any], 
                                     models: List[str], 
                                     pixel_spacing: float) -> Dict[str, float]:
        """
        DEPRECATED: Extract table-level quality features.
        Retained for backward compatibility.
        """
        return {}
    
    def start_session(self, session_id: str, config: Dict[str, Any]) -> None:
        """
        Start collecting metrics for a session.
        
        Args:
            session_id: Unique session identifier
            config: Session configuration
        """
        self.sessions[session_id] = {
            'session_id': session_id,
            'start_time': time.time(),
            'config': config,
            'timings': {},
            'metrics': {},
            'system_metrics': [],
            'model_metrics': {},
            'measurements': {},
            'status': 'started'
        }
        
        # Collect initial system metrics
        if self.include_system_metrics:
            self._collect_system_metrics(session_id)
        
        self.logger.debug(f"Started metrics collection for session {session_id}")
    
    def record_timing(self, session_id: str, stage: str, duration: float) -> None:
        """
        Record timing information for a processing stage.
        
        Args:
            session_id: Session identifier
            stage: Processing stage name
            duration: Duration in seconds
        """
        if session_id not in self.sessions:
            return
        
        self.sessions[session_id]['timings'][stage] = {
            'duration': duration,
            'timestamp': time.time()
        }
        
        self.logger.debug(f"Recorded timing {stage}: {duration:.2f}s")
    
    def record_model_metrics(self, session_id: str, model_name: str, 
                           metrics: Dict[str, Any]) -> None:
        """
        Record model performance metrics.
        
        Args:
            session_id: Session identifier
            model_name: Name of the model
            metrics: Dictionary of model metrics
        """
        if session_id not in self.sessions or not self.include_model_metrics:
            return
        
        self.sessions[session_id]['model_metrics'][model_name] = {
            'timestamp': time.time(),
            'metrics': metrics
        }
        
        self.logger.debug(f"Recorded model metrics for {model_name}")
    
    def record_measurements(self, session_id: str, measurements: Dict[str, Any], 
                           dicom_path: str = None) -> None:
        """
        Record measurement results with DICOM metadata.
        
        Args:
            session_id: Session identifier
            measurements: Dictionary of measurements
            dicom_path: Path to DICOM file for metadata extraction
        """
        if session_id not in self.sessions:
            return
        
        self.sessions[session_id]['measurements'] = measurements
        if dicom_path:
            self.sessions[session_id]['dicom_path'] = dicom_path
            
        self.logger.debug(f"Recorded {len(measurements)} measurements")
    
    def record_performance_data(self, session_id: str, performance_data: Dict[str, Any],
                               dicom_path: str = None) -> None:
        """
        Record AI performance data (uncertainties, point statistics).
        
        Args:
            session_id: Session identifier
            performance_data: Dictionary containing uncertainties and point statistics
            dicom_path: Path to DICOM file for metadata extraction
        """
        if session_id not in self.sessions:
            return
            
        self.sessions[session_id]['performance_data'] = performance_data
        if dicom_path:
            self.sessions[session_id]['dicom_path'] = dicom_path
            
        self.logger.debug(f"Recorded performance data with {len(performance_data.get('uncertainties', {}))} points")
    
    def record_custom_metric(self, session_id: str, name: str, value: Any, 
                           tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a custom metric.
        
        Args:
            session_id: Session identifier
            name: Metric name
            value: Metric value
            tags: Optional tags
        """
        if session_id not in self.sessions:
            return
        
        if 'custom_metrics' not in self.sessions[session_id]:
            self.sessions[session_id]['custom_metrics'] = []
        
        self.sessions[session_id]['custom_metrics'].append({
            'name': name,
            'value': value,
            'tags': tags or {},
            'timestamp': time.time()
        })
        
        self.logger.debug(f"Recorded custom metric {name}: {value}")
    
    def _collect_system_metrics(self, session_id: str) -> None:
        """Collect current system metrics."""
        if session_id not in self.sessions:
            return
        
        try:
            # CPU and memory metrics
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            # System-wide metrics
            system_cpu = psutil.cpu_percent()
            system_memory = psutil.virtual_memory()
            disk_usage = psutil.disk_usage('/')
            
            # GPU metrics if available
            gpu_metrics = self._get_gpu_metrics()
            
            system_data = {
                'timestamp': time.time(),
                'process_cpu_percent': cpu_percent,
                'process_memory_mb': memory_mb,
                'system_cpu_percent': system_cpu,
                'system_memory_percent': system_memory.percent,
                'system_memory_available_gb': system_memory.available / (1024**3),
                'disk_usage_percent': disk_usage.percent,
                'disk_free_gb': disk_usage.free / (1024**3)
            }
            
            if gpu_metrics:
                system_data.update(gpu_metrics)
            
            self.sessions[session_id]['system_metrics'].append(system_data)
            
        except Exception as e:
            self.logger.debug(f"Failed to collect system metrics: {e}")
    
    def _get_gpu_metrics(self) -> Dict[str, Any]:
        """Get GPU metrics if available."""
        gpu_metrics = {}
        
        try:
            if TORCH_AVAILABLE and torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    # Memory usage
                    memory_allocated = torch.cuda.memory_allocated(i) / (1024**2)  # MB
                    memory_reserved = torch.cuda.memory_reserved(i) / (1024**2)   # MB
                    
                    gpu_metrics[f'gpu_{i}_memory_allocated_mb'] = memory_allocated
                    gpu_metrics[f'gpu_{i}_memory_reserved_mb'] = memory_reserved
                    
                    # Temperature and utilization would require nvidia-ml-py
                    # Not including to keep dependencies minimal
                    
        except Exception as e:
            self.logger.debug(f"Failed to collect GPU metrics: {e}")
        
        return gpu_metrics
    
    def get_monitoring_event(self, session_id: str, status: str = 'completed') -> Optional[MonitoringEvent]:
        """
        Construct a MonitoringEvent from session data.
        
        Args:
            session_id: Session identifier
            status: Final status of the session
            
        Returns:
            MonitoringEvent or None if session not found
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
            config = session.get('config', {})
            dicom_path = session.get('dicom_path')
            
            # Extract DICOM metadata
            dicom_metadata = {}
            if dicom_path:
                dicom_metadata = self._extract_dicom_metadata(dicom_path)
            
        # 1. Metadata
        metadata: Metadata = {
            'event_id': str(uuid.uuid4()),
            'session_id': session_id,
            'timestamp': datetime.fromtimestamp(time.time()).isoformat(),
            'app_version': '0.2.0',  # Ideally this should come from config or package
            'model_version': '_'.join(config.get('models', ['unknown'])),
            'config_snapshot': config
        }
        
        # 2. Context
        context: Context = {
            'scanner_manufacturer': dicom_metadata.get('scanner_manufacturer', 'unknown'),
            'pixel_spacing': [dicom_metadata.get('pixel_spacing', 0.0), dicom_metadata.get('pixel_spacing', 0.0)],
            'image_size': [0, 0], # TODO: We need to capture image size
            'patient_age_group': dicom_metadata.get('patient_age_group', 'unknown'),
            'patient_sex': dicom_metadata.get('patient_gender', 'unknown'),
                'study_id': dicom_metadata.get('study_id', 'unknown'),
                'series_id': dicom_metadata.get('series_id', 'unknown'),
            'accession_number': dicom_metadata.get('accession_number', 'unknown')
        }
        
        # 3. Timings
        timings_data = session.get('timings', {})
        timings: Timings = {
            'total_processing': timings_data.get('total_processing', {}).get('duration', 0.0),
            'inference': timings_data.get('inference', {}).get('duration', 0.0),
            'measurement_calculation': timings_data.get('measurement', {}).get('duration', 0.0),
            'dicom_generation': timings_data.get('dicom_generation', {}).get('duration', 0.0),
            'stages': {k: v.get('duration', 0.0) for k, v in timings_data.items()}
        }
        
        # 4. Raw Predictions
                        performance_data = session.get('performance_data', {})
        individual_preds = performance_data.get('individual_model_predictions', {})
        raw_predictions: Dict[str, ModelPrediction] = {}
        
        for model_name, pred_data in individual_preds.items():
            predictions = pred_data.get('predictions', {})
            raw_predictions[model_name] = {
                'boxes': predictions.get('boxes', []),
                'labels': predictions.get('labels', []),
                'scores': predictions.get('scores', [])
            }
            
        # 5. Derived Results
        measurements = session.get('measurements', {})
        
        # Helper to extract leg measurements safely
        def get_leg_measurements(side_prefix: str) -> LegResults:
            return {
                'femur_length_mm': measurements.get(f'{side_prefix}_femur_length', {}).get('millimeters') if isinstance(measurements.get(f'{side_prefix}_femur_length'), dict) else None,
                'tibia_length_mm': measurements.get(f'{side_prefix}_tibia_length', {}).get('millimeters') if isinstance(measurements.get(f'{side_prefix}_tibia_length'), dict) else None,
                'total_length_mm': measurements.get(f'{side_prefix}_total_length', {}).get('millimeters') if isinstance(measurements.get(f'{side_prefix}_total_length'), dict) else None,
            }

        derived_results: DerivedResults = {
            'left': get_leg_measurements('left'), # Assuming keys like 'left_femur_length'
            'right': get_leg_measurements('right'), # Assuming keys like 'right_femur_length'
            'metrics': {}
        }
        
        # Fallback for old measurement structure if side prefixes aren't used
        # This part depends on how your measurements dictionary is actually structured
        # If it's just 'femur_length', we might need to know which leg it is or if it's combined
        if not derived_results['left']['femur_length_mm'] and not derived_results['right']['femur_length_mm']:
             # Try without prefix if specific side data is missing (backward compatibility)
             derived_results['metrics']['legacy_femur_length_mm'] = measurements.get('femur_length', {}).get('millimeters') if isinstance(measurements.get('femur_length'), dict) else None
             derived_results['metrics']['legacy_tibia_length_mm'] = measurements.get('tibia_length', {}).get('millimeters') if isinstance(measurements.get('tibia_length'), dict) else None
             derived_results['metrics']['legacy_total_length_mm'] = measurements.get('total_length', {}).get('millimeters') if isinstance(measurements.get('total_length'), dict) else None

        # 6. Status
        status_obj: Status = {
            'code': status,
            'errors': performance_data.get('issues', [])
        }
        
        return {
            'metadata': metadata,
            'context': context,
            'timings': timings,
            'raw_predictions': raw_predictions,
            'derived_results': derived_results,
            'status': status_obj
        }

    def get_influx_data(self, session_id: str) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Format session data for InfluxDB.
        Retained for backward compatibility if InfluxDB client is re-added.
        """
        return []
    
    def get_prometheus_data(self, session_id: str) -> Dict[str, Any]:
        """
        DEPRECATED: Format session data for Prometheus.
        Retained for backward compatibility if Prometheus client is re-added.
        """
            return {}
    
    def cleanup_session(self, session_id: str) -> None:
        """
        Clean up session data.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.logger.debug(f"Cleaned up session {session_id}")
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.sessions.keys())
