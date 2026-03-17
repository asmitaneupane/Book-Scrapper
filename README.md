# Books Scraper

A Python web scraper that crawls all pages of [books.toscrape.com](https://books.toscrape.com),
visits each book's detail page, and extracts structured data.

## Extracted Fields

- Title, URL, Scrape date
- Description, Price, Tax
- Availability, UPC, Rating

## Setup

1. Clone the repo

```bash
   git clone https://github.com/asmitaneupane/Book-Scrapper.git
   cd Book-Scrapper
```

2. Create and activate a virtual environment

```bash
   python -m venv .venv
   .venv\Scripts\activate
```

3. Install dependencies

```bash
   pip install -r requirements.txt
```

## Usage

```bash
python books_scraper.py
```

Output files `books_data.json` and `books_data.csv` will be created
in the same directory.

## Tech Stack

- Python 3
- `requests`
- `BeautifulSoup4`
