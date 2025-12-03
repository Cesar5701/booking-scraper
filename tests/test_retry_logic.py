import unittest
from unittest.mock import MagicMock, patch
from selenium.common.exceptions import StaleElementReferenceException
from pages.reviews_modal import ReviewsModal
from tenacity import RetryError

class TestRetryLogic(unittest.TestCase):
    def setUp(self):
        self.mock_driver = MagicMock()
        self.reviews_modal = ReviewsModal(self.mock_driver, "Test Hotel", "http://test.com")

    @patch('pages.reviews_modal.ReviewsModal._get_safe_text')
    @patch('pages.reviews_modal.extract_score_from_text')
    def test_extract_review_retry_success(self, mock_extract_score, mock_get_safe_text):
        # Setup mocks
        mock_element = MagicMock()
        # First call raises Stale, second succeeds
        self.mock_driver.find_elements.side_effect = [
            [mock_element], # First call (will be stale)
            [mock_element]  # Second call (success)
        ]
        
        # Simulate StaleElementReferenceException on first attempt accessing text
        # We simulate it by making _get_safe_text raise it the first time
        mock_get_safe_text.side_effect = [StaleElementReferenceException("Stale"), "Title Text", "8.5", "Pos", "Neg", "Date"]
        mock_extract_score.return_value = "8.5"

        # Execute
        data = self.reviews_modal._extract_review_at_index(0)

        # Verify
        self.assertEqual(data['title'], "Title Text")
        self.assertEqual(self.mock_driver.find_elements.call_count, 2) # Called twice due to retry

    @patch('pages.reviews_modal.ReviewsModal._get_safe_text')
    def test_extract_review_retry_fail(self, mock_get_safe_text):
        # Setup mocks to always fail
        self.mock_driver.find_elements.return_value = [MagicMock()]
        mock_get_safe_text.side_effect = StaleElementReferenceException("Stale")

        # Execute and expect RetryError (tenacity raises this after max attempts)
        with self.assertRaises(RetryError):
            self.reviews_modal._extract_review_at_index(0)

if __name__ == '__main__':
    unittest.main()
