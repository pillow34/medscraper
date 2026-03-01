# medscraper

A collection of medicine scrapers for various Indian pharmacies.

## Multi-Source Medicine Scraper

The medscraper app supports multiple sources to extract medicine information:
- **1mg.com**
- **PlatinumRx.in**
- **TrueMeds.in**

All sources operate in two main stages: initial search to find products (brands) and detailed scraping to extract full product details including compositions, substitutes, and generic alternatives.

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

### Project Structure
- `onemg/onemg_scraper_v2.py`: Scraper script for 1mg.
- `onemg/platinumrx_scraper.py`: Scraper script for PlatinumRx.
- `onemg/truemeds_scraper.py`: Scraper script for TrueMeds.
- `onemg/brands_to_fetch.txt`: Input file for search mode (one medicine name per line).
- `onemg/db/db.py`: Database management logic.
- `onemg/db/db.duckdb`: The database where data is stored.
- `onemg/app_1mg.py`: Streamlit application.

### Usage

#### Streamlit App (Recommended)
You can run the Streamlit app for a user-friendly interface:
```bash
uv run streamlit run onemg/app_1mg.py
```

**Streamlit App Features:**
- **Sidebar Configuration:**
    - **Debug Mode**: Toggle to enable `DEBUG` level logging and see/download the log file.
    - **Run Browser Headless**: Choose to see the browser while scraping or hide it.
    - **Products per Search Limit**: Set how many results to fetch for each medicine name.
    - **⚠️ Reset Database**: A button to completely clear the database, deleting all scraped data and search history.
- **🔍 Search Brands Tab:**
    - **Single Medicine**: Type a name to search for it specifically.
    - **Batch from List**: Paste multiple medicine names (one per line) to search in bulk. This list is saved to `brands_to_fetch.txt` for persistence.
- **📄 Scrape Details Tab:**
    - **Check Pending Brands**: Load the list of URLs found in the Search phase that are waiting for detailed scraping.
    - **Clear Pending Brands**: Use this to empty the queue.
    - **Start Detailed Scraping**: Begins the process of fetching compositions, marketers, and alternatives for each pending URL.
- **📊 View Data Tab:**
    - **Refresh Data**: Reload latest results from the database.
    - **Filtering**: Filter the scraped results by Name/Composition, Marketer, Generic availability, Price, and Discount.
    - **Export**: Download filtered data as **CSV** or **Excel** files.

#### CLI Mode
Navigate to the `medscraper/onemg` directory before running any of the scripts. Each scraper (`onemg_scraper_v2.py`, `platinumrx_scraper.py`, `truemeds_scraper.py`) supports the same set of command-line arguments.

#### Step 1: Scrape Product Links (Search Mode)
This mode reads medicine names from `brands_to_fetch.txt`, searches for them on the selected source, and stores the basic info and URLs in the database.

```bash
uv run python onemg_scraper_v2.py --brands --limit 20 --headless
# OR
uv run python platinumrx_scraper.py --brands --limit 20 --headless
# OR
uv run python truemeds_scraper.py --brands --limit 20 --headless
```
- `--brands`: Enables search mode using the input file.
- `--limit <number>`: Limits the number of products scraped per search term.
- `--headless`: Runs the browser in the background.

#### Step 2: Scrape Detailed Information (Detail Mode)
This mode retrieves the URLs collected in Step 1 from the database and scrapes full details for each.

```bash
uv run python onemg_scraper_v2.py --detail --headless
# OR
uv run python platinumrx_scraper.py --detail --headless
# OR
uv run python truemeds_scraper.py --detail --headless
```
- `--detail`: Enables detailed scraping for URLs found in the database.

```bash
uv run python onemg_scraper_v2.py --extract_scraped_data
```
- `--extract_scraped_data`: Save an Excel file with all scraped data.

### Command Line Arguments
| Argument | Description                                                         |
|---|---------------------------------------------------------------------|
| `medicine_name` | (Optional) Name of a single medicine to search for.                 |
| `--limit <int>` | Maximum number of products to scrape per search.                    |
| `--headless` | Run browser in headless mode.                                       |
| `--debug` | Enable DEBUG level logging for troubleshooting.                     |
| `--brands` | Extract brands using search terms from `brands_to_fetch.txt`.       |
| `--detail` | Extract full PDP data and substitutes using URLs from the database. |
| `--extract_scraped_data` | Save and excel file with all the scraped data.                      |

### Debugging and Logging

The 1mg scraper includes a robust logging system to help troubleshoot issues.

#### In Streamlit App:
- Toggle **Debug Mode** in the sidebar to enable detailed logging.
- When enabled, logs are written to `onemg/scraper.log`.
- A **Download Scraper Log** button will appear in the sidebar to easily access the log file.
- Use the **🗑️ Clear Log File** button to empty the log file when it gets too large.
- **📋 Scraper Logs**: A real-time, scrollable log viewer at the bottom of the page.
    - **Auto-Refresh**: Automatically updates every 2 seconds to show the latest scraper activity.
    - **Search & Filter**: Search logs by keyword or toggle to show only **ERRORS** to quickly identify problematic products.
    - **Scrollable**: A fixed-height container allows you to scroll through the last 500 lines of logs without cluttering the UI.
- The log file has an automatic **TTL of 6 hours** and will be cleared if it is older than that when the app is started or refreshed.

#### In CLI Mode:
- Use the `--debug` flag to see detailed `DEBUG` level logs in the console.
- Example: `uv run python onemg_scraper_v2.py --brands --debug`

### Data Schema
Data is stored in `onemg/db/db.duckdb` with the following main tables:
- `medicines`: Basic product info from search results.
- `medicine_details`: Queue of URLs to be scraped for details.
- `medicine_scraped_details`: Full product data (composition, substitutes, etc.).

### Docker Support

You can run the entire Streamlit app and scrapers using Docker. This ensures all dependencies (including Playwright and browsers) are correctly installed.

#### Prerequisites
- Docker and Docker Compose installed on your system.

#### Running with Docker Compose
1. Build and start the container:
   ```bash
   docker-compose up --build -d
   ```
2. Access the Streamlit app at: `http://localhost:8888`

#### Persistence
The `docker-compose.yml` is configured to persist your data even if the container is stopped or removed:
- **Database**: Stored in `./onemg/db/` on your host.
- **Brand List**: The `brands_to_fetch.txt` file is synced with your host.
- **Logs**: The `scraper.log` file is synced with your host.

#### Stopping the app
```bash
docker-compose down
```