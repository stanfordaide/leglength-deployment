"""
Harvester Core Logic
--------------------
Scans the filesystem for monitoring events and runs calculators.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Callable

from .calculators import CALCULATORS

logger = logging.getLogger(__name__)

class Harvester:
    def __init__(self, data_path: str, interval: int = 60):
        self.data_path = Path(data_path)
        self.interval = interval
        self.processed_files = set() # TODO: Persist this state (e.g., sqlite or a simple tracking file)
        
    def scan_files(self) -> List[Path]:
        """
        Recursively find all .json files in the data path.
        Returns files sorted by modification time (oldest first).
        """
        if not self.data_path.exists():
            logger.warning(f"Data path {self.data_path} does not exist.")
            return []
            
        files = []
        for root, _, filenames in os.walk(self.data_path):
            for filename in filenames:
                if filename.endswith('.json'):
                    files.append(Path(root) / filename)
        
        # Sort by mtime to process in order
        files.sort(key=lambda p: p.stat().st_mtime)
        return files

    def process_event(self, file_path: Path) -> Dict[str, Any]:
        """
        Read an event file and apply all registered calculators.
        """
        try:
            with open(file_path, 'r') as f:
                event = json.load(f)
                
            # Metadata for context
            result = {
                'meta_session_id': event.get('metadata', {}).get('session_id'),
                'meta_timestamp': event.get('metadata', {}).get('timestamp'),
                'meta_source_file': str(file_path)
            }
            
            # Run all calculators
            for calculator in CALCULATORS:
                try:
                    metrics = calculator(event)
                    result.update(metrics)
                except Exception as e:
                    logger.error(f"Calculator {calculator.__name__} failed for {file_path}: {e}")
                    
            return result
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return {}

    def run_once(self):
        """Run a single pass over all files."""
        logger.info(f"Scanning {self.data_path}...")
        files = self.scan_files()
        new_files = [f for f in files if f not in self.processed_files]
        
        logger.info(f"Found {len(new_files)} new events.")
        
        for file_path in new_files:
            metrics = self.process_event(file_path)
            if metrics:
                self.emit_metrics(metrics)
                self.processed_files.add(file_path)
                
    def run_loop(self):
        """Run continuously."""
        logger.info("Starting Harvester Loop...")
        while True:
            self.run_once()
            time.sleep(self.interval)

    def emit_metrics(self, metrics: Dict[str, Any]):
        """
        Output the calculated metrics.
        TODO: Replace this with InfluxDB/Prometheus push logic.
        """
        # For now, just print JSON to stdout so it can be piped or viewed
        print(json.dumps(metrics))
