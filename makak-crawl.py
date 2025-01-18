#!/usr/bin/env python3

import os
import time
import glob
import logging
from multiprocessing import Pool, cpu_count
from typing import Optional, Set
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MakakCrawler:
    def __init__(self, 
                 base_dir: str = "/images/",
                 makak_script: str = "/home/mates/test/makak.py",
                 max_workers: Optional[int] = None):
        self.base_dir = base_dir
        self.makak_script = makak_script
        self.triggered_files: Set[str] = set()
        self.max_workers = max_workers or cpu_count()
        self.pool = Pool(processes=self.max_workers)
        
    def get_latest_date_dir(self) -> Optional[str]:
        """Find the most recent date directory."""
        pattern = os.path.join(self.base_dir, "*", "20??????")
        dirs = glob.glob(pattern)
        return max(dirs) if dirs else None

    def process_file(self, fits_file: str) -> None:
        """Process a single FITS file using makak.py"""
        try:
            subprocess.run([self.makak_script, fits_file])
        except Exception as e:
            logging.error(f"Error processing {fits_file}: {e}")

    def run(self) -> None:
        """Main crawling loop."""
        logging.info(f"Starting crawl with {self.max_workers} workers")
        current_dir = None
        
        while True:
            try:
                date_dir = self.get_latest_date_dir()
                if not date_dir:
                    time.sleep(2)
                    continue

                # If moved to new directory, clear triggered files
                if date_dir != current_dir:
                    logging.info(f"New directory: {date_dir}")
                    self.triggered_files.clear()
                    current_dir = date_dir
                    # Get all existing files to avoid reprocessing them
                    pattern = os.path.join(date_dir, "*.fits")
                    self.triggered_files.update(glob.glob(pattern))

                # Check for new file
                pattern = os.path.join(date_dir, "*.fits")
                all_files = sorted(glob.glob(pattern))
                if not all_files:
                    time.sleep(2)
                    continue

                newest_file = all_files[-1]
                if newest_file not in self.triggered_files:
                    logging.info(f"Processing new file: {newest_file}")
                    self.pool.apply_async(self.process_file, (newest_file,))
                    self.triggered_files.add(newest_file)

                time.sleep(2)

            except KeyboardInterrupt:
                logging.info("Shutting down...")
                self.pool.close()
                self.pool.join()
                break
            except Exception as e:
                logging.error(f"Error in crawling loop: {e}")
                time.sleep(2)

def main():
    os.environ['DISPLAY'] = ''
    os.environ['LANG'] = 'C'
    crawl = MakakCrawler()
    crawl.run()

if __name__ == "__main__":
    main()
