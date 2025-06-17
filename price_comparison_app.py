import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime
import time
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
import functools
import cachetools
from typing import List, Dict, Any

from functools import wraps
from old_stores import *


# Configure Streamlit page
st.set_page_config(
    page_title="Egypt Tech Price Comparison",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session configuration (connector will be created in async context)
def get_session_config():
    return {
        'timeout': aiohttp.ClientTimeout(total=15, connect=8),
        'connector': aiohttp.TCPConnector(
            limit=50,  # Total connection pool size
            limit_per_host=8,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        ),
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    }

# Cache for storing recent search results (TTL: 5 minutes)
@cachetools.cached(cache=cachetools.TTLCache(maxsize=100, ttl=300))
def get_cached_results(query: str, stores_hash: str) -> pd.DataFrame:
    """Cache results for 5 minutes to avoid repeated scraping"""
    return None  # This will be handled by the caching decorator

class FastScraper:
    def __init__(self):
        self.session = None
        self.results_cache = cachetools.TTLCache(maxsize=50, ttl=300)  # 5 min cache
        
    async def __aenter__(self):
        session_config = get_session_config()
        self.session = aiohttp.ClientSession(**session_config)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def scrape_store_async(self, store_name: str, scraper_func, query: str, semaphore: asyncio.Semaphore, progress_callback=None) -> tuple:
        """Async wrapper for store scraping with rate limiting"""
        async with semaphore:  # Limit concurrent requests
            try:
                # Run the synchronous scraper in a thread pool
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, scraper_func, query)
                if progress_callback:
                    progress_callback(store_name, len(results), None)
                return store_name, results, None
            except Exception as e:
                if progress_callback:
                    progress_callback(store_name, 0, str(e))
                return store_name, [], str(e)
    
    async def scrape_multiple_stores(self, query: str, scrapers_dict: dict, max_concurrent: int = 10, progress_callback=None) -> pd.DataFrame:
        """Scrape multiple stores concurrently with rate limiting"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Create tasks for all scrapers
        tasks = [
            self.scrape_store_async(store_name, scraper_func, query, semaphore, progress_callback)
            for store_name, scraper_func in scrapers_dict.items()
        ]
        
        all_data = []
        
        # Process results as they complete
        for coro in asyncio.as_completed(tasks):
            store_name, results, error = await coro
            
            if not error:
                all_data.extend(results)
        
        return pd.DataFrame(all_data)

def scrape_all_optimized(query: str, selected_stores: List[str] = None) -> pd.DataFrame:
    """Optimized scraping function with parallel execution and caching"""
    
    # All available scrapers
    all_scrapers = {
        "Sigma": scrape_sigma,
        "Elnekhely": scrape_elnekhely,
        "ElBadrGroup": scrape_elbadrgroupe,
        "BarakaComputer": scrape_barakacomputer,
        "DeltaComputer": scrape_deltacomputer,
        "ElnourTech": scrape_elnourtech,
        "SolidHardware": scrape_solidhardware,
        "AlFrensia": scrape_alfrensia,
        "AHWStore": scrape_ahwstore,
        "KimoStore": scrape_kimostore,
        "UpToDate": scrape_uptodate,
        "ABCShop": scrape_abcshop,
        "CompuMarts": scrape_compumarts,
        "CompuNileStore": scrape_compunilestore,
        "CompuScience": scrape_compuscience,
        "MaximumHardware": scrape_maximumhardware,
        "HighEndStore": scrape_highendstore,
        "QuantumTechnology": scrape_quantumtechnology
    }
    
    # Use selected stores or all stores
    scrapers_to_use = {}
    if selected_stores:
        scrapers_to_use = {name: func for name, func in all_scrapers.items() if name in selected_stores}
    else:
        scrapers_to_use = all_scrapers
    
    # Check cache first
    cache_key = f"{query}_{hash(frozenset(scrapers_to_use.keys()))}"
    
    # Create cache in session state if it doesn't exist
    if 'scraping_cache' not in st.session_state:
        st.session_state.scraping_cache = {}
    
    # Check if we have cached results (less than 5 minutes old)
    if cache_key in st.session_state.scraping_cache:
        cached_data, timestamp = st.session_state.scraping_cache[cache_key]
        if (datetime.now() - timestamp).seconds < 300:  # 5 minutes
            st.info("📦 Using cached results (less than 5 minutes old)")
            return cached_data
    
    # Show single progress bar
    progress_bar = st.progress(0, text="🚀 Starting parallel scraping...")
    completed_stores = 0
    total_stores = len(scrapers_to_use)
    
    def update_progress(store_name: str, products_count: int, error: str):
        nonlocal completed_stores
        completed_stores += 1
        progress = completed_stores / total_stores
        
        if error:
            status_text = f"❌ Error with {store_name} - {completed_stores}/{total_stores} completed"
        else:
            status_text = f"✅ {store_name} done ({products_count} products) - {completed_stores}/{total_stores} completed"
        
        progress_bar.progress(progress, text=status_text)
    
    try:
        # Check if there's already an event loop running
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, we can't use run_until_complete
            st.warning("🔄 Using threaded scraping (async context detected)...")
            df = scrape_all_sequential_fallback(query, scrapers_to_use, progress_bar, total_stores)
        except RuntimeError:
            # No event loop running, safe to create one
            async def run_scraping():
                async with FastScraper() as scraper:
                    return await scraper.scrape_multiple_stores(query, scrapers_to_use, max_concurrent=10, progress_callback=update_progress)
            
            # Use asyncio.run for Python 3.7+
            try:
                df = asyncio.run(run_scraping())
            except Exception as e:
                st.warning(f"Async scraping failed: {e}, falling back to threaded approach...")
                df = scrape_all_sequential_fallback(query, scrapers_to_use, progress_bar, total_stores)
        
    except Exception as e:
        st.error(f"Error during parallel scraping: {e}")
        # Fallback to sequential scraping
        st.warning("🔄 Falling back to sequential scraping...")
        df = scrape_all_sequential_fallback(query, scrapers_to_use, progress_bar, total_stores)
    
    # Complete progress bar
    progress_bar.progress(1.0, text="✅ Scraping completed!")
    
    if not df.empty:
        # Filter out products with price <= 1 EGP (likely parsing errors)
        df = df[df['price'] > 1]
        
        # Apply all-words filtering
        df_filtered = filter_products_by_all_words(df, query)
        
        # Remove duplicates
        df_filtered = df_filtered.drop_duplicates(subset=['name', 'price'], keep='first')
        
        # Cache the results
        st.session_state.scraping_cache[cache_key] = (df_filtered, datetime.now())
        
        # Limit cache size
        if len(st.session_state.scraping_cache) > 10:
            # Remove oldest entries
            oldest_key = min(st.session_state.scraping_cache.keys(), 
                           key=lambda k: st.session_state.scraping_cache[k][1])
            del st.session_state.scraping_cache[oldest_key]
        
        return df_filtered
    
    return df

def scrape_all_sequential_fallback(query: str, scrapers_dict: dict, progress_bar, total_stores: int) -> pd.DataFrame:
    """Fallback sequential scraping with threading"""
    all_data = []
    
    # Use ThreadPoolExecutor for improved sequential performance
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all scraping tasks
        future_to_store = {
            executor.submit(scraper_func, query): store_name 
            for store_name, scraper_func in scrapers_dict.items()
        }
        
        completed = 0
        
        # Process completed tasks
        for future in as_completed(future_to_store):
            store_name = future_to_store[future]
            completed += 1
            
            try:
                results = future.result(timeout=15)  # 15 second timeout per store
                all_data.extend(results)
                status_text = f"✅ {store_name} completed ({len(results)} products) - {completed}/{total_stores}"
            except Exception as e:
                status_text = f"❌ Error with {store_name} - {completed}/{total_stores}"
            
            # Update progress
            progress_bar.progress(completed / total_stores, text=status_text)
    
    return pd.DataFrame(all_data)

# Keep all your existing utility functions
def extract_price(price_str):
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None

def filter_products_by_all_words(df, search_query):
    """Filter products that contain ALL words from the search query"""
    if df.empty or not search_query:
        return df
    
    # Clean the data first - remove rows with invalid names
    df = df.dropna(subset=['name'])  # Remove rows where name is NaN
    df = df[df['name'].astype(str).str.strip() != '']  # Remove empty strings
    
    # Convert search query to lowercase and split into words
    search_words = search_query.lower().strip().split()
    
    if not search_words:
        return df
    
    # Filter products that contain ALL search words
    def contains_all_words(product_name):
        if pd.isna(product_name) or product_name is None:
            return False
        
        product_name_lower = str(product_name).lower()
        return all(word in product_name_lower for word in search_words)
    
    # Apply the filter
    df_filtered = df[df['name'].apply(contains_all_words)]
    
    # Sort by price (lowest first)
    df_filtered = df_filtered.sort_values('price', ascending=True)
    
    return df_filtered

def smart_search_terms(query):
    """Generate alternative search terms for better results"""
    alternatives = []
    query_lower = query.lower()
    
    # Graphics card alternatives
    if 'rtx' in query_lower:
        alternatives.append(query.replace('rtx', 'geforce rtx'))
        alternatives.append(query.replace('rtx', 'nvidia rtx'))
    
    if 'gtx' in query_lower:
        alternatives.append(query.replace('gtx', 'geforce gtx'))
        alternatives.append(query.replace('gtx', 'nvidia gtx'))
    
    if 'rx' in query_lower and 'rtx' not in query_lower:
        alternatives.append(query.replace('rx', 'radeon rx'))
        alternatives.append(query.replace('rx', 'amd rx'))
    
    # CPU alternatives
    if any(cpu in query_lower for cpu in ['i3', 'i5', 'i7', 'i9']):
        alternatives.append(query + ' processor')
        alternatives.append(query + ' cpu')
    
    if 'ryzen' in query_lower:
        alternatives.append(query + ' processor')
        alternatives.append(query + ' cpu')
    
    return alternatives[:2]  # Limit to 2 alternatives to avoid too many requests

def extract_price_european_format(text):
    """Handle European number format like 31.999,00 EGP"""
    if not text:
        return None
    
    # Remove currency symbols and extra spaces
    text = re.sub(r'[^\d.,]', '', text.strip())
    
    # Check if it's European format (ends with ,XX)
    european_pattern = r'(\d{1,3}(?:\.\d{3})*),(\d{2})$'
    match = re.search(european_pattern, text)
    
    if match:
        # European format: 31.999,00 -> 31999.00
        whole_part = match.group(1).replace('.', '')  # Remove thousands separators
        decimal_part = match.group(2)
        return int(float(f"{whole_part}.{decimal_part}"))
    
    # Fallback to original method
    numbers = re.findall(r'\d+', text.replace(",", ""))
    return int("".join(numbers)) if numbers else None

# Replace your scrape_all function with scrape_all_optimized
def scrape_all(query, selected_stores=None):
    """Wrapper to maintain compatibility"""
    return scrape_all_optimized(query, selected_stores)

# Add these new functions for filter application
def apply_filters(df, min_price, max_price, stock_options, sort_option):
    """Apply all filters locally to the cached data"""
    if df.empty:
        return df
        
    # Apply price filter
    df = df[(df['price'] >= min_price) & (df['price'] <= max_price)]
    
    # Apply stock filter
    if stock_options:
        df = df[df['availability'].isin(stock_options)]
    
    # Apply sorting
    if sort_option == "Price (Low to High)":
        df = df.sort_values('price')
    elif sort_option == "Price (High to Low)":
        df = df.sort_values('price', ascending=False)
    elif sort_option == "Store Name":
        df = df.sort_values('store')
    elif sort_option == "Product Name":
        df = df.sort_values('name')
        
    return df

def initialize_session_state():
    """Initialize session state variables"""
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = pd.DataFrame()
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""
    if 'last_stores' not in st.session_state:
        st.session_state.last_stores = []
    if 'scraping_cache' not in st.session_state:
        st.session_state.scraping_cache = {}

# === Enhanced Streamlit UI ===
st.title("💻 Egypt Tech Price Comparison")
st.markdown("### Find the best tech deals across Egyptian online stores!")

# Initialize session state
initialize_session_state()

# Performance monitoring
if st.sidebar.button("🧹 Clear Cache"):
    st.session_state.scraping_cache = {}
    st.sidebar.success("Cache cleared!")

# Show cache status
cache_size = len(st.session_state.scraping_cache)
if cache_size > 0:
    st.sidebar.info(f"📦 Cached searches: {cache_size}")

# Sidebar for filters and options
with st.sidebar:
    st.header("🔧 Search Options")
    
    # Store selection
    st.subheader("Select Stores")
    all_stores = [
        "Sigma", "Elnekhely", "ElBadrGroup", "BarakaComputer",
        "DeltaComputer", "ElnourTech", "SolidHardware", "AlFrensia",
        "AHWStore", "KimoStore", "UpToDate", "ABCShop", "CompuMarts",
        "CompuNileStore", "CompuScience", "MaximumHardware",
        "QuantumTechnology", "HighEndStore"
    ]

    selected_stores = st.multiselect(
        "Choose stores to search:",
        all_stores,
        default=all_stores[:8]  # Default to first 8 stores for faster initial loading
    )
    
    # Price range filter
    st.subheader("Price Range")
    min_price = st.number_input("Minimum Price (EGP)", min_value=0, value=0)
    max_price = st.number_input("Maximum Price (EGP)", min_value=0, value=100000)
    
    # Sort options
    st.subheader("Sort By")
    sort_option = st.selectbox(
        "Sort results by:",
        ["Price (Low to High)", "Price (High to Low)", "Store Name", "Product Name"]
    )
    
    # Stock availability filter
    st.subheader("📦 Stock Status")
    stock_options = st.multiselect(
        "Filter by availability:",
        ["In Stock", "Out of Stock", "Check site"],
        default=["In Stock", "Out of Stock", "Check site"],
        help="Select which stock statuses to include in results"
    )

# Main search interface
col1, col2 = st.columns([3, 1])

with col1:
    query = st.text_input("🔍 Search for a product (e.g. 32gb ddr4 ram, RTX 4070, iPhone 15):", placeholder="Enter product name...")

with col2:
    st.write("")  # Space for alignment
    search_button = st.button("🔍 Search", type="primary")

# Check if we need to fetch new data
need_new_data = (
    search_button and query and 
    (query != st.session_state.last_query or 
     selected_stores != st.session_state.last_stores)
)

# Fetch new data only when necessary
if need_new_data:
    with st.spinner("🔄 Fetching data from selected stores..."):
        # Fetch new data
        df = scrape_all(query, selected_stores)
        
        # Update session state
        st.session_state.raw_data = df
        st.session_state.last_query = query
        st.session_state.last_stores = selected_stores

# Apply filters to cached data
if not st.session_state.raw_data.empty:
    df_filtered = apply_filters(
        st.session_state.raw_data,
        min_price,
        max_price,
        stock_options,
        sort_option
    )
    
    if df_filtered.empty:
        st.warning("❌ No results found with current filters. Try adjusting your filters or search terms.")
        
        # Show search tips
        st.info("""
        💡 **Search Tips:**
        - Use specific terms like "32gb ddr4 ram" instead of just "ram"
        - All words in your search must appear in the product name
        - Try different word combinations if no results appear
        """)
        
        # Suggest alternative search terms
        alternatives = smart_search_terms(st.session_state.last_query)
        if alternatives:
            st.info("💡 Try these alternative searches:")
            for alt in alternatives:
                if st.button(f"🔍 Search for: {alt}"):
                    query = alt
                    st.session_state.last_query = ""  # Force new search
                    st.rerun()
    else:
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Results", len(df_filtered))
        with col2:
            st.metric("Lowest Price", f"{df_filtered['price'].min():,} EGP")
        with col3:
            st.metric("Highest Price", f"{df_filtered['price'].max():,} EGP")
        with col4:
            st.metric("Stores Found", df_filtered['store'].nunique())
        
        # Create tabs for different views
        tab1, tab2 = st.tabs(["📋 Product List", "📊 Price Analysis"])
        
        with tab1:
            st.subheader("🛍️ Available Products")
            
            # Display products in a more attractive format
            for i, row in df_filtered.iterrows():
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    
                    with col1:
                        st.markdown(f"**[{row['name']}]({row['url']})**")
                        
                        stock_color = {
                            "In Stock": "🟢",
                            "Out of Stock": "🔴", 
                            "Check site": "⚪"
                        }.get(row['availability'], "⚪")
                        
                        st.caption(f"🏪 {row['store']} • {stock_color} {row['availability']}")
                    
                    with col2:
                        st.markdown(f"### 💰 {row['price']:,} EGP")
                    
                    with col3:
                        if row['availability'] == "Out of Stock":
                            st.button("❌ Out of Stock", disabled=True, key=f"disabled_{i}")
                        else:
                            st.link_button("🛒 View Product", row['url'])
                    
                    st.divider()
        
        with tab2:
            st.subheader("📊 Price Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Price Statistics:**")
                stats_df = pd.DataFrame({
                    'Metric': ['Average Price', 'Median Price', 'Price Range', 'Standard Deviation'],
                    'Value': [
                        f"{df_filtered['price'].mean():.0f} EGP",
                        f"{df_filtered['price'].median():.0f} EGP",
                        f"{df_filtered['price'].max() - df_filtered['price'].min():,} EGP",
                        f"{df_filtered['price'].std():.0f} EGP"
                    ]
                })
                st.dataframe(stats_df, hide_index=True)
            
            with col2:
                st.write("**Store Comparison:**")
                store_stats = df_filtered.groupby('store').agg({
                    'price': ['count', 'mean', 'min', 'max']
                }).round(0)
                store_stats.columns = ['Products', 'Avg Price', 'Min Price', 'Max Price']
                st.dataframe(store_stats)

elif query:
    st.info("👆 Click the Search button to find products!")

# Sidebar clear results button
with st.sidebar:
    if not st.session_state.raw_data.empty:
        if st.button("🗑️ Clear Results"):
            st.session_state.raw_data = pd.DataFrame()
            st.session_state.last_query = ""
            st.session_state.last_stores = []
            st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🇪🇬 Made for Egyptian tech enthusiasts • Updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """</p>
    <p>💡 Tip: Use specific product names for better results (e.g., "RTX 4070 Super" instead of just "graphics card")</p>
    <p>🔍 All search words must appear in product names (e.g., "32gb ddr4 ram" will only show products containing all three terms)</p>
</div>
""", unsafe_allow_html=True)
