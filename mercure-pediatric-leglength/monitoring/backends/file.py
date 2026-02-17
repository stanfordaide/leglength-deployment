"""
File-based monitoring backend for storing raw events.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .base import MonitoringBackend
from ..events import MonitoringEvent

class FileBackend(MonitoringBackend):
    """
    Writes monitoring events to individual JSON files in a directory structure.
    Strategy: One file per session to ensure atomic writes and avoid locking issues.
    Structure: {base_path}/{date}/event_{session_id}.json
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        super().__init__(config)
        self.logger = logger or logging.getLogger(__name__)
        
        # Determine output path
        # Priority:
        # 1. config['path'] (from task.json)
        # 2. MONITORING_DATA_PATH env var
        # 3. Default: /var/log/mercure/monitoring_events
        
        self.base_path = Path(config.get('path', os.environ.get('MONITORING_DATA_PATH', '/var/log/mercure/monitoring_events')))
        
        # Ensure base directory exists
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"FileBackend initialized with base path: {self.base_path}")
        except Exception as e:
            self.logger.error(f"Failed to create monitoring directory {self.base_path}: {e}")
            self.enabled = False

    def record_event(self, event: MonitoringEvent) -> bool:
        """
        Write the event to a unique JSON file.
        """
        if not self.enabled:
            return False
            
        try:
            # 1. Get Session ID for filename
            session_id = event['metadata'].get('session_id', 'unknown_session')
            # Sanitize session_id for filename (replace slashes, etc if any)
            safe_session_id = "".join([c for c in session_id if c.isalnum() or c in "._-"])
            
            # 2. Create Date-based Directory
            date_str = datetime.now().strftime('%Y-%m-%d')
            daily_dir = self.base_path / date_str
            daily_dir.mkdir(exist_ok=True)
            
            # 3. Define File Path
            filename = f"event_{safe_session_id}.json"
            file_path = daily_dir / filename
            
            # 4. Write Atomic JSON
            # Use default=str to handle any non-serializable objects gracefully
            with open(file_path, 'w') as f:
                json.dump(event, f, indent=2, default=str)
                
            self.logger.debug(f"Recorded event to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write event file: {e}")
            return False

    def close(self) -> None:
        """No persistent connection to close."""
        pass
