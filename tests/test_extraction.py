from src.pages.reviews_modal import ReviewsModal

def test_extraction():
    url = "https://www.booking.com/hotel/mx/boutique-malinalli.es.html"
    scraper = ReviewsModal("Boutique Malinalli", url)
    reviews = scraper.extract_all_reviews()
    
    print(f"Total extracted: {len(reviews)}")
    if reviews:
        print("\nSAMPLE REVIEW:")
        for k, v in reviews[0].items():
            print(f"  {k}: {v}")
            
if __name__ == "__main__":
    test_extraction()
