import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from inference import predict_in_batches

class MockPrediction:
    def __init__(self, output, probas):
        self.output = output
        self.probas = probas

class TestInference(unittest.TestCase):
    def test_predict_in_batches(self):
        # Mock analyzer
        mock_analyzer = MagicMock()
        
        # Setup mock return values
        # Batch 1: 2 items
        # Batch 2: 1 item
        mock_analyzer.predict.side_effect = [
            [MockPrediction('POS', {'POS': 0.9}), MockPrediction('NEG', {'NEG': 0.8})],
            [MockPrediction('NEU', {'NEU': 0.7})]
        ]
        
        texts = ["Good hotel", "Bad hotel", "Okay hotel"]
        
        # Run function with batch_size=2
        results = predict_in_batches(mock_analyzer, texts, 'en', batch_size=2)
        
        # Assertions
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].output, 'POS')
        self.assertEqual(results[1].output, 'NEG')
        self.assertEqual(results[2].output, 'NEU')
        
        # Verify calls
        self.assertEqual(mock_analyzer.predict.call_count, 2)
        mock_analyzer.predict.assert_any_call(["Good hotel", "Bad hotel"])
        mock_analyzer.predict.assert_any_call(["Okay hotel"])

if __name__ == '__main__':
    unittest.main()
