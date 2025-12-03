import unittest
from unittest.mock import MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pages.hotel_page import HotelPage
from selenium.common.exceptions import NoSuchElementException

class TestHotelPage(unittest.TestCase):
    def setUp(self):
        self.mock_driver = MagicMock()
        self.hotel_page = HotelPage(self.mock_driver)

    def test_get_name_title_fallback(self):
        # Setup mock to fail all other strategies and fallback to title
        self.mock_driver.find_elements.return_value = [] # No JSON-LD
        self.mock_driver.find_element.side_effect = NoSuchElementException # No specific elements
        self.mock_driver.title = "Hotel California - Booking.com"
        
        name = self.hotel_page.get_name()
        self.assertEqual(name, "Hotel California")

    def test_get_expected_review_count(self):
        # Mock finding the element with review count
        mock_elem = MagicMock()
        mock_elem.text = "Comentarios (1,234)"
        
        # Simulate finding the element in the list of candidates
        self.mock_driver.find_elements.return_value = [mock_elem]
        
        count = self.hotel_page.get_expected_review_count()
        self.assertEqual(count, 1234)

if __name__ == '__main__':
    unittest.main()
