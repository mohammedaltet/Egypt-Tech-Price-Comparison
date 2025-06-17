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
import traceback
import logging
from old_stores import *

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="Egypt Tech Price Comparison",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced session configuration with more robust settings
def get_session_config():
    return {
        'timeout': aiohttp.ClientTimeout(total=30, connect=10),  # Increased timeouts
        'connector': aiohttp.TCPConnector(
            limit=30,  # Reduced connection pool size
            limit_per_host=5,  # Reduced max connections per host
            ttl_dns_cache=300,
            use_dns_cache=True,
            enable_cleanup_closed=True,  # Clean up closed connections
        ),
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
    }

# Enhanced cache decorator
@cachetools.cached(cache=cachetools.TTLCache(maxsize=100, ttl=300))
def get_cached_results(query: str, stores_hash: str) -> pd.DataFrame:
    """Cache results for 5 minutes to avoid repeated scraping"""
    return None

class FastScraper:
    def __init__(self):
        self.session = None
        self.results_cache = cachetools.TTLCache(maxsize=50, ttl=300)
        
    async def __aenter__(self):
        session_config = get_session_config()
        self.session = aiohttp.ClientSession(**session_config)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def scrape_store_async(self, store_name: str, scraper_func, query: str, semaphore: asyncio.Semaphore, progress_callback=None) -> tuple:
        """Enhanced async wrapper with better error handling"""
        async with semaphore:
            try:
                # Add delay between requests to avoid rate limiting
                await asyncio.sleep(0.5)
                
                loop = asyncio.get_event_loop()
                # Increased timeout for problematic stores
                timeout = 45 if store_name in ['ElBadrGroup', 'ElnourTech', 'MaximumHardware'] else 30
                
                results = await asyncio.wait_for(
                    loop.run_in_executor(None, scraper_func, query),
                    timeout=timeout
                )
                
                if progress_callback:
                    progress_callback(store_name, len(results), None)
                
                logger.info(f"Successfully scraped {store_name}: {len(results)} products")
                return store_name, results, None
                
            except asyncio.TimeoutError:
                error_msg = f"Timeout after {timeout}s"
                logger.error(f"Timeout scraping {store_name}: {error_msg}")
                if progress_callback:
                    progress_callback(store_name, 0, error_msg)
                return store_name, [], error_msg
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error scraping {store_name}: {error_msg}")
                logger.error(traceback.format_exc())
                if progress_callback:
                    progress_callback(store_name, 0, error_msg)
                return store_name, [], error_msg

    async def scrape_multiple_stores(self, query: str, scrapers_dict: dict, max_concurrent: int = 5, progress_callback=None) -> pd.DataFrame:
        """Enhanced scraping with reduced concurrency for cloud stability"""
        # Reduced concurrency for cloud environments
        semaphore = asyncio.Semaphore(max_concurrent)
        
        tasks = [
            self.scrape_store_async(store_name, scraper_func, query, semaphore, progress_callback)
            for store_name, scraper_func in scrapers_dict.items()
        ]
        
        all_data = []
        successful_stores = []
        failed_stores = []
        
        for coro in asyncio.as_completed(tasks):
            try:
                store_name, results, error = await coro
                
                if error:
                    failed_stores.append((store_name, error))
                else:
                    all_data.extend(results)
                    successful_stores.append(store_name)
                    
            except Exception as e:
                logger.error(f"Unexpected error in scraping task: {e}")
        
        # Log summary
        logger.info(f"Scraping completed. Successful: {len(successful_stores)}, Failed: {len(failed_stores)}")
        if failed_stores:
            logger.warning(f"Failed stores: {failed_stores}")
        
        return pd.DataFrame(all_data)

def safe_scraper_wrapper(scraper_func, store_name):
    """Wrapper to make scraper functions more robust"""
    def wrapped_scraper(query):
        try:
            logger.info(f"Starting scrape for {store_name} with query: {query}")
            
            # Add retry logic for problematic stores
            max_retries = 3 if store_name in ['ElBadrGroup', 'ElnourTech', 'MaximumHardware'] else 1
            
            for attempt in range(max_retries):
                try:
                    results = scraper_func(query)
                    logger.info(f"Attempt {attempt + 1} for {store_name}: {len(results)} products found")
                    return results
                    
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed for {store_name}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
                    else:
                        raise e
                        
        except Exception as e:
            logger.error(f"All attempts failed for {store_name}: {e}")
            return []
            
    return wrapped_scraper

def scrape_all_optimized(query: str, selected_stores: List[str] = None) -> pd.DataFrame:
    """Enhanced optimized scraping with better error handling"""
    
    # All available scrapers with safe wrappers
    all_scrapers = {
        "Sigma": safe_scraper_wrapper(scrape_sigma, "Sigma"),
        "Elnekhely": safe_scraper_wrapper(scrape_elnekhely, "Elnekhely"),
        "ElBadrGroup": safe_scraper_wrapper(scrape_elbadrgroupe, "ElBadrGroup"),
        "BarakaComputer": safe_scraper_wrapper(scrape_barakacomputer, "BarakaComputer"),
        "DeltaComputer": safe_scraper_wrapper(scrape_deltacomputer, "DeltaComputer"),
        "ElnourTech": safe_scraper_wrapper(scrape_elnourtech, "ElnourTech"),
        "SolidHardware": safe_scraper_wrapper(scrape_solidhardware, "SolidHardware"),
        "AlFrensia": safe_scraper_wrapper(scrape_alfrensia, "AlFrensia"),
        "AHWStore": safe_scraper_wrapper(scrape_ahwstore, "AHWStore"),
        "KimoStore": safe_scraper_wrapper(scrape_kimostore, "KimoStore"),
        "UpToDate": safe_scraper_wrapper(scrape_uptodate, "UpToDate"),
        "ABCShop": safe_scraper_wrapper(scrape_abcshop, "ABCShop"),
        "CompuMarts": safe_scraper_wrapper(scrape_compumarts, "CompuMarts"),
        "CompuNileStore": safe_scraper_wrapper(scrape_compunilestore, "CompuNileStore"),
        "CompuScience": safe_scraper_wrapper(scrape_compuscience, "CompuScience"),
        "MaximumHardware": safe_scraper_wrapper(scrape_maximumhardware, "MaximumHardware"),
        "HighEndStore": safe_scraper_wrapper(scrape_highendstore, "HighEndStore"),
        "QuantumTechnology": safe_scraper_wrapper(scrape_quantumtechnology, "QuantumTechnology")
    }
    
    # Use selected stores or all stores
    scrapers_to_use = {}
    if selected_stores:
        scrapers_to_use = {name: func for name, func in all_scrapers.items() if name in selected_stores}
    else:
        scrapers_to_use = all_scrapers
    
    # Check cache first
    cache_key = f"{query}_{hash(frozenset(scrapers_to_use.keys()))}"
    
    if 'scraping_cache' not in st.session_state:
        st.session_state.scraping_cache = {}
    
    if cache_key in st.session_state.scraping_cache:
        cached_data, timestamp = st.session_state.scraping_cache[cache_key]
        if (datetime.now() - timestamp).seconds < 300:
            st.info("📦 Using cached results (less than 5 minutes old)")
            return cached_data
    
    # Enhanced progress tracking
    progress_bar = st.progress(0, text="🚀 Starting parallel scraping...")
    completed_stores = 0
    total_stores = len(scrapers_to_use)
    store_status = {}
    
    def update_progress(store_name: str, products_count: int, error: str):
        nonlocal completed_stores
        completed_stores += 1
        progress = completed_stores / total_stores
        
        if error:
            status_text = f"❌ Error with {store_name}: {error[:50]}... - {completed_stores}/{total_stores}"
            store_status[store_name] = f"❌ Error: {error}"
        else:
            status_text = f"✅ {store_name} done ({products_count} products) - {completed_stores}/{total_stores}"
            store_status[store_name] = f"✅ {products_count} products"
        
        progress_bar.progress(progress, text=status_text)
    
    try:
        # Always use threaded approach for cloud stability
        logger.info("Using threaded scraping for cloud compatibility")
        df = scrape_all_sequential_fallback(query, scrapers_to_use, progress_bar, total_stores, update_progress)
        
    except Exception as e:
        st.error(f"Error during scraping: {e}")
        logger.error(f"Scraping error: {e}")
        logger.error(traceback.format_exc())
        df = pd.DataFrame()
    
    # Complete progress bar
    progress_bar.progress(1.0, text="✅ Scraping completed!")
    
    # Show detailed status
    with st.expander("📊 Scraping Status Details", expanded=False):
        for store, status in store_status.items():
            st.write(f"**{store}:** {status}")
    
    if not df.empty:
        # Filter out products with price <= 1 EGP
        df = df[df['price'] > 1]
        
        # Apply filtering
        df_filtered = filter_products_by_all_words(df, query)
        
        # Remove duplicates
        df_filtered = df_filtered.drop_duplicates(subset=['name', 'price'], keep='first')
        
        # Cache results
        st.session_state.scraping_cache[cache_key] = (df_filtered, datetime.now())
        
        # Limit cache size
        if len(st.session_state.scraping_cache) > 10:
            oldest_key = min(st.session_state.scraping_cache.keys(), 
                           key=lambda k: st.session_state.scraping_cache[k][1])
            del st.session_state.scraping_cache[oldest_key]
        
        return df_filtered
    
    return df

def scrape_all_sequential_fallback(query: str, scrapers_dict: dict, progress_bar, total_stores: int, update_progress_callback) -> pd.DataFrame:
    """Enhanced fallback with better error handling and progress tracking"""
    all_data = []
    
    # Reduced max_workers for cloud stability
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_store = {
            executor.submit(scraper_func, query): store_name 
            for store_name, scraper_func in scrapers_dict.items()
        }
        
        completed = 0
        
        for future in as_completed(future_to_store):
            store_name = future_to_store[future]
            completed += 1
            
            try:
                # Increased timeout for problematic stores
                timeout = 60 if store_name in ['ElBadrGroup', 'ElnourTech', 'MaximumHardware'] else 30
                results = future.result(timeout=timeout)
                
                if results:
                    all_data.extend(results)
                    logger.info(f"Successfully scraped {store_name}: {len(results)} products")
                else:
                    logger.warning(f"No results from {store_name}")
                
                update_progress_callback(store_name, len(results), None)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error scraping {store_name}: {error_msg}")
                update_progress_callback(store_name, 0, error_msg)
    
    logger.info(f"Total products collected: {len(all_data)}")
    return pd.DataFrame(all_data)

# Keep all existing utility functions
def extract_price(price_str):
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None

def filter_products_by_all_words(df, search_query):
    """Filter products that contain ALL words from the search query"""
    if df.empty or not search_query:
        return df
    
    df = df.dropna(subset=['name'])
    df = df[df['name'].astype(str).str.strip() != '']
    
    search_words = search_query.lower().strip().split()
    
    if not search_words:
        return df
    
    def contains_all_words(product_name):
        if pd.isna(product_name) or product_name is None:
            return False
        
        product_name_lower = str(product_name).lower()
        return all(word in product_name_lower for word in search_words)
    
    df_filtered = df[df['name'].apply(contains_all_words)]
    df_filtered = df_filtered.sort_values('price', ascending=True)
    
    return df_filtered

def smart_search_terms(query):
    """Generate alternative search terms for better results"""
    alternatives = []
    query_lower = query.lower()
    
    if 'rtx' in query_lower:
        alternatives.append(query.replace('rtx', 'geforce rtx'))
        alternatives.append(query.replace('rtx', 'nvidia rtx'))
    
    if 'gtx' in query_lower:
        alternatives.append(query.replace('gtx', 'geforce gtx'))
        alternatives.append(query.replace('gtx', 'nvidia gtx'))
    
    if 'rx' in query_lower and 'rtx' not in query_lower:
        alternatives.append(query.replace('rx', 'radeon rx'))
        alternatives.append(query.replace('rx', 'amd rx'))
    
    if any(cpu in query_lower for cpu in ['i3', 'i5', 'i7', 'i9']):
        alternatives.append(query + ' processor')
        alternatives.append(query + ' cpu')
    
    if 'ryzen' in query_lower:
        alternatives.append(query + ' processor')
        alternatives.append(query + ' cpu')
    
    return alternatives[:2]

def extract_price_european_format(text):
    """Handle European number format like 31.999,00 EGP"""
    if not text:
        return None
    
    text = re.sub(r'[^\d.,]', '', text.strip())
    
    european_pattern = r'(\d{1,3}(?:\.\d{3})*),(\d{2})$'
    match = re.search(european_pattern, text)
    
    if match:
        whole_part = match.group(1).replace('.', '')
        decimal_part = match.group(2)
        return int(float(f"{whole_part}.{decimal_part}"))
    
    numbers = re.findall(r'\d+', text.replace(",", ""))
    return int("".join(numbers)) if numbers else None

def scrape_all(query, selected_stores=None):
    """Wrapper to maintain compatibility"""
    return scrape_all_optimized(query, selected_stores)

def apply_filters(df, min_price, max_price, stock_options, sort_option):
    """Apply all filters locally to the cached data"""
    if df.empty:
        return df
        
    df = df[(df['price'] >= min_price) & (df['price'] <= max_price)]
    
    if stock_options:
        df = df[df['availability'].isin(stock_options)]
    
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

initialize_session_state()

# Performance monitoring
if st.sidebar.button("🧹 Clear Cache"):
    st.session_state.scraping_cache = {}
    st.sidebar.success("Cache cleared!")

cache_size = len(st.session_state.scraping_cache)
if cache_size > 0:
    st.sidebar.info(f"📦 Cached searches: {cache_size}")

# Sidebar for filters and options
with st.sidebar:
    st.header("🔧 Search Options")
    
    st.subheader("Select Stores")
    all_stores = [
        "Sigma", "Elnekhely", "ElBadrGroup", "BarakaComputer",
        "DeltaComputer", "ElnourTech", "SolidHardware", "AlFrensia",
        "AHWStore", "KimoStore", "UpToDate", "ABCShop", "CompuMarts",
        "CompuNileStore", "CompuScience", "MaximumHardware",
        "QuantumTechnology", "HighEndStore"
    ]
    
    # Default selection includes the problematic stores
    default_stores = ["Sigma", "Elnekhely", "ElBadrGroup", "ElnourTech", "MaximumHardware", "BarakaComputer", "DeltaComputer", "SolidHardware"]
    
    selected_stores = st.multiselect(
        "Choose stores to search:",
        all_stores,
        default=default_stores,
        help="ElBadrGroup, ElnourTech, and MaximumHardware are included by default"
    )
    
    st.subheader("Price Range")
    min_price = st.number_input("Minimum Price (EGP)", min_value=0, value=0)
    max_price = st.number_input("Maximum Price (EGP)", min_value=0, value=100000)
    
    st.subheader("Sort By")
    sort_option = st.selectbox(
        "Sort results by:",
        ["Price (Low to High)", "Price (High to Low)", "Store Name", "Product Name"]
    )
    
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
    query = st.text_input("🔍 Search for a product:", placeholder="Enter product name...")
with col2:
    st.write("")
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
        df = scrape_all(query, selected_stores)
        
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
        
        st.info("""
        💡 **Search Tips:**
        - Use specific terms like "32gb ddr4 ram" instead of just "ram"
        - All words in your search must appear in the product name
        - Try different word combinations if no results appear
        """)
        
        alternatives = smart_search_terms(st.session_state.last_query)
        if alternatives:
            st.info("💡 Try these alternative searches:")
            for alt in alternatives:
                if st.button(f"🔍 Search for: {alt}"):
                    query = alt
                    st.session_state.last_query = ""
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
        
        # Show which of the problematic stores actually returned results
        problematic_stores = ['ElBadrGroup', 'ElnourTech', 'MaximumHardware']
        working_problematic = [store for store in problematic_stores if store in df_filtered['store'].values]
        if working_problematic:
            st.success(f"✅ Successfully retrieved data from: {', '.join(working_problematic)}")
        
        # Create tabs for different views
        tab1, tab2 = st.tabs(["📋 Product List", "📊 Price Analysis"])
        
        with tab1:
            st.subheader("🛍️ Available Products")
            
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
st.markdown(f"""
<div style='text-align: center; color: #666;'>
    <p>🇪🇬 Made for Egyptian tech enthusiasts • Updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    <p>💡 Tip: Use specific product names for better results</p>
    <p>🔍 All search words must appear in product names</p>
</div>
""", unsafe_allow_html=True)
