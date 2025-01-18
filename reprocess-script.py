#!/usr/bin/env python3

import os
import glob
import logging
import signal
from multiprocessing import Pool, cpu_count
from typing import Optional, Set, List
import subprocess
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def init_worker(nice_level: int = 10):
    """Initialize worker process to ignore SIGINT and set nice level"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    os.nice(nice_level)

def process_file(fits_file: str) -> bool:
    """Process a single file using makak.py"""
    try:
        makak_script = "/home/mates/makak-reloaded/bin/makak-reloaded.py"  # Make this a global constant
        subprocess.run([makak_script, fits_file], check=True)
        if process_file.processed_count % 100 == 0:
            logging.info(f"Processed {process_file.processed_count} files")
        process_file.processed_count += 1
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error processing {fits_file}: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error processing {fits_file}: {e}")
        return False

# Initialize the counter as a function attribute
process_file.processed_count = 0

class BatchProcessor:
    def __init__(self, 
                 base_dir: str = "/storage/archive-images/MAKAK/images/",
                 max_workers: Optional[int] = None,
                 failed_list: Optional[str] = None,
                 nice_level: int = 10):
        self.base_dir = base_dir
        self.max_workers = max_workers or cpu_count()
        self.nice_level = nice_level
        self.failed_files: Set[str] = self._load_failed_files(failed_list) if failed_list else set()
#        self.processed_count = 0
        self.start_time = datetime.now()

    def _load_failed_files(self, failed_list: str) -> Set[str]:
        """Load list of failed files if it exists"""
        try:
            with open(failed_list, 'r') as f:
                return set(line.strip() for line in f)
        except FileNotFoundError:
            return set()

    def _is_processed(self, fits_file: str) -> bool:
        """Check if a file has been processed by looking for its output"""
        # Convert input path to expected output path
        date_str = datetime.fromtimestamp(os.path.getmtime(fits_file)).strftime("%Y%m%d")
        ecsv_name = Path(fits_file).stem + ".ecsv"
        ecsv_path = f"/home/mates/makak-reloaded/ecsv/{date_str}/{ecsv_name}"
        return os.path.exists(ecsv_path)

    def find_unprocessed_files(self) -> List[str]:
        """Find all .fits files that haven't been processed yet"""
        logging.info(f"Scanning directory tree starting at {self.base_dir}")
        all_files = []
        
        # Use os.walk for memory-efficient directory traversal
        for root, _, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith('.fits'):
                    full_path = os.path.join(root, file)
                    if not self._is_processed(full_path) and full_path not in self.failed_files:
                        all_files.append(full_path)
                        
                        # Log progress periodically
                        if len(all_files) % 1000 == 0:
                            logging.info(f"Found {len(all_files)} unprocessed files so far...")
        
        logging.info(f"Found total of {len(all_files)} unprocessed files")
        return sorted(all_files)  # Sort for predictable processing order

    def run(self, reprocess_failed: bool = False) -> None:
        """Main processing loop"""
        try:
            # Find files to process
            if reprocess_failed:
                files_to_process = list(self.failed_files)
                logging.info(f"Reprocessing {len(files_to_process)} previously failed files")
            else:
                files_to_process = self.find_unprocessed_files()

            if not files_to_process:
                logging.info("No files to process")
                return

            # Process files in parallel
            logging.info(f"Starting processing with {self.max_workers} workers")
            with Pool(processes=self.max_workers, 
                     initializer=init_worker,
                     initargs=(self.nice_level,)) as pool:
                
                results = pool.map(process_file, files_to_process)

            # Collect failed files
            failed = [f for f, success in zip(files_to_process, results) if not success]
            
            # Write failed files to log
            if failed:
                failed_log = "failed_processing.txt"
                with open(failed_log, 'w') as f:
                    for file in failed:
                        f.write(f"{file}\n")
                logging.info(f"Written {len(failed)} failed files to {failed_log}")

            # Final statistics
            elapsed = datetime.now() - self.start_time
            total_processed = process_file.processed_count
            rate = total_processed / elapsed.total_seconds()
            logging.info(f"Processing complete. Total files: {len(files_to_process)}")
            logging.info(f"Successful: {total_processed}, Failed: {len(failed)}")
            logging.info(f"Total time: {elapsed}, Average rate: {rate:.2f} files/second")

        except KeyboardInterrupt:
            logging.info("Received interrupt, shutting down gracefully...")
        except Exception as e:
            logging.error(f"Error in processing: {e}")

def main():
    parser = argparse.ArgumentParser(description='Batch process FITS files')
    parser.add_argument('--base-dir', default='/storage/archive-images/MAKAK/images/', help='Base directory to scan')
    parser.add_argument('--max-workers', type=int, help='Maximum number of worker processes')
    parser.add_argument('--failed-list', help='File containing list of failed files', default='/home/mates/makak-reloaded/failed.lst')
    parser.add_argument('--reprocess-failed', action='store_true', 
                       help='Reprocess files from failed list instead of finding new ones')
    parser.add_argument('--nice', type=int, default=10,
                       help='Nice level for worker processes (0-19, default: 10)')
    
    args = parser.parse_args()
    
    os.environ['DISPLAY'] = ''
    os.environ['LANG'] = 'C'
    
    processor = BatchProcessor(
        base_dir=args.base_dir,
        max_workers=args.max_workers,
        failed_list=args.failed_list,
        nice_level=args.nice
    )
    processor.run(reprocess_failed=args.reprocess_failed)

if __name__ == "__main__":
    import argparse
    main()
