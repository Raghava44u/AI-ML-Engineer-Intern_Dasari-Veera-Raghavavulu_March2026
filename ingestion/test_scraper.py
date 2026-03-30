import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

def test_stanford():
    url = "https://explorecourses.stanford.edu/search?view=catalog&filter-coursestatus-Active=on&page=0&catalog=&q=CS"
    resp = requests.get(url)
    print("Stanford:", resp.status_code)

def test_mit():
    url = "http://student.mit.edu/catalog/m6a.html"
    resp = requests.get(url)
    print("MIT:", resp.status_code)

def test_bits():
    # Trying bits-pilani computer science curriculum
    url = "https://www.bits-pilani.ac.in/goa/computer-science-and-information-systems/academics/curriculum/"
    # or general search
    resp = requests.get(url)
    print("BITS Pilani:", resp.status_code)

if __name__ == "__main__":
    test_stanford()
    test_mit()
    test_bits()
