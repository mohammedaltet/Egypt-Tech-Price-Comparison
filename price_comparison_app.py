
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
from difflib import SequenceMatcher

# Configure Streamlit page
st.set_page_config(
    page_title="Egypt Tech Price Comparison",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

def extract_price(price_str):
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None

def calculate_relevance_score(product_name, search_query):
    """
    Calculate how relevant a product is to the search query
    Returns a score between 0 and 1 (1 being most relevant)
    """
    product_name = product_name.lower().strip()
    search_query = search_query.lower().strip()
    
    # Split search query into individual terms
    search_terms = search_query.split()
    
    # Calculate base similarity using SequenceMatcher
    base_similarity = SequenceMatcher(None, product_name, search_query).ratio()
    
    # Check for exact matches of search terms
    exact_matches = 0
    partial_matches = 0
    
    for term in search_terms:
        if term in product_name:
            exact_matches += 1
        elif any(term in word for word in product_name.split()):
            partial_matches += 1
    
    # Calculate weighted score
    term_match_score = (exact_matches * 2 + partial_matches) / (len(search_terms) * 2)
    
    # Combine base similarity with term matching
    final_score = (base_similarity * 0.3) + (term_match_score * 0.7)
    
    return final_score

def filter_relevant_products(df, search_query, min_relevance=0.3):
    """
    Filter products based on relevance to search query
    """
    if df.empty:
        return df
    
    # Calculate relevance scores
    df['relevance_score'] = df['name'].apply(
        lambda x: calculate_relevance_score(x, search_query)
    )
    
    # Apply additional filters for common irrelevant items
    irrelevant_keywords = [
        'thermal pad', 'thermal paste', 'cable', 'screw', 'bracket',
        'case', 'power supply', 'psu', 'cooling', 'fan', 'rgb',
        'keyboard', 'mouse', 'monitor', 'speaker', 'headset',
        'chair', 'desk', 'webcam', 'microphone'
    ]
    
    # Special handling for graphics card searches
    if any(gpu_term in search_query.lower() for gpu_term in ['rtx', 'gtx', 'rx', 'graphics', 'gpu', 'vga']):
        gpu_keywords = ['rtx', 'gtx', 'rx', 'graphics', 'gpu', 'vga', 'geforce', 'radeon']
        # Boost relevance for products containing GPU keywords
        for idx, row in df.iterrows():
            if any(gpu_word in row['name'].lower() for gpu_word in gpu_keywords):
                df.at[idx, 'relevance_score'] += 0.2
        
        # Penalize clearly unrelated items for GPU searches
        for idx, row in df.iterrows():
            if any(bad_word in row['name'].lower() for bad_word in irrelevant_keywords):
                df.at[idx, 'relevance_score'] -= 0.3
    
    # Filter by minimum relevance score
    df_filtered = df[df['relevance_score'] >= min_relevance]
    
    # Sort by relevance score (descending) then by price
    df_filtered = df_filtered.sort_values(['relevance_score', 'price'], ascending=[False, True])
    
    return df_filtered

def smart_search_terms(query):
    """
    Generate alternative search terms for better results
    """
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
    """
    Handle European number format like 31.999,00 EGP
    where dots are thousands separators and commas are decimal separators
    """
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

# ✅ 1. Sigma Computer
def scrape_sigma(query):
    url = "https://www.sigma-computer.com/searchautocomplete"
    params = {"keyword": query}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for li in soup.select("ul#country-list li"):
            a = li.find("a")
            span = li.find("span")
            if a and span:
                price = extract_price(span.text)
                if price and price > 1:  # Filter out 1 EGP prices
                    results.append({
                        "name": a.text.strip(),
                        "url": "https://www.sigma-computer.com/" + a['href'],
                        "price": price,
                        "store": "Sigma",
                        "availability": "Check site"
                    })
        return results
    except Exception as e:
        st.error(f"Error scraping Sigma: {e}")
        return []

# ✅ 2. Elnekhely Technology (JSON)
def scrape_elnekhely(query):
    url = f"https://www.elnekhelytechnology.com/index.php?route=journal3/search&search={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        results = []

        if r.status_code == 200 and "response" in r.json():
            for item in r.json()["response"]:
                if "href" in item and "name" in item and (item.get("special") or item.get("price")):
                    price_str = item.get("special") or item.get("price")
                    price = extract_price(price_str)
                    if price and price > 1:  # Filter out 1 EGP prices
                        results.append({
                            "name": item["name"],
                            "url": item["href"],
                            "price": price,
                            "store": "Elnekhely",
                            "availability": "In Stock" if item.get("quantity", 0) > 0 else "Out of Stock"
                        })
        return results
    except Exception as e:
        st.error(f"Error scraping Elnekhely: {e}")
        return []

#✅ 3. elbadrgroupeg
def scrape_elbadrgroupe(query):
    url = f"https://elbadrgroupeg.store/index.php?route=journal3/search&search={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        results = []

        if r.status_code == 200:
            try:
                data = r.json()
                if "response" in data:
                    for item in data["response"]:
                        if "name" in item and (item.get("special") or item.get("price")):
                            price_str = item.get("special") or item.get("price")
                            price = extract_price(price_str)
                            if price and price > 1:  # Filter out 1 EGP prices
                                results.append({
                                    "name": item["name"],
                                    "url": item.get("href", "#"),
                                    "price": price,
                                    "store": "ElBadrGroup",
                                    "availability": "In Stock" if item.get("quantity", 0) > 0 else "Out of Stock"
                                })
            except Exception as e:
                print("❌ Error parsing JSON from ElBadrGroup:", e)

        return results
    except Exception as e:
        st.error(f"Error scraping ElBadrGroup: {e}")
        return []

#✅ 4. barakacomputer
def scrape_barakacomputer(query):
    def extract_price_from_html(html_text):
        soup = BeautifulSoup(html_text, "html.parser")
        price_tag = soup.find("ins") or soup.find("span", class_="woocommerce-Price-amount")
        if price_tag:
            text = price_tag.get_text()
            numbers = re.findall(r'\d+', text.replace(",", ""))
            return int("".join(numbers)) if numbers else None
        return None

    url = f"https://barakacomputer.net/?wc-ajax=nasa_search_products&s={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        results = []

        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, list):
                    for item in data:
                        name = item.get("title")
                        link = item.get("url")
                        price_html = item.get("price")
                        if name and link and price_html:
                            price = extract_price_from_html(price_html)
                            if price and price > 1:  # Filter out 1 EGP prices
                                results.append({
                                    "name": name.strip(),
                                    "url": link,
                                    "price": price,
                                    "store": "BarakaComputer",
                                    "availability": "Check site"
                                })
            except Exception as e:
                print("❌ Error parsing JSON from BarakaComputer:", e)

        return results
    except Exception as e:
        st.error(f"Error scraping BarakaComputer: {e}")
        return []

#✅ 5. delta-computer
def scrape_deltacomputer(query):
    def extract_price(text):
        numbers = re.findall(r'\d+', str(text).replace(",", ""))
        return int("".join(numbers)) if numbers else None

    url = f"https://api.delta-computer.net/api/products?search={query}&per_page=50"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        results = []

        if r.status_code == 200:
            try:
                data = r.json()
                if "data" in data and isinstance(data["data"], list):
                    for item in data["data"]:
                        name = item.get("name") or item.get("title")
                        link = "https://delta-computer.net/product/" + str(item.get("slug", ""))
                        price = extract_price(item.get("price"))
                        if name and price and price > 1:  # Filter out 1 EGP prices
                            results.append({
                                "name": name.strip(),
                                "url": link,
                                "price": price,
                                "store": "DeltaComputer",
                                "availability": "Check site"
                            })
            except Exception as e:
                print("❌ Error parsing JSON from DeltaComputer:", e)

        return results
    except Exception as e:
        st.error(f"Error scraping DeltaComputer: {e}")
        return []

#✅ 6. elnour-tech (FIXED)
def scrape_elnourtech(query):
    def extract_price_from_html(html_text):
        soup = BeautifulSoup(html_text, "html.parser")
        price_tag = soup.select_one("ins") or soup.select_one("span.amount") or soup
        if price_tag:
            # Use the European format handler for ElnourTech
            return extract_price_european_format(price_tag.get_text())
        return None

    url = f"https://elnour-tech.com/wp-admin/admin-ajax.php?action=woodmart_ajax_search&number=20&post_type=product&query={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        results = []

        if r.status_code == 200:
            try:
                data = r.json()
                for item in data.get("suggestions", []):
                    name = item.get("value")
                    link = item.get("permalink")
                    price_html = item.get("price")
                    price = extract_price_from_html(price_html) if price_html else None

                    if name and link and price and price > 1:  # Filter out 1 EGP prices
                        results.append({
                            "name": name.strip(),
                            "url": link,
                            "price": price,
                            "store": "ElnourTech",
                            "availability": "Check site"
                        })
            except Exception as e:
                print("❌ Error parsing JSON from ElnourTech:", e)

        return results
    except Exception as e:
        st.error(f"Error scraping ElnourTech: {e}")
        return []
        
#✅ 7. solidhardware
def scrape_solidhardware(query):
    import requests
    from bs4 import BeautifulSoup
    import re

    def extract_price_from_html(html_text):
        soup = BeautifulSoup(html_text, "html.parser")
        price_tag = soup.select_one("ins .woocommerce-Price-amount") or soup.select_one(".woocommerce-Price-amount")
        if price_tag:
            text = price_tag.get_text()
            # إزالة الفواصل من الرقم وتحويله إلى int
            numbers = re.findall(r'\d+', text.replace(",", ""))
            return int("".join(numbers)) if numbers else None
        return None

    url = f"https://solidhardware.store/wp-admin/admin-ajax.php?action=woodmart_ajax_search&number=20&post_type=product&query={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    r = requests.get(url, headers=headers)
    results = []

    if r.status_code == 200:
        try:
            data = r.json()
            for item in data.get("suggestions", []):
                name = item.get("value")
                link = item.get("permalink")
                price_html = item.get("price")
                price = extract_price_from_html(price_html) if price_html else None

                if name and link and price:
                    results.append({
                        "name": name.strip(),
                        "url": link,
                        "price": price,
                        "store": "SolidHardware",
                        "availability": "Check site"
                    })
        except Exception as e:
            print("❌ Error parsing JSON from SolidHardware:", e)

    return results

#✅ 8. alfrensia
import requests
from bs4 import BeautifulSoup

def extract_price(html_price):
    try:
        soup = BeautifulSoup(html_price, "html.parser")
        price_text = soup.get_text(strip=True).replace(",", "")
        return int("".join(filter(str.isdigit, price_text)))
    except:
        return None

def scrape_alfrensia(query):
    url = f"https://alfrensia.com/wp-admin/admin-ajax.php?action=flatsome_ajax_search_products&query={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest"
    }

    response = requests.get(url, headers=headers)
    results = []

    if response.status_code == 200:
        data = response.json()
        suggestions = data.get("suggestions", [])
        for item in suggestions:
            title = item.get("value", "").strip()
            url = item.get("url", "").strip()
            price_html = item.get("price", "")
            price = extract_price(price_html)

            results.append({
                "name": title,
                "url": url,
                "price": price,
                "store": "Alfrensia",
                "availability": "Available"
            })
    return results

# ✅ 9. ahw.store
def scrape_ahwstore(query):
    url = f"https://ahw.store/index.php?route=journal3/search&search={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)
    results = []

    if response.status_code == 200:
        try:
            data = response.json()
            for item in data.get("response", []):
                name = item.get("name")
                link = item.get("href")
                price_str = item.get("special") or item.get("price")
                price = extract_price(price_str)

                if name and link and price:
                    results.append({
                        "name": name.strip(),
                        "url": link.strip(),
                        "price": price,
                        "store": "AHW Store",
                        "availability": "In Stock" if item.get("quantity", 0) > 0 else "Out of Stock"
                    })
        except Exception as e:
            print("❌ Error parsing JSON from AHW Store:", e)

    return results

# ✅ 10. kimostore
def get_price_from_product_page(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            selectors = [
                '.price-item--regular',
                '.price__regular .price-item',
                'span.price',
                '.product__price span',
                '.product__price .money',
                '[data-product-price]',
            ]
            for selector in selectors:
                tag = soup.select_one(selector)
                if tag:
                    text = tag.get_text(strip=True)
                    match = re.search(r'[\d.,]+', text)
                    if match:
                        raw = match.group().replace(",", "")
                        try:
                            return int(float(raw))
                        except:
                            return int(re.sub(r'\D', '', raw))
    except Exception as e:
        print("❌ Error extracting price:", e)
    return None

def scrape_kimostore(query):
    url = "https://kimostore.net/search/suggest"
    params = {
        "section_id": "predictive-search",
        "q": query,
        "resources[limit]": 20,
        "resources[limit_scope]": "each",
        "resources[options][fields]": "title,product_type,variants.title,variants.sku,vendor"
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://kimostore.net/",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            products = data.get("resources", {}).get("results", {}).get("products", [])
            results = []
            for p in products:
                title = p.get("title", "").strip()
                url_suffix = p.get("url", "#")
                full_url = f"https://kimostore.net{url_suffix}"
                price = get_price_from_product_page(full_url)
                results.append({
                    "name": title,
                    "url": full_url,
                    "price": price,
                    "store": "Kimostore",
                    "availability": "Check site"
                })
            return results
        except Exception as e:
            print("❌ JSON Parse Error:", e)
            return []
    else:
        print("❌ HTTP Error:", response.status_code)
        return []

# ✅ 11. uptodate
def extract_price_uptodate(html_text):
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        price_text = soup.get_text(strip=True).replace(",", "")
        numbers = re.findall(r'\d+', price_text)
        if numbers:
            return int(numbers[0])  # أول رقم فقط لتفادي التكرار
        return None
    except:
        return None

def scrape_uptodate(query):
    url = f"https://uptodate.store/wp-admin/admin-ajax.php?action=woodmart_ajax_search&number=20&post_type=product&product_cat=0&query={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://uptodate.store/"
    }

    response = requests.get(url, headers=headers)
    results = []

    if response.status_code == 200:
        try:
            data = response.json()
            for item in data.get("suggestions", []):
                name = item.get("value", "").strip()
                link = item.get("permalink", "").strip()
                price_html = item.get("price", "")
                price = extract_price_uptodate(price_html)

                results.append({
                    "name": name,
                    "url": link,
                    "price": price,
                    "store": "Uptodate Store",
                    "availability": "Check site"
                })
        except Exception as e:
            print("❌ Error parsing JSON from Uptodate Store:", e)

    return results

# ✅ 12. abcshop
def scrape_abcshop(query):
    base_url = "https://www.abcshop-eg.com"
    search_url = f"{base_url}/en/website/search?search={query.replace(' ', '+')}"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []

    product_links = soup.select("a.dropdown-item.p-2")

    for item in product_links:
        try:
            name = item.select_one(".h6.fw-bold").text.strip()
            link = base_url + item["href"]
            
            price_el = item.select_one("b span.oe_currency_value")
            if price_el:
                raw_price = price_el.text.strip().replace(",", "")
                price_val = round(float(raw_price)) 
            else:
                price_val = None

            results.append({
                "name": name,
                "price": price_val,
                "url": link,
                "store": "ABC Shop",
                "availability": "Check site"
            })
        except Exception as e:
            print("❌ Error parsing item:", e)

    return results

# ✅ 13. compumarts
def scrape_compumarts(query):
    base_url = "https://www.compumarts.com"
    search_url = f"{base_url}/ar/search?options%5Bprefix%5D=last&q={query.replace(' ', '+')}"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []

    product_cards = soup.select("li.js-pagination-result")

    for card in product_cards:
        try:
            name = card.select_one("p.card__title a").text.strip()

            relative_url = card.select_one("p.card__title a")["href"]
            url = base_url + relative_url

            price_text = card.select_one("span.price__current span.js-value").text.strip()
            price_clean = price_text.replace(",", "").replace("EGP", "").strip()
            price_val = round(float(price_clean))

            results.append({
                "name": name,
                "price": price_val,
                "url": url,
                "store": "Compumarts",
                "availability": "Check site"
            })
        except Exception as e:
            print("❌ Error parsing item:", e)

    return results


# ✅ 14. compunilestore
def scrape_compunilestore(query):
    url = "https://compunilestore.com/wp-admin/admin-ajax.php"
    params = {
        "action": "woodmart_ajax_search",
        "number": 20,
        "post_type": "product",
        "product_cat": 0,
        "query": query
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json"
    }

    response = requests.get(url, params=params, headers=headers)

    results = []

    if response.status_code == 200:
        try:
            data = response.json()
            for item in data.get("suggestions", []):
                name = item.get("value", "").strip()
                url = item.get("permalink", "").strip()

                price_raw = item.get("price", "")
                match = re.search(r"\d[\d,]*", price_raw)
                if match:
                    price = int(match.group(0).replace(",", ""))
                else:
                    price = None

                results.append({
                    "name": name,
                    "price": price,
                    "url": url,
                    "store": "Compunilestore",
                    "availability": "Check site"
                })
        except Exception as e:
            print("❌ JSON parse error:", e)
    else:
        print("❌ HTTP error:", response.status_code)

    return results

# ✅ 15. compuscience
def scrape_compuscience(query):
    base_url = "https://compuscience.com.eg"
    search_url = f"{base_url}/ar/بحث?controller=search&orderby=position&orderway=desc&search_category=all&submit_search=&search_query={query.replace(' ', '+')}"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    results = []
    products = soup.select("article.product-miniature")

    for product in products:
        try:
            name_el = product.select_one("h2.product-title a")
            price_el = product.select_one("span.price")

            if not name_el or not price_el:
                continue  

            name = name_el.text.strip()
            url = name_el["href"]
            full_url = url if url.startswith("http") else base_url + url

            price_text = price_el.text.strip().replace("EGP", "").replace(",", "").replace("\xa0", "").strip()
            price_val = float(price_text)

            results.append({
                "name": name,
                "price": price_val,
                "url": full_url,
                "store": "Compuscience",
                "availability": "Check site"
            })
        except Exception as e:
            print("❌ Error parsing item:", e)

    return results


def scrape_all(query, selected_stores=None, relevance_filter=True):
    """Enhanced scraping function with relevance filtering"""
    
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
        "CompuScience": scrape_compuscience

    }
    
    # Use selected stores or all stores
    scrapers_to_use = {}
    if selected_stores:
        scrapers_to_use = {name: func for name, func in all_scrapers.items() if name in selected_stores}
    else:
        scrapers_to_use = all_scrapers
    
    all_data = []
    
    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_scrapers = len(scrapers_to_use)
    
    for i, (store_name, scraper_func) in enumerate(scrapers_to_use.items()):
        try:
            status_text.text(f"Scraping {store_name}...")
            results = scraper_func(query)
            all_data.extend(results)
            
            # Update progress bar
            progress_bar.progress((i + 1) / total_scrapers)
            
        except Exception as e:
            st.error(f"Error scraping {store_name}: {e}")
    
    # Clean up progress indicators
    progress_bar.empty()
    status_text.empty()
    
    # Create DataFrame and filter
    df = pd.DataFrame(all_data)
    
    if not df.empty:
        # Filter out products with price <= 1 EGP (likely parsing errors)
        df = df[df['price'] > 1]
        
        # Apply relevance filtering if enabled
        if relevance_filter:
            df = filter_relevant_products(df, query)
            st.info(f"🎯 Applied smart filtering - showing {len(df)} relevant products out of {len(all_data)} total results")
        else:
            # Sort by price if no relevance filtering
            df = df.sort_values("price", na_position="last")
        
        # Remove duplicates based on name and price
        df = df.drop_duplicates(subset=['name', 'price'], keep='first')
    
    return df

def create_price_chart(df):
    """Create a price comparison chart"""
    if df.empty:
        return None
    
    # Group by store and calculate average price
    store_avg = df.groupby('store')['price'].agg(['mean', 'count']).reset_index()
    store_avg.columns = ['Store', 'Average Price', 'Product Count']
    
    fig = px.bar(
        store_avg, 
        x='Store', 
        y='Average Price',
        title='Average Prices by Store',
        color='Product Count',
        color_continuous_scale='viridis'
    )
    
    fig.update_layout(
        xaxis_title="Store",
        yaxis_title="Average Price (EGP)",
        showlegend=True
    )
    
    return fig

def create_price_distribution(df):
    """Create price distribution histogram"""
    if df.empty:
        return None
    
    fig = px.histogram(
        df, 
        x='price', 
        nbins=20,
        title='Price Distribution',
        labels={'price': 'Price (EGP)', 'count': 'Number of Products'}
    )
    
    fig.update_layout(
        xaxis_title="Price (EGP)",
        yaxis_title="Number of Products"
    )
    
    return fig

# === Enhanced Streamlit UI ===
st.title("💻 Egypt Tech Price Comparison")
st.markdown("### Find the best tech deals across Egyptian online stores!")

# Sidebar for filters and options
with st.sidebar:
    st.header("🔧 Search Options")
    
    # Smart filtering toggle
    st.subheader("🎯 Smart Filtering")
    relevance_filter = st.checkbox(
        "Enable smart filtering (recommended)", 
        value=True,
        help="Filters out unrelated products and shows only relevant results"
    )
    
    if relevance_filter:
        min_relevance = st.slider(
            "Relevance threshold", 
            min_value=0.1, 
            max_value=1.0, 
            value=0.8, 
            step=0.1,
            help="Higher values = stricter filtering"
        )
    
    # Store selection
    st.subheader("Select Stores")
    all_stores = [
    "Sigma",
    "Elnekhely",
    "ElBadrGroup",
    "BarakaComputer",
    "DeltaComputer",
    "ElnourTech",
    "SolidHardware",
    "AlFrensia",
    "AHWStore",
    "KimoStore",
    "UpToDate",
    "ABCShop",
    "CompuMarts",
    "CompuNileStore",
    "CompuScience"
]

    selected_stores = st.multiselect(
        "Choose stores to search:",
        all_stores,
        default=all_stores
    )
    
    # Price range filter
    st.subheader("Price Range")
    min_price = st.number_input("Minimum Price (EGP)", min_value=0, value=0)
    max_price = st.number_input("Maximum Price (EGP)", min_value=0, value=100000)
    
    # Sort options
    st.subheader("Sort By")
    if relevance_filter:
        sort_option = st.selectbox(
            "Sort results by:",
            ["Relevance + Price", "Price (Low to High)", "Price (High to Low)", "Store Name", "Product Name"]
        )
    else:
        sort_option = st.selectbox(
            "Sort results by:",
            ["Price (Low to High)", "Price (High to Low)", "Store Name", "Product Name"]
        )

# Main search interface
col1, col2 = st.columns([3, 1])

with col1:
    query = st.text_input("🔍 Search for a product (e.g. RTX 4070, iPhone 15, MacBook):", placeholder="Enter product name...")

with col2:
    st.write("")  # Space for alignment
    search_button = st.button("🔍 Search", type="primary")

# Check for alternative query from suggestions
if 'alternative_query' in st.session_state:
    query = st.session_state.alternative_query
    del st.session_state.alternative_query
    st.rerun()

if query and (search_button or st.session_state.get('auto_search', False)):
    with st.spinner("🔄 Fetching data from selected stores..."):
        df = scrape_all(query, selected_stores, relevance_filter)
        
        if df.empty:
            st.warning("❌ No results found. Try different keywords or check more stores.")
            
            # Suggest alternative search terms
            alternatives = smart_search_terms(query)
            if alternatives:
                st.info("💡 Try these alternative searches:")
                for alt in alternatives:
                    if st.button(f"🔍 Search for: {alt}"):
                        st.session_state.alternative_query = alt
                        st.rerun()
        else:
            # Apply price filters
            df_filtered = df[(df['price'] >= min_price) & (df['price'] <= max_price)]
            
            # Apply sorting (but keep relevance-based sorting if enabled)
            if not relevance_filter or sort_option != "Relevance + Price":
                if sort_option == "Price (Low to High)":
                    df_filtered = df_filtered.sort_values('price')
                elif sort_option == "Price (High to Low)":
                    df_filtered = df_filtered.sort_values('price', ascending=False)
                elif sort_option == "Store Name":
                    df_filtered = df_filtered.sort_values('store')
                elif sort_option == "Product Name":
                    df_filtered = df_filtered.sort_values('name')
            
            # Display summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Results", len(df_filtered))
            with col2:
                if not df_filtered.empty:
                    st.metric("Lowest Price", f"{df_filtered['price'].min():,} EGP")
            with col3:
                if not df_filtered.empty:
                    st.metric("Highest Price", f"{df_filtered['price'].max():,} EGP")
            with col4:
                st.metric("Stores Found", df_filtered['store'].nunique())
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["📋 Product List", "📊 Price Analysis", "📈 Charts"])
            
            with tab1:
                st.subheader("🛍️ Available Products")
                
                # Display products in a more attractive format
                for i, row in df_filtered.iterrows():
                    with st.container():
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 0.5])
                        
                        with col1:
                            st.markdown(f"**[{row['name']}]({row['url']})**")
                            st.caption(f"🏪 {row['store']} • 📦 {row['availability']}")
                        
                        with col2:
                            st.markdown(f"### 💰 {row['price']:,} EGP")
                        
                        with col3:
                            st.link_button("🛒 View Product", row['url'])
                        
                        with col4:
                            if relevance_filter and 'relevance_score' in row:
                                st.caption(f"🎯 {row['relevance_score']:.1%}")
                        
                        st.divider()
            
            with tab2:
                st.subheader("📊 Price Analysis")
                
                if not df_filtered.empty:
                    # Price statistics
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
            
            with tab3:
                st.subheader("📈 Visual Analysis")
                
                if not df_filtered.empty and len(df_filtered) > 1:
                    # Price chart
                    price_chart = create_price_chart(df_filtered)
                    if price_chart:
                        st.plotly_chart(price_chart, use_container_width=True)
                    
                    # Price distribution
                    dist_chart = create_price_distribution(df_filtered)
                    if dist_chart:
                        st.plotly_chart(dist_chart, use_container_width=True)
                else:
                    st.info("Need more data points to generate meaningful charts.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🇪🇬 Made for Egyptian tech enthusiasts • Updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """</p>
    <p>💡 Tip: Use specific product names for better results (e.g., "RTX 4070 Super" instead of just "graphics card")</p>
    <p>🎯 Smart filtering automatically removes unrelated products like cables, cases, and accessories</p>
</div>
""", unsafe_allow_html=True)

# Auto-refresh option
if st.sidebar.checkbox("🔄 Auto-refresh every 30 seconds"):
    time.sleep(30)
    st.rerun()