import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from core.extractor import ReviewExtractor
from utils.cleaning import extract_score_from_text
from selenium.common.exceptions import NoSuchElementException

class TestCleaning(unittest.TestCase):
    def test_extract_score_simple(self):
        self.assertEqual(extract_score_from_text("Score: 8.5"), "8.5")
        self.assertEqual(extract_score_from_text("10"), "10")
        self.assertEqual(extract_score_from_text("9,2"), "9.2")

    def test_extract_score_complex(self):
        self.assertEqual(extract_score_from_text("Puntuación: 7.5 / 10"), "7.5")
        self.assertEqual(extract_score_from_text("Review score: 10"), "10")
        self.assertEqual(extract_score_from_text("Garbage text 5.0 more text"), "5.0")
        
    def test_extract_score_invalid(self):
        self.assertEqual(extract_score_from_text("No score here"), "0")
        self.assertEqual(extract_score_from_text(""), "0")
        self.assertEqual(extract_score_from_text(None), "0")

class TestExtractor(unittest.TestCase):
    def setUp(self):
        self.mock_driver = MagicMock()
        self.extractor = ReviewExtractor(self.mock_driver)

    def test_get_hotel_name_title_fallback(self):
        # Setup mock to fail all other strategies and fallback to title
        self.mock_driver.find_elements.return_value = [] # No JSON-LD
        self.mock_driver.find_element.side_effect = NoSuchElementException # No specific elements
        self.mock_driver.title = "Hotel California - Booking.com"
        
        name = self.extractor.get_hotel_name()
        self.assertEqual(name, "Hotel California")

    def test_get_total_review_count(self):
        # Mock finding the element with review count
        mock_elem = MagicMock()
        mock_elem.text = "Comentarios (1,234)"
        self.mock_driver.find_elements.return_value = [mock_elem]
        
        count = self.extractor.get_total_review_count()
        self.assertEqual(count, 1234)

if __name__ == '__main__':
    unittest.main()
