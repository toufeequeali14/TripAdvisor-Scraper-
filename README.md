#                            TripAdvisor Scraper

# Overview

This project is a TripAdvisor data scraper that collects hotels, restaurants, attractions, and related business information from TripAdvisor based on a specified city. The scraper extracts location details, ratings, review statistics, pricing information, awards, addresses, images, and URLs, then stores the collected data in a JSON file named after the target city.

The scraper supports automated data collection and can be used for market research, travel analytics, business intelligence, and review analysis.



# Features
- TripAdvisor Scraping: Scrapes business listings directly from TripAdvisor.
- City-Based Search: Collects data for a specified city.

- Comprehensive Data Extraction:
    Location ID
    Business Name
    Category (Hotel, Restaurant, Attraction, etc.)
    Ratings
    Review Count
    Awards
    Address
    City Information
    Price Details
    Photo URLs
    Business URLs
    Geo IDs

- JSON Output: Saves scraped results in a structured JSON file.
- Lightweight Setup: Minimal dependencies and simple execution.

# Requirements
System Requirements
Python 3.8+

# Python Packages
- requests
- playwright

# Install all dependencies using:
pip install -r requirements.txt

pip install playwright chromium

# for easy run in linux environment jut run below two command:
chmod +x run.sh
./run.sh


# for easy run in Windows environment jut run below two command: 
run.bat


### Usage

# Login First properly(save cookies)
python  login_tripadvisor.py   (Login manually, Press Enter to save cookies)

- Run the scraper

python tripadvisor_scraper.py

