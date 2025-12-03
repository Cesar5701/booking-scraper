import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

import config
# Override config for dry run
config.HOTEL_VISIT_LIMIT = 1
config.HEADLESS_MODE = True 
config.MAX_WORKERS = 1

print(f"Running scraper dry run with limit: {config.HOTEL_VISIT_LIMIT}")

from scraper import main

if __name__ == "__main__":
    try:
        main()
        print("SUCCESS: Scraper dry run completed.")
    except Exception as e:
        print(f"FAILURE: Scraper dry run failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
