import logging
import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
import json
import os
import sys
import io
import time

# Setup Logging
LOG_FILE = os.path.join(os.path.dirname(__file__), 'scraper.log')

def setup_logging(debug_mode=False):
    level = logging.DEBUG if debug_mode else logging.INFO
    
    # TTL Check (6 hours = 21600 seconds)
    if os.path.exists(LOG_FILE):
        try:
            file_age = time.time() - os.path.getmtime(LOG_FILE)
            if file_age > 21600:
                with open(LOG_FILE, 'w'):
                    pass
                print(f"Log file cleared due to TTL (6 hours)")
        except Exception as e:
            print(f"Failed to clear log file during TTL check: {e}")

    # Reset existing handlers to allow reconfiguration
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging to both file and console
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Logging initialized at level: {logging.getLevelName(level)}")

# Add the current directory to sys.path to allow imports from onemg_scraper_v2 and db.db
sys.path.append(os.path.dirname(__file__))

# Import logic from the renamed scraper script
from onemg_scraper_v2 import main as main_1mg, main2 as main2_1mg
import platinumrx_scraper
import truemeds_scraper
from db.db import Database

SOURCES = {
    "1MG": {"search": main_1mg, "detail": main2_1mg},
    "PlatinumRx": {"search": platinumrx_scraper.main, "detail": None},
    "TrueMeds": {"search": truemeds_scraper.main, "detail": truemeds_scraper.main2},
}

# Set page config
st.set_page_config(
    page_title="1mg Medicine Scraper",
    page_icon="💊",
    layout="wide"
)

# Sidebar for configuration
st.sidebar.header("Configuration")
debug_mode = st.sidebar.checkbox("Debug Mode", value=False, help="Enable detailed logging and log to file.")
setup_logging(debug_mode)

if debug_mode:
    st.sidebar.info("Debug mode is ON. Logs are being saved to scraper.log")
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "rb") as f:
            st.sidebar.download_button(
                label="📥 Download Scraper Log",
                data=f,
                file_name="scraper.log",
                mime="text/plain"
            )
        
        if st.sidebar.button("🗑️ Clear Log File", help="Remove all contents from the log file."):
            try:
                # Close handlers before clearing to avoid issues on Windows
                for handler in logging.root.handlers[:]:
                    logging.root.removeHandler(handler)
                    handler.close()
                
                with open(LOG_FILE, 'w'):
                    pass
                st.sidebar.success("Log file cleared!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error clearing log file: {e}")

headless = st.sidebar.checkbox("Run Browser Headless", value=True)
limit = st.sidebar.number_input("Products per Search Limit", min_value=1, max_value=100, value=20)
source = st.sidebar.selectbox("Scrape Source", list(SOURCES.keys()))

# Initialize Database
db_path = os.path.join(os.path.dirname(__file__), 'db/db.duckdb')
dbase = Database(dbpath=db_path)
dbase.init()

# Database Management
st.sidebar.markdown("---")
st.sidebar.header("Database Management")
if st.sidebar.button("⚠️ Reset Database", help="This will delete ALL scraped data and search history! Use with caution."):
    try:
        dbase.del_()
        dbase.init()
        st.sidebar.success("Database reset successfully!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error resetting database: {e}")

# Title and Description
st.title("💊 Medicine Scraper")
st.markdown(f"""
This app allows you to scrape medicine information from **{source}**. 
You can search for brands to find product links, and then scrape detailed information including compositions and substitutes.
""")

# Main layout with tabs
tab1, tab2, tab3 = st.tabs(["🔍 Search Brands", "📄 Scrape Details", "📊 View Data"])

with tab1:
    st.header("Search for Medicine Brands")
    
    search_mode = st.radio("Search Mode", ["Single Medicine", "Batch from List"])
    
    if search_mode == "Single Medicine":
        medicine_name = st.text_input("Enter Medicine Name (e.g., Telma)")
        
        # Check if already searched
        is_searched = dbase.get_brand_search_status(medicine_name, source)
        if is_searched:
            st.info(f"'{medicine_name}' has already been searched on {source}.")
            
        if st.button("Start Search", key="single_search"):
            if medicine_name:
                with st.status(f"Searching for '{medicine_name}' on {source}...") as status:
                    asyncio.run(SOURCES[source]["search"](medicine_name=medicine_name, max_products=limit, headless=headless, dbase=dbase))
                    status.update(label=f"Completed search for '{medicine_name}' on {source}!", state="complete")
                st.success(f"Successfully scraped results for '{medicine_name}' from {source}")
                st.rerun()
            else:
                st.error("Please enter a medicine name.")
                
    else:
        # Load existing brands from file if it exists
        brands_file = os.path.join(os.path.dirname(__file__), 'brands_to_fetch.txt')
        default_brands = ""
        if os.path.exists(brands_file):
            with open(brands_file, 'r') as f:
                default_brands = f.read()
        
        brands_input = st.text_area("Enter Medicine Names (one per line)", value=default_brands, height=200)
        
        if st.button("Start Batch Search", key="batch_search"):
            brands = [b.strip() for b in brands_input.split('\n') if b.strip()]
            if brands:
                # Save to file for persistence
                with open(brands_file, 'w') as f:
                    f.write('\n'.join(brands))
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, brand in enumerate(brands):
                    status_text.text(f"Scraping brand {idx+1}/{len(brands)} from {source}: {brand}")
                    asyncio.run(SOURCES[source]["search"](medicine_name=brand, max_products=limit, headless=headless, dbase=dbase))
                    progress_bar.progress((idx + 1) / len(brands))
                
                status_text.text("Batch search completed!")
                st.success(f"Successfully scraped {len(brands)} brands.")
            else:
                st.error("Please enter at least one medicine name.")

with tab2:
    st.header("Scrape Detailed Product Information")
    
    col_b1, col_b2 = st.columns(2)
    
    if col_b1.button("Check Pending Brands"):
        st.session_state.show_pending = True
        
    if col_b2.button("Clear Pending Brands"):
        dbase.clear_pending_brands(source=source)
        st.session_state.show_pending = True
        st.success(f"Cleared all pending brands for {source} from database.")

    if st.session_state.get("show_pending"):
        # Get pending brands from DB
        pending_brands = dbase.get_brands(source=source)
        num_pending = len(pending_brands)
        
        st.info(f"Found **{num_pending}** product URLs for **{source}** in the database pending detailed scraping.")
        
        if num_pending > 0:
            if SOURCES[source]["detail"] is None:
                st.warning(f"{source} integration currently performs detailed scraping during the search phase. No further action needed.")
                with st.expander("Show Scraped Products (Listing)", expanded=False):
                    st.dataframe(pending_brands, width="stretch")
            else:
                with st.expander("Show Pending Products", expanded=True):
                    st.dataframe(pending_brands, width="stretch")
                    
                if st.button("Start Detailed Scraping", key="detail_scrape"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, (_, row) in enumerate(pending_brands.iterrows()):
                        url = row['url']
                        name = row['medicine_name']
                        status_text.text(f"Scraping details {idx+1}/{num_pending}: {name} ({url})")
                        asyncio.run(SOURCES[source]["detail"](medicine_url=url, headless=headless, dbase=dbase))
                        progress_bar.progress((idx + 1) / num_pending)
                    
                    status_text.text("Detailed scraping completed!")
                    st.success(f"Successfully scraped details for {num_pending} products.")
        else:
            st.warning("No pending URLs found. Please run 'Search Brands' first.")
    else:
        st.info("Click 'Check Pending Brands' to load the current scraping queue.")

with tab3:
    st.header("Scraped Data")
    
    if st.button("Refresh Data", key="refresh_data"):
        st.rerun()
        
    try:
        df = dbase.extract_scraped_data()
        if not df.empty:
            st.write(f"Total Scraped Products: {len(df)}")
            
            # --- Filter Section ---
            with st.expander("Filter Options", expanded=True):
                col_f1, col_f2, col_f3 = st.columns(3)
                
                # Search by name or composition
                search_text = col_f1.text_input("Search Name/Composition", "")
                
                # Filter by Source
                all_sources = sorted(df['source'].unique().tolist())
                selected_sources = col_f2.multiselect("Filter by Source", options=all_sources, default=all_sources)
                
                # Filter by Marketer
                marketers = sorted([m for m in df['medicine_marketer'].unique().tolist() if m])
                selected_marketers = col_f3.multiselect("Filter by Marketer", options=marketers)
                
                col_f4, col_f5, col_f6 = st.columns(3)
                
                # Generic Availability
                generic_opt = col_f4.radio("Generic Alternative Available", ["All", "Yes", "No"], horizontal=True)
                
                # Price Range
                price_data = df['medicine_selling_price'].dropna()
                if not price_data.empty:
                    min_price = float(price_data.min())
                    max_price = float(price_data.max())
                    if min_price == max_price:
                        col_f5.info(f"Price: ₹{min_price}")
                        price_range = (min_price, max_price)
                    else:
                        price_range = col_f5.slider("Price Range (₹)", min_price, max_price, (min_price, max_price))
                else:
                    price_range = (0.0, float('inf'))
                
                # Discount Range
                discount_data = df['medicine_discount'].dropna()
                if not discount_data.empty:
                    min_disc = float(discount_data.min())
                    max_disc = float(discount_data.max())
                    if min_disc == max_disc:
                        col_f6.info(f"Discount: {min_disc}%")
                        discount_range = (min_disc, max_disc)
                    else:
                        discount_range = col_f6.slider("Discount Range (%)", min_disc, max_disc, (min_disc, max_disc))
                else:
                    discount_range = (0.0, 100.0)
                
            # Apply Filters
            filtered_df = df.copy()
            
            if selected_sources:
                filtered_df = filtered_df[filtered_df['source'].isin(selected_sources)]
            
            if search_text:
                filtered_df = filtered_df[
                    filtered_df['medicine_name'].str.contains(search_text, case=False, na=False) |
                    filtered_df['medicine_composition'].str.contains(search_text, case=False, na=False)
                ]
            
            if selected_marketers:
                filtered_df = filtered_df[filtered_df['medicine_marketer'].isin(selected_marketers)]
                
            if generic_opt == "Yes":
                filtered_df = filtered_df[filtered_df['generic_alternative_available'] == True]
            elif generic_opt == "No":
                filtered_df = filtered_df[filtered_df['generic_alternative_available'] == False]
                
            filtered_df = filtered_df[
                (filtered_df['medicine_selling_price'] >= price_range[0]) &
                (filtered_df['medicine_selling_price'] <= price_range[1])
            ]
            
            filtered_df = filtered_df[
                (filtered_df['medicine_discount'] >= discount_range[0]) &
                (filtered_df['medicine_discount'] <= discount_range[1])
            ]
            
            st.write(f"Filtered Results: {len(filtered_df)}")
            
            # Export options (using filtered_df)
            col1, col2 = st.columns(2)
            
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            col1.download_button(
                label="Download as CSV",
                data=csv,
                file_name=f'scraped_data_{now}.csv',
                mime='text/csv',
                key="download_csv"
            )
            
            # Excel export (using io.BytesIO)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False)
            col2.download_button(
                label="Download as Excel",
                data=buffer.getvalue(),
                file_name=f'scraped_data_{now}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key="download_excel"
            )
            
            st.dataframe(filtered_df)
        else:
            st.write("No data found in the database.")
    except Exception as e:
        st.error(f"Error retrieving/filtering data: {e}")

# Footer
st.markdown("---")
st.markdown("Developed with ❤️ for Multi-Source Medicine Scraping")
