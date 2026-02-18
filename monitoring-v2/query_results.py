#!/usr/bin/env python3
"""
Simple CLI tool to query AI results from the monitoring database.

Usage:
    python query_results.py <study_id>          # Get results by study_id
    python query_results.py --accession <acc>   # Get all results for accession
    python query_results.py --list              # List recent results
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add parent directory to path to import results_db_client
sys.path.insert(0, str(Path(__file__).parent))

from results_db_client import ResultsDBClient


def main():
    parser = argparse.ArgumentParser(description='Query AI results from monitoring database')
    parser.add_argument('study_uid', nargs='?', help='DICOM StudyInstanceUID to query')
    parser.add_argument('--study-id', help='Orthanc study ID to query')
    parser.add_argument('--accession', '-a', help='Accession number to query')
    parser.add_argument('--list', '-l', action='store_true', help='List recent results')
    parser.add_argument('--limit', type=int, default=10, help='Limit for --list (default: 10)')
    parser.add_argument('--pretty', '-p', action='store_true', help='Pretty print JSON')
    
    args = parser.parse_args()
    
    client = ResultsDBClient()
    
    if not client.enabled:
        print("ERROR: Results DB client not available. Check MONITORING_DB_* environment variables.")
        sys.exit(1)
    
    try:
        if args.list:
            # List recent results (would need to add this method to client)
            print("Listing recent results...")
            print("(Feature not yet implemented - use study_uid, --study-id, or --accession)")
            sys.exit(1)
        elif args.accession:
            results = client.get_by_accession(args.accession)
            if not results:
                print(f"No results found for accession: {args.accession}")
                sys.exit(1)
            print(f"Found {len(results)} result(s) for accession: {args.accession}\n")
            for i, result in enumerate(results, 1):
                if len(results) > 1:
                    print(f"--- Result {i} ---")
                if args.pretty:
                    print(json.dumps(result, indent=2))
                else:
                    print(json.dumps(result))
        elif args.study_id:
            result = client.get_by_study_id(args.study_id)
            if not result:
                print(f"No results found for study_id: {args.study_id}")
                sys.exit(1)
            if args.pretty:
                print(json.dumps(result, indent=2))
            else:
                print(json.dumps(result))
        elif args.study_uid:
            result = client.get_by_study_uid(args.study_uid)
            if not result:
                print(f"No results found for study_uid: {args.study_uid}")
                sys.exit(1)
            if args.pretty:
                print(json.dumps(result, indent=2))
            else:
                print(json.dumps(result))
        else:
            parser.print_help()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()


if __name__ == '__main__':
    main()
