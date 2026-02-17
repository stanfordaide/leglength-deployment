"""
Harvester CLI Entry Point
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from .processor import Harvester

def main():
    parser = argparse.ArgumentParser(description="Monitoring Event Harvester")
    parser.add_argument('--data-path', type=str, 
                        default=os.environ.get('MONITORING_DATA_PATH', '/var/log/mercure/monitoring_events'),
                        help="Path to monitoring event files")
    parser.add_argument('--loop', action='store_true', help="Run in a continuous loop")
    parser.add_argument('--interval', type=int, default=60, help="Loop interval in seconds")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='[%(levelname)s] %(message)s')
    
    # Validate path
    if not Path(args.data_path).exists():
        logging.warning(f"Data path {args.data_path} does not exist. Waiting for events...")
    
    harvester = Harvester(args.data_path, interval=args.interval)
    
    if args.loop:
        harvester.run_loop()
    else:
        harvester.run_once()

if __name__ == "__main__":
    main()
