"""
Backend for writing Mercure result.json file.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .base import MonitoringBackend
from ..events import MonitoringEvent, MercureResult

class MercureResultBackend(MonitoringBackend):
    """
    Writes a result.json file to the output directory for Mercure to pick up.
    This enables Mercure's internal tracking and notification features.
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        super().__init__(config)
        self.logger = logger or logging.getLogger(__name__)
        # The output directory is passed in the config, usually from run.py arguments
        self.output_dir = Path(config.get('output_dir', '.'))
        
    def record_event(self, event: MonitoringEvent) -> bool:
        """
        Write the event to result.json in the output directory.
        """
        if not self.enabled:
            return False
            
        try:
            result_path = self.output_dir / 'result.json'
            
            # Construct the Mercure result object
            # We wrap the full event inside, so Mercure archives everything
            mercure_result: MercureResult = {
                'event': event
            }
            
            # Check if we should trigger a notification
            # Example logic: if status is failed, or if specific findings are present
            if event['status']['code'] == 'failed':
                mercure_result['__mercure_notification'] = {
                    'text': f"Leg Length Analysis Failed: {', '.join(event['status']['errors'])}",
                    'status': 'error'
                }
            elif event['status']['code'] == 'success':
                # Optional: Notify on success with summary
                left = event['derived_results']['left']
                right = event['derived_results']['right']
                summary = []
                if left['total_length_mm']:
                    summary.append(f"L:{left['total_length_mm']:.1f}mm")
                if right['total_length_mm']:
                    summary.append(f"R:{right['total_length_mm']:.1f}mm")
                
                # Only notify if configured to do so (to avoid spam)
                if self.config.get('notify_on_success', False):
                    mercure_result['__mercure_notification'] = {
                        'text': f"Leg Length Analysis Complete. {' '.join(summary)}",
                        'status': 'info'
                    }

            # Write to file
            with open(result_path, 'w') as f:
                json.dump(mercure_result, f, default=str)
                
            self.logger.debug(f"Wrote Mercure result.json to {result_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write result.json: {e}")
            return False

    def close(self) -> None:
        pass
