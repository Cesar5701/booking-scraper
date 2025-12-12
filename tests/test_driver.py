from src.core.driver import initialize_driver
import logging

logging.basicConfig(level=logging.INFO)

try:
    driver = initialize_driver()
    print("Driver initialized successfully with new options.")
    driver.quit()
except Exception as e:
    print(f"Driver initialization failed: {e}")
