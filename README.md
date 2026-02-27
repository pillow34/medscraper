# medscraper

A collection of medicine scrapers for various Indian pharmacies.

## 1mg Scraper v2 (`1mg_scraper_v2.py`)

The `1mg_scraper_v2.py` script is a powerful tool to extract medicine information from 1mg.com using Playwright. It operates in two main stages: initial search to find products (brands) and detailed scraping to extract full product details including compositions, substitutes, and generic alternatives.

### Features
- **Search Mode**: Scrapes product listings for a list of medicine names.
- **Detail Mode**: Scrapes full product details from individual product URLs.
- **Headless Support**: Can run with or without a visible browser window.
- **Database Storage**: Automatically stores all scraped data in a DuckDB database.
- **Substitutes & Generics**: Extracts information about medicine substitutes and cheaper generic alternatives.

### Prerequisites
- Python 3.x
- Playwright (`pip install playwright` and `playwright install chromium`)
- DuckDB (`pip install duckdb`)
- Pandas (`pip install pandas`)

### Project Structure for 1mg
- `medscraper/onemg/1mg_scraper_v2.py`: The main scraper script.
- `medscraper/onemg/brands_to_fetch.txt`: Input file for search mode (one medicine name per line).
- `medscraper/onemg/db/db.py`: Database management logic.
- `medscraper/onemg/db/db.duckdb`: The database where data is stored.

### Usage

Navigate to the `medscraper/onemg` directory before running the script.

#### Step 1: Scrape Product Links (Search Mode)
This mode reads medicine names from `brands_to_fetch.txt`, searches for them on 1mg, and stores the basic info and URLs in the database.

```bash
python 1mg_scraper_v2.py --brands --limit 20 --headless
```
- `--brands`: Enables search mode using the input file.
- `--limit <number>`: Limits the number of products scraped per search term.
- `--headless`: Runs the browser in the background.

#### Step 2: Scrape Detailed Information (Detail Mode)
This mode retrieves the URLs collected in Step 1 from the database and scrapes full details for each.

```bash
python 1mg_scraper_v2.py --detail --headless
```
- `--detail`: Enables detailed scraping for URLs found in the database.

### Command Line Arguments
| Argument | Description |
|---|---|
| `medicine_name` | (Optional) Name of a single medicine to search for. |
| `--limit <int>` | Maximum number of products to scrape per search. |
| `--headless` | Run browser in headless mode. |
| `--debug` | Enable DEBUG level logging for troubleshooting. |
| `--brands` | Extract brands using search terms from `brands_to_fetch.txt`. |
| `--detail` | Extract full PDP data and substitutes using URLs from the database. |

### Data Schema
Data is stored in `db/db.duckdb` with the following main tables:
- `medicines`: Basic product info from search results.
- `medicine_details`: Queue of URLs to be scraped for details.
- `medicine_scraped_details`: Full product data (composition, substitutes, etc.).