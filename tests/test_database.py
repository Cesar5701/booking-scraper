import unittest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.models import Review

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Use in-memory DB for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_create_review(self):
        review = Review(
            hotel_name="Test Hotel",
            hotel_url="http://test.com",
            title="Great stay",
            score="10",
            positive="Everything",
            negative="Nothing",
            date="2023-01-01",
            review_hash="abc123hash"
        )
        self.session.add(review)
        self.session.commit()

        # Query back
        saved_review = self.session.query(Review).first()
        self.assertEqual(saved_review.hotel_name, "Test Hotel")
        self.assertEqual(saved_review.score, 10.0)
        self.assertEqual(saved_review.review_hash, "abc123hash")

    def test_duplicate_hash(self):
        # Add first review
        r1 = Review(hotel_name="H1", hotel_url="u1", title="t1", score="10", review_hash="hash1")
        self.session.add(r1)
        self.session.commit()

        # Add second review with same hash (should fail unique constraint if enforced, 
        # but SQLAlchemy might raise IntegrityError)
        r2 = Review(hotel_name="H1", hotel_url="u1", title="t1", score="10", review_hash="hash1")
        self.session.add(r2)
        
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            self.session.commit()

if __name__ == '__main__':
    unittest.main()
