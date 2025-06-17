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
from functools import wraps

def get_stock_status_sigma(product_url):
    """
    Fetch the actual stock status from the Sigma product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the cart icon element and check the text after it
            cart_icons = soup.select("i.fa.fa-shopping-cart")
            
            for cart_icon in cart_icons:
                # Get the parent element or next sibling to find the text
                parent = cart_icon.parent
                if parent:
                    text = parent.get_text().strip().lower()
                    if "add to cart" in text:
                        return "In Stock"
                    elif "out of stock" in text:
                        return "Out of Stock"
                
                # Also check next sibling text
                next_element = cart_icon.next_sibling
                if next_element and hasattr(next_element, 'strip'):
                    text = next_element.strip().lower()
                    if "add to cart" in text:
                        return "In Stock"
                    elif "out of stock" in text:
                        return "Out of Stock"
            
            # Alternative approach: look for button text directly
            buttons = soup.select("button, a[class*='cart'], [class*='add-to-cart']")
            for button in buttons:
                text = button.get_text().strip().lower()
                if "add to cart" in text:
                    return "In Stock"
                elif "out of stock" in text:
                    return "Out of Stock"
            
            # Additional fallback: check for common stock indicators
            stock_texts = soup.find_all(text=re.compile(r"(out of stock|add to cart)", re.IGNORECASE))
            for text in stock_texts:
                text_lower = text.strip().lower()
                if "add to cart" in text_lower:
                    return "In Stock"
                elif "out of stock" in text_lower:
                    return "Out of Stock"
                    
        return "Check site"
    except Exception as e:
        print(f"Error fetching stock status from Sigma: {e}")
        return "Check site"

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
                    product_url = "https://www.sigma-computer.com/" + a['href']
                    
                    # Get actual stock status from product page
                    stock_status = get_stock_status_sigma(product_url)
                    
                    results.append({
                        "name": a.text.strip(),
                        "url": product_url,
                        "price": price,
                        "store": "Sigma",
                        "availability": stock_status
                    })
        return results
    except Exception as e:
        print(f"Error scraping Sigma: {e}")
        return []

def extract_price(price_str):
    """Helper function to extract price from string"""
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None




# ✅ 2. Elnekhely Technology (JSON)
def get_stock_status_elnekhely(product_url):
    """
    Fetch the actual stock status from the product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the stock status element
            stock_element = soup.select_one("li.product-stock")
            if stock_element:
                if "in-stock" in stock_element.get("class", []):
                    return "In Stock"
                elif "out-of-stock" in stock_element.get("class", []):
                    return "Out of Stock"
                else:
                    # Fallback: check the text content
                    stock_text = stock_element.get_text().lower()
                    if "in stock" in stock_text:
                        return "In Stock"
                    elif "out of stock" in stock_text:
                        return "Out of Stock"
            
            # Additional fallback: look for other common stock indicators
            stock_indicators = soup.select("span:contains('In Stock'), span:contains('Out of Stock')")
            for indicator in stock_indicators:
                text = indicator.get_text().lower()
                if "in stock" in text:
                    return "In Stock"
                elif "out of stock" in text:
                    return "Out of Stock"
                    
        return "Check site"
    except Exception as e:
        print(f"Error fetching stock status: {e}")
        return "Check site"

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
                    product_url = item["href"]
                    
                    if price and price > 1:  # Filter out 1 EGP prices
                        # Get actual stock status from product page
                        stock_status = get_stock_status_elnekhely(product_url)
                        
                        results.append({
                            "name": item["name"],
                            "url": product_url,
                            "price": price,
                            "store": "Elnekhely",
                            "availability": stock_status
                        })
        return results
    except Exception as e:
        st.error(f"Error scraping Elnekhely: {e}")
        return []

def extract_price(price_str):
    """Helper function to extract price from string"""
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None

#✅ 3. elbadrgroupeg
WORKING_HEADERS = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'origin': 'https://elbadrgroupeg.store',
    'referer': 'https://elbadrgroupeg.store/',
    'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-arch': '"x86"',
    'sec-ch-ua-bitness': '"64"',
    'sec-ch-ua-full-version': '"137.0.7151.104"',
    'sec-ch-ua-full-version-list': '"Google Chrome";v="137.0.7151.104", "Chromium";v="137.0.7151.104", "Not/A)Brand";v="24.0.0.0"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"Windows"',
    'sec-ch-ua-platform-version': '"10.0.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest'
}

WORKING_COOKIES = {
    'language': 'en-gb',
    'currency': 'EGP',
    'OCSESSID': '3bbac5c84ef6b30e244ba01faf',
    'cf_clearance': 'gNogXtUzKZijvZenW9dszYepfP2htaetRG30hcf6q8A-1750122467-1.2.1.1-NqJmn4x8w1e1GrZ.q0fSivqtra1czLpPHRS2hIw6cyTWkO0Mt7BNmPQdgYT05znLkMWMTzXuSlCUVSB1RYaMX_IG9yDaeyvWAKbRGqPf7FFG4EFglGLY9m0JKOB3.V64NsmV0w3BVKYlLG6YxgkuD6NwC9hQzDcwysqRa2cSjBuzf.UzyyngCq_LGAn_kJL.s9BOJf0MLZ_YzwN6GawdkW5CraJpE0QBHSzmLI2gvxYTtU29J1rpUM7AxQkTae3BJngmSMYqbKp06lQKdN.qncbeC0wb4M50wUrUoSRwQE1_v8uM3IVWarEKomuc9qejaqW_QNcmdbWU6tLjYjuueRqLNivFAyauy3i36wrfF6hEUV_mOgasnIL9J0PchHXA',
    'jrv': '6599',
    '_fbp': 'fb.1.1750122471066.824500933275114599'
}


def get_stock_status_elbadrgroup(product_url):
    """
    Fetch the actual stock status from the ElBadrGroup product page
    """
    try:
        response = requests.get(product_url, headers=WORKING_HEADERS, cookies=WORKING_COOKIES, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the stock status element
            stock_element = soup.select_one("li.product-stock")
            if stock_element:
                if "in-stock" in stock_element.get("class", []):
                    return "In Stock"
                elif "out-of-stock" in stock_element.get("class", []):
                    return "Out of Stock"
                else:
                    # Fallback: check the text content
                    stock_text = stock_element.get_text().lower().strip()
                    if "in stock" in stock_text:
                        return "In Stock"
                    elif "out of stock" in stock_text:
                        return "Out of Stock"
            
            # Additional fallback: look for other common stock indicators
            stock_indicators = soup.select("span:contains('In Stock'), span:contains('Out Of Stock')")
            for indicator in stock_indicators:
                text = indicator.get_text().lower().strip()
                if "in stock" in text:
                    return "In Stock"
                elif "out of stock" in text:
                    return "Out of Stock"
                    
        return "Check site"
    except Exception as e:
        print(f"Error fetching stock status from ElBadrGroup: {e}")
        return "Check site"


def scrape_elbadrgroupe(query):
    url = f"https://elbadrgroupeg.store/index.php?route=journal3/search&search={query}"
    
    try:
        r = requests.get(url, headers=WORKING_HEADERS, cookies=WORKING_COOKIES, timeout=10)
        results = []
        if r.status_code == 200:
            try:
                data = r.json()
                if "response" in data:
                    for item in data["response"]:
                        if "name" in item and (item.get("special") or item.get("price")):
                            price_str = item.get("special") or item.get("price")
                            price = extract_price(price_str)
                            product_url = item.get("href", "#")
                            
                            if price and price > 1:  # Filter out 1 EGP prices
                                # Get actual stock status from product page
                                stock_status = get_stock_status_elbadrgroup(product_url)
                                
                                results.append({
                                    "name": item["name"],
                                    "url": product_url,
                                    "price": price,
                                    "store": "ElBadrGroup",
                                    "availability": stock_status
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
                                    "availability": "In Stock"
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
                                "availability": "In Stock"
                            })
            except Exception as e:
                print("❌ Error parsing JSON from DeltaComputer:", e)

        return results
    except Exception as e:
        st.error(f"Error scraping DeltaComputer: {e}")
        return []

#✅ 6. elnour-tech (FIXED)
def extract_price_european_format(price_text):
    """
    Extract price from European format text (e.g., "1.234,56 €" or "1,234.56")
    """
    if not price_text:
        return None
    
    # Remove currency symbols and extra whitespace
    price_clean = re.sub(r'[^\d,.\s]', '', price_text.strip())
    
    # Handle different formats
    if ',' in price_clean and '.' in price_clean:
        # Format like "1,234.56" or "1.234,56"
        if price_clean.rfind(',') > price_clean.rfind('.'):
            # European format: "1.234,56"
            price_clean = price_clean.replace('.', '').replace(',', '.')
        else:
            # US format: "1,234.56"
            price_clean = price_clean.replace(',', '')
    elif ',' in price_clean:
        # Could be thousands separator or decimal
        parts = price_clean.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Decimal separator: "1234,56"
            price_clean = price_clean.replace(',', '.')
        else:
            # Thousands separator: "1,234"
            price_clean = price_clean.replace(',', '')
    
    try:
        return round(float(price_clean))
    except ValueError:
        return None

def get_stock_status_elnourtech(product_url):
    """
    Fetch the actual stock status from ElnourTech product page
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Check for out of stock indicators
            out_of_stock_selectors = [
                ".out-of-stock",
                ".stock.out-of-stock",
                "*:contains('Out of stock')",
                "*:contains('نفدت الكمية')",
                "button:disabled",
                ".single_add_to_cart_button:disabled"
            ]
            
            for selector in out_of_stock_selectors:
                element = soup.select_one(selector)
                if element:
                    return "Out of Stock"
            
            # Check if add to cart button is available
            add_to_cart = soup.select_one(".single_add_to_cart_button, .add_to_cart_button")
            if add_to_cart and "disabled" in add_to_cart.get("class", []):
                return "Out of Stock"
            
            return "In Stock"
                    
    except Exception as e:
        print(f"Error fetching stock status from ElnourTech: {e}")
        return "Check site"

def scrape_elnourtech(query):
    """
    Scrape ElnourTech using their AJAX search endpoint
    """
    def extract_price_from_html(html_text):
        if not html_text:
            return None
        
        soup = BeautifulSoup(html_text, "html.parser")
        
        # Try different price selectors
        price_selectors = [
            "ins .amount",
            "ins",
            ".amount",
            ".price .woocommerce-Price-amount",
            ".woocommerce-Price-amount",
            "span[class*='amount']"
        ]
        
        price_element = None
        for selector in price_selectors:
            price_element = soup.select_one(selector)
            if price_element:
                break
        
        if not price_element:
            # Fallback: try to find any element with price-like text
            price_element = soup
        
        if price_element:
            return extract_price_european_format(price_element.get_text())
        return None

    # Primary AJAX endpoint
    primary_url = f"https://elnour-tech.com/wp-admin/admin-ajax.php"
    
    # Fallback search URLs to try
    fallback_urls = [
        f"https://elnour-tech.com/?s={query.replace(' ', '+')}&post_type=product",
        f"https://elnour-tech.com/shop/?s={query.replace(' ', '+')}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
        "Referer": "https://elnour-tech.com/",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    results = []
    
    # Try AJAX search first
    try:
        ajax_params = {
            "action": "woodmart_ajax_search",
            "number": 20,
            "post_type": "product",
            "query": query
        }
        
        print(f"Trying AJAX search for: {query}")
        response = requests.get(primary_url, params=ajax_params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            try:
                data = response.json()
                suggestions = data.get("suggestions", [])
                
                print(f"Found {len(suggestions)} suggestions from AJAX")
                
                for item in suggestions:
                    try:
                        name = item.get("value", "").strip()
                        link = item.get("permalink", "")
                        price_html = item.get("price", "")
                        
                        if not name or not link:
                            continue
                        
                        # Extract price
                        price = extract_price_from_html(price_html) if price_html else None
                        
                        # Skip items without valid price
                        if not price or price <= 0:
                            continue
                        
                        # Get stock status
                        stock_status = get_stock_status_elnourtech(link)
                        
                        results.append({
                            "name": name,
                            "url": link,
                            "price": price,
                            "store": "ElnourTech",
                            "availability": stock_status
                        })
                        
                        print(f"✅ Added: {name} - {price} EGP - {stock_status}")
                        
                    except Exception as e:
                        print(f"❌ Error parsing ElnourTech item: {e}")
                        continue
                
                if results:
                    return results
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                print(f"Response content: {response.text[:200]}...")
            except Exception as e:
                print(f"❌ Error parsing AJAX response: {e}")
    
    except requests.RequestException as e:
        print(f"❌ AJAX request failed: {e}")
    
    # Fallback to regular search if AJAX fails
    print("AJAX search failed, trying fallback methods...")
    
    for fallback_url in fallback_urls:
        try:
            print(f"Trying fallback URL: {fallback_url}")
            response = requests.get(fallback_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try different product selectors
                product_selectors = [
                    ".product",
                    ".woocommerce-product",
                    ".product-item",
                    ".shop-item",
                    "li[class*='product']"
                ]
                
                products = []
                for selector in product_selectors:
                    products = soup.select(selector)
                    if products:
                        print(f"Found {len(products)} products with selector: {selector}")
                        break
                
                for product in products[:10]:  # Limit to first 10 products
                    try:
                        # Get product name and link
                        link_element = product.select_one("a[href*='/product/'], .woocommerce-loop-product__link, h2 a")
                        if not link_element:
                            continue
                        
                        name = link_element.get("title") or link_element.get_text().strip()
                        link = link_element.get("href")
                        
                        if not name or not link:
                            continue
                        
                        # Make sure link is absolute
                        if link.startswith('/'):
                            link = "https://elnour-tech.com" + link
                        
                        # Get price
                        price_element = product.select_one(".price .amount, .woocommerce-Price-amount, .price")
                        if not price_element:
                            continue
                        
                        price = extract_price_european_format(price_element.get_text())
                        if not price or price <= 0:
                            continue
                        
                        # Get stock status
                        stock_status = get_stock_status_elnourtech(link)
                        
                        results.append({
                            "name": name,
                            "url": link,
                            "price": price,
                            "store": "ElnourTech",
                            "availability": stock_status
                        })
                        
                        print(f"✅ Added from fallback: {name} - {price} EGP")
                        
                    except Exception as e:
                        print(f"❌ Error parsing fallback product: {e}")
                        continue
                
                if results:
                    return results
                    
        except requests.RequestException as e:
            print(f"❌ Fallback request failed for {fallback_url}: {e}")
            continue
    
    print("❌ All search methods failed")
    return results

        
#✅ 7. solidhardware
def scrape_solidhardware(query):
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
                        "availability": "In Stock"
                    })
        except Exception as e:
            print("❌ Error parsing JSON from SolidHardware:", e)

    return results

#✅ 8. alfrensia
def get_stock_status_alfrensia(product_url):
    """
    Fetch the actual stock status from the product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the stock status element
            stock_element = soup.select_one("p.stock")
            if stock_element:
                # Check CSS classes first
                if "in-stock" in stock_element.get("class", []):
                    return "In Stock"
                elif "out-of-stock" in stock_element.get("class", []):
                    return "Out of Stock"
                
                # Check text content for various stock messages
                stock_text = stock_element.get_text().strip().lower()
                
                # Check for in-stock indicators (English and Arabic)
                in_stock_indicators = [
                    "in stock",
                    "متوفر في المخزون",
                    "left in stock"  # This covers "Only 2 left in stock", "Only 1 left in stock", etc.
                ]
                
                for indicator in in_stock_indicators:
                    if indicator in stock_text:
                        return "In Stock"
                
                # If stock element exists but has no text and no in-stock class, it's likely out of stock
                if not stock_text or stock_text == "":
                    return "Out of Stock"
            
            # Additional fallback: look for other common stock indicators across the page
            # Check for any element containing stock information
            all_stock_elements = soup.find_all(text=re.compile(r'(in stock|متوفر في المخزون|left in stock)', re.IGNORECASE))
            if all_stock_elements:
                return "In Stock"
            
            # Check for out of stock indicators
            out_of_stock_elements = soup.find_all(text=re.compile(r'(out of stock|غير متوفر|نفد المخزون)', re.IGNORECASE))
            if out_of_stock_elements:
                return "Out of Stock"
                    
        return "Check site"
    except Exception as e:
        print(f"Error fetching stock status for Alfrensia: {e}")
        return "Check site"

def extract_price_alfrensia(html_price):
    """Extract price from HTML content"""
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

    try:
        response = requests.get(url, headers=headers, timeout=10)
        results = []

        if response.status_code == 200:
            data = response.json()
            suggestions = data.get("suggestions", [])
            
            for item in suggestions:
                title = item.get("value", "").strip()
                product_url = item.get("url", "").strip()
                price_html = item.get("price", "")
                price = extract_price_alfrensia(price_html)

                if title and product_url and price and price > 1:
                    # Get actual stock status from product page
                    stock_status = get_stock_status_alfrensia(product_url)
                    
                    results.append({
                        "name": title,
                        "url": product_url,
                        "price": price,
                        "store": "Alfrensia",
                        "availability": stock_status
                    })
                    
        return results
    except Exception as e:
        print(f"Error scraping Alfrensia: {e}")
        return []
# ✅ 9. ahw.store
def get_stock_status_ahwstore(product_url):
    """
    Fetch the actual stock status from the AHW Store product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the stock status element
            stock_element = soup.select_one("li.product-stock")
            if stock_element:
                # Check CSS classes first
                classes = stock_element.get("class", [])
                stock_span = stock_element.select_one("span")
                
                if stock_span:
                    stock_text = stock_span.get_text().strip()
                    
                    # Check for in-stock conditions
                    if "in-stock" in classes or stock_text.lower() in ["builds only", "in stock"]:
                        return "In Stock"
                    
                    # Check for out-of-stock conditions
                    elif "out-of-stock" in classes or stock_text.lower() == "out of stock":
                        return "Out of Stock"
                
                # Fallback: check the entire element text
                full_text = stock_element.get_text().lower()
                if "builds only" in full_text or "in stock" in full_text:
                    return "In Stock"
                elif "out of stock" in full_text:
                    return "Out of Stock"
            
            # Additional fallback: look for other stock indicators
            stock_indicators = soup.select("span:contains('In Stock'), span:contains('Out of Stock'), span:contains('Builds Only')")
            for indicator in stock_indicators:
                text = indicator.get_text().strip().lower()
                if text in ["in stock", "builds only"]:
                    return "In Stock"
                elif text == "out of stock":
                    return "Out of Stock"
                    
        return "Check site"
    except Exception as e:
        print(f"Error fetching AHW Store stock status: {e}")
        return "Check site"

def scrape_ahwstore(query):
    url = f"https://ahw.store/index.php?route=journal3/search&search={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        results = []

        if response.status_code == 200:
            try:
                data = response.json()
                for item in data.get("response", []):
                    name = item.get("name")
                    link = item.get("href")
                    price_str = item.get("special") or item.get("price")
                    price = extract_price(price_str)

                    if name and link and price and price > 1:  # Filter out 1 EGP prices
                        # Get actual stock status from product page
                        stock_status = get_stock_status_ahwstore(link)
                        
                        results.append({
                            "name": name.strip(),
                            "url": link.strip(),
                            "price": price,
                            "store": "AHW Store",
                            "availability": stock_status
                        })
            except Exception as e:
                print("❌ Error parsing JSON from AHW Store:", e)

        return results
    except Exception as e:
        st.error(f"Error scraping AHW Store: {e}")
        return []

def extract_price(price_str):
    """Helper function to extract price from string"""
    if not price_str:
        return None
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None

# ✅ 10. kimostore
def get_stock_status_kimostore(product_url):
    """
    Fetch the actual stock status from the KimoStore product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the stock status element
            stock_element = soup.select_one("span.product-form__inventory.inventory")
            if stock_element:
                stock_text = stock_element.get_text().strip().lower()
                
                if "in stock" in stock_text:
                    return "In Stock"
                elif "sold out" in stock_text:
                    return "Out of Stock"
                else:
                    # Additional check for other possible text variations
                    if "available" in stock_text:
                        return "In Stock"
                    elif "unavailable" in stock_text or "out of stock" in stock_text:
                        return "Out of Stock"
            
            # Alternative selectors as fallback
            alternative_selectors = [
                ".inventory--high",
                ".inventory--low", 
                ".inventory--medium",
                "[data-inventory]",
                ".stock-status"
            ]
            
            for selector in alternative_selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text().strip().lower()
                    if "in stock" in text or "available" in text:
                        return "In Stock"
                    elif "sold out" in text or "out of stock" in text or "unavailable" in text:
                        return "Out of Stock"
                        
        return "Check site"
    except Exception as e:
        print(f"Error fetching stock status from KimoStore: {e}")
        return "Check site"

def get_price_from_product_page(url):
    """Enhanced price extraction that also gets stock status"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Price selectors
            selectors = [
                '.price-item--regular',
                '.price__regular .price-item',
                'span.price',
                '.product__price span',
                '.product__price .money',
                '[data-product-price]',
            ]
            
            price = None
            for selector in selectors:
                tag = soup.select_one(selector)
                if tag:
                    text = tag.get_text(strip=True)
                    match = re.search(r'[\d.,]+', text)
                    if match:
                        raw = match.group().replace(",", "")
                        try:
                            price = int(float(raw))
                            break
                        except:
                            price = int(re.sub(r'\D', '', raw))
                            break
            
            return price
    except Exception as e:
        print("❌ Error extracting price from KimoStore:", e)
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
                
                # Get price from product page
                price = get_price_from_product_page(full_url)
                
                # Get stock status from product page
                stock_status = get_stock_status_kimostore(full_url)
                
                results.append({
                    "name": title,
                    "url": full_url,
                    "price": price,
                    "store": "Kimostore",
                    "availability": stock_status
                })
            return results
        except Exception as e:
            print("❌ JSON Parse Error from KimoStore:", e)
            return []
    else:
        print("❌ HTTP Error from KimoStore:", response.status_code)
        return []
# ✅ 11. uptodate
def get_stock_status_uptodate(product_url):
    """
    Fetch the actual stock status from the product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the specific out of stock element
            out_of_stock_element = soup.select_one("p.stock.out-of-stock")
            if out_of_stock_element and "out of stock" in out_of_stock_element.get_text().lower():
                return "Out of Stock"
            
            # Additional check for other possible out of stock indicators
            stock_elements = soup.select("p.stock, .stock-status, .availability")
            for element in stock_elements:
                text = element.get_text().lower()
                if "out of stock" in text:
                    return "Out of Stock"
            
            # If no "Out of Stock" found, assume it's in stock
            return "In Stock"
            
    except Exception as e:
        print(f"Error fetching stock status for {product_url}: {e}")
        return "In Stock"  # Default to In Stock if error occurs

def extract_price_uptodate(html_text):
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        price_text = soup.get_text(strip=True).replace(",", "")
        numbers = re.findall(r'\d+', price_text)
        if numbers:
            return int(numbers[0])  # First number only to avoid duplication
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

                if name and link and price and price > 1:
                    # Get actual stock status from product page
                    stock_status = get_stock_status_uptodate(link)
                    
                    results.append({
                        "name": name,
                        "url": link, 
                        "price": price,
                        "store": "Uptodate Store",
                        "availability": stock_status
                    })
        except Exception as e:
            print("❌ Error parsing JSON from Uptodate Store:", e)

    return results
# ✅ 12. abcshop
def get_stock_status_abcshop(product_url):
    """
    Fetch the actual stock status from the product page
    Returns "Out of Stock" if "Get notified when back in stock" is found, otherwise "In Stock"
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the "Get notified when back in stock" element
            notification_element = soup.select_one("#product_stock_notification_message")
            if notification_element:
                # Check if the text contains the out of stock message
                text = notification_element.get_text().strip().lower()
                if "get notified when back in stock" in text:
                    return "Out of Stock"
            
            # Alternative: look for the text anywhere in the page
            if "get notified when back in stock" in soup.get_text().lower():
                return "Out of Stock"
            
            # If we don't find the notification message, assume it's in stock
            return "In Stock"
            
    except Exception as e:
        print(f"Error fetching stock status from ABCShop: {e}")
        return "Check site"
    
    return "Check site"

def scrape_abcshop(query):
    base_url = "https://www.abcshop-eg.com"
    search_url = f"{base_url}/en/website/search?search={query.replace(' ', '+')}"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(search_url, headers=headers, timeout=10)
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

                if name and price_val and price_val > 1:
                    # Get actual stock status from product page
                    stock_status = get_stock_status_abcshop(link)
                    
                    results.append({
                        "name": name,
                        "price": price_val,
                        "url": link,
                        "store": "ABC Shop",
                        "availability": stock_status
                    })
                    
            except Exception as e:
                print(f"❌ Error parsing ABCShop item: {e}")

        return results
        
    except Exception as e:
        print(f"❌ Error scraping ABCShop: {e}")
        return []
        
# ✅ 13. compumarts
import requests
from bs4 import BeautifulSoup

def get_stock_status_compumarts(product_url):
    """
    Fetch the actual stock status from the CompuMarts product page
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the sold out label
            sold_out_element = soup.select_one("span.product-label--sold-out")
            if sold_out_element:
                return "Out of Stock"
            
            # Additional check for sold out text
            sold_out_text = soup.select("span:contains('Sold out'), span:contains('sold out')")
            if sold_out_text:
                return "Out of Stock"
            
            # Check for "Unavailable" text which is common on CompuMarts
            unavailable_elements = soup.select("*:contains('Unavailable')")
            if unavailable_elements:
                return "Out of Stock"
            
            # Check for stock status in button text
            add_to_cart_button = soup.select_one("button[type='submit'], .btn-product-form")
            if add_to_cart_button and "sold out" in add_to_cart_button.get_text().lower():
                return "Out of Stock"
            
            # If no sold out indicator found, assume it's in stock
            return "In Stock"
                    
    except Exception as e:
        print(f"Error fetching stock status from CompuMarts: {e}")
        return "Check site"

def scrape_compumarts(query):
    base_url = "https://www.compumarts.com"
    
    # Try different possible search URL formats
    possible_urls = [
        f"{base_url}/search?q={query.replace(' ', '+')}",
        f"{base_url}/search?query={query.replace(' ', '+')}",
        f"{base_url}/collections/all?filter.v.availability=1&sort_by=best-selling&q={query.replace(' ', '+')}",
        f"{base_url}/ar/search?options%5Bprefix%5D=last&q={query.replace(' ', '+')}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Try different URL formats until one works
    soup = None
    working_url = None
    
    for url in possible_urls:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                working_url = url
                break
                
        except requests.RequestException:
            continue
    
    if not soup:
        print("❌ All URL formats failed")
        return []

    # Try different selectors for product cards
    selectors_to_try = [
        "li.js-pagination-result",
        ".product-item",
        ".card",
        ".product-card",
        "article.product",
        ".grid-item",
        "[data-product-id]"
    ]
    
    product_cards = []
    for selector in selectors_to_try:
        product_cards = soup.select(selector)
        if product_cards:
            break
    
    if not product_cards:
        return []

    results = []
    for card in product_cards:
        try:
            # Try different selectors for product name
            name_selectors = [
                "p.card__title a",
                ".product-title a",
                ".card-title a",
                "h3 a",
                "h2 a",
                ".product-name a",
                "a[href*='/products/']"
            ]
            
            name_element = None
            for selector in name_selectors:
                name_element = card.select_one(selector)
                if name_element:
                    break
            
            if not name_element:
                continue
                
            name = name_element.text.strip()
            relative_url = name_element.get("href")
            if not relative_url:
                continue
                
            url = base_url + relative_url

            # Try different selectors for price
            price_selectors = [
                "span.price__current span.js-value",
                ".price .current",
                ".price-current",
                ".price",
                "[class*='price']",
                ".money"
            ]
            
            price_element = None
            for selector in price_selectors:
                price_element = card.select_one(selector)
                if price_element:
                    break
            
            if not price_element:
                continue
                
            price_text = price_element.text.strip()
            price_clean = price_text.replace(",", "").replace("EGP", "").strip()
            
            try:
                price_val = round(float(price_clean))
            except ValueError:
                continue

            # Check stock status directly from the search results page first
            sold_out_selectors = [
                "span.product-label--sold-out",
                ".sold-out",
                ".out-of-stock",
                "*:contains('Sold out')",
                "*:contains('Unavailable')"
            ]
            
            stock_status = "In Stock"  # Default assumption
            for selector in sold_out_selectors:
                sold_out_label = card.select_one(selector)
                if sold_out_label:
                    stock_status = "Out of Stock"
                    break
            
            # If not found as sold out in search results, check the product page
            if stock_status == "In Stock":
                stock_status = get_stock_status_compumarts(url)

            results.append({
                "name": name,
                "price": price_val,
                "url": url,
                "store": "Compumarts",
                "availability": stock_status
            })
            
        except Exception as e:
            print(f"❌ Error parsing CompuMarts item: {e}")
            continue

    return results

# ✅ 14. compunilestore
def get_stock_status_compunilestore(product_url):
    """
    Fetch the actual stock status from the product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the specific out-of-stock element
            out_of_stock_element = soup.select_one("p.stock.out-of-stock")
            if out_of_stock_element:
                # Check if it contains "Out of stock" text
                stock_text = out_of_stock_element.get_text().lower()
                if "out of stock" in stock_text:
                    return "Out of Stock"
            
            # Additional check for other out-of-stock indicators
            out_of_stock_indicators = soup.select("*:contains('Out of stock'), *:contains('out of stock')")
            for indicator in out_of_stock_indicators:
                if "out-of-stock" in indicator.get("class", []):
                    return "Out of Stock"
            
            # If no out-of-stock indicator found, assume in stock
            return "In Stock"
            
    except Exception as e:
        print(f"Error fetching stock status for {product_url}: {e}")
        return "Check site"

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
                product_url = item.get("permalink", "").strip()

                price_raw = item.get("price", "")
                match = re.search(r"\d[\d,]*", price_raw)
                if match:
                    price = int(match.group(0).replace(",", ""))
                else:
                    price = None

                if name and product_url and price:
                    # Get actual stock status from product page
                    stock_status = get_stock_status_compunilestore(product_url)
                    
                    results.append({
                        "name": name,
                        "price": price,
                        "url": product_url,
                        "store": "Compunilestore",
                        "availability": stock_status
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
                "availability": "In Stock"
            })
        except Exception as e:
            print("❌ Error parsing item:", e)

    return results

# ✅ 16. MaximumHardware
def get_stock_status_maximumhardware(product_url):
    """
    Fetch the actual stock status from the MaximumHardware product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the stock status element
            stock_element = soup.select_one("li.product-stock")
            if stock_element:
                # Check CSS classes first
                if "in-stock" in stock_element.get("class", []):
                    return "In Stock"
                elif "out-of-stock" in stock_element.get("class", []):
                    return "Out of Stock"
                else:
                    # Fallback: check the span text content
                    stock_span = stock_element.select_one("span")
                    if stock_span:
                        stock_text = stock_span.get_text().strip().lower()
                        if "in stock" in stock_text:
                            return "In Stock"
                        elif "out of stock" in stock_text:
                            return "Out of Stock"
            
            # Additional fallback: look for other common stock indicators
            stock_indicators = soup.select("span:contains('In Stock'), span:contains('Out Of Stock')")
            for indicator in stock_indicators:
                text = indicator.get_text().lower()
                if "in stock" in text:
                    return "In Stock"
                elif "out of stock" in text:
                    return "Out of Stock"
                    
        return "Check site"
    except Exception as e:
        print(f"Error fetching stock status from MaximumHardware: {e}")
        return "Check site"

def scrape_maximumhardware(query):
    url = f"https://maximumhardware.store/index.php?route=journal3/search&search={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        results = []
        for item in data.get("response", []):
            title = item.get("name")
            link = item.get("href")
            price_text = item.get("price", "").replace(",", "").replace("EGP", "").strip()
            
            # Extract price
            try:
                price = float(price_text)
            except ValueError:
                # Try to extract numbers from the price text
                numbers = re.findall(r'\d+', price_text.replace(",", ""))
                price = int("".join(numbers)) if numbers else None

            if title and link and price and price > 1:
                # Get actual stock status from product page
                stock_status = get_stock_status_maximumhardware(link)
                
                results.append({
                    "name": title.strip(),
                    "price": price,
                    "url": link,
                    "store": "MaximumHardware",
                    "availability": stock_status
                })
        return results

    except Exception as e:
        print(f"❌ Error fetching from MaximumHardware: {e}")
        return []
# ✅ 17. quantumtechnology
def get_stock_status_quantum(product_url):
    """
    Fetch the actual stock status from the QuantumTechnology product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the out of stock element
            out_of_stock_element = soup.select_one("p.stock.out-of-stock")
            if out_of_stock_element:
                stock_text = out_of_stock_element.get_text().lower().strip()
                if "out of stock" in stock_text:
                    return "Out of Stock"
            
            # If no out-of-stock element found, assume it's in stock
            return "In Stock"
            
    except Exception as e:
        print(f"Error fetching stock status from QuantumTechnology: {e}")
        return "Check site"

def extract_price_from_html(price_html):
    try:
        soup = BeautifulSoup(price_html, "html.parser")
        text = soup.get_text(strip=True)
        match = re.search(r'[\d\.,]+', text)
        if match:
            # تحويل السعر لصيغة float
            price_str = match.group(0).replace('.', '').replace(',', '.')
            return float(price_str)
    except:
        return None

def scrape_quantumtechnology(query):
    try:
        url = f"https://quantumtechnologyeg.com/wp-admin/admin-ajax.php"
        params = {
            "action": "woodmart_ajax_search",
            "number": "20",
            "post_type": "product",
            "product_cat": "0",
            "query": query
        }
        headers = {
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest"
        }

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        results = []
        for product in data.get("suggestions", []):
            title = product.get("value")
            product_url = product.get("permalink")
            raw_price = product.get("price")
            price = extract_price_from_html(raw_price)

            if price is not None and price > 1:  # Filter out invalid prices
                # Get actual stock status from product page
                stock_status = get_stock_status_quantum(product_url)
                
                results.append({
                    "name": title,
                    "price": price,
                    "url": product_url,
                    "store": "QuantumTechnology",
                    "availability": stock_status
                })

        return results

    except Exception as e:
        print("❌ Error scraping QuantumTechnology:", e)
        return []

# ✅ 18. HighEndStore
def get_stock_status_highendstore(product_url):
    """
    Fetch the actual stock status from the HighEndStore product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(product_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the stock status element
            stock_element = soup.select_one("li.product-stock")
            if stock_element:
                if "in-stock" in stock_element.get("class", []):
                    return "In Stock"
                elif "out-of-stock" in stock_element.get("class", []):
                    return "Out of Stock"
                else:
                    # Fallback: check the text content
                    stock_text = stock_element.get_text().lower()
                    if "in stock" in stock_text:
                        return "In Stock"
                    elif "out of stock" in stock_text:
                        return "Out of Stock"
            
            # Additional fallback: look for other common stock indicators
            stock_spans = soup.select("span")
            for span in stock_spans:
                text = span.get_text().lower().strip()
                if text == "in stock":
                    return "In Stock"
                elif text == "out of stock":
                    return "Out of Stock"
                    
        return "Check site"
    except Exception as e:
        print(f"Error fetching stock status from HighEndStore: {e}")
        return "Check site"

def scrape_highendstore(search_term):
    try:
        url = f"https://highendstore.net/index.php?route=journal3/search&search={search_term}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest"
        }

        response = requests.get(url, headers=headers)
        data = response.json()

        products = []
        for item in data.get("response", []):
            if "name" in item and "price" in item and "href" in item:
                price_str = item.get("special") or item.get("price")
                price_num = float(price_str.replace(",", "").replace("EGP", "").strip())
                product_url = item["href"]

                # Get actual stock status from product page
                stock_status = get_stock_status_highendstore(product_url)

                product = {
                    "name": item["name"].strip(),
                    "price": price_num,
                    "url": product_url,
                    "store": "HighEndStore",
                    "availability": stock_status
                }
                products.append(product)

        return products

    except Exception as e:
        print(f"❌ Error scraping HighEndStore: {e}")
        return []

# ✅ 19. Newvision
def scrape_newvision(query="rtx 4070"):
    url = "https://newvision.com.eg/wp-content/plugins/ajax-search-for-woocommerce-premium/includes/Engines/TNTSearchMySQL/Endpoints/search.php"
    params = {"s": query}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/plain, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        raw_json = json.loads(response.text)
        suggestions = raw_json.get("suggestions", [])

        results = []
        for item in suggestions:
            title = item.get("value", "").strip()
            url = item.get("url", "")

            # Extract number from price HTML
            price_html = item.get("price", "")
            match = re.search(r">([\d.,]+)\s*&nbsp;", price_html)
            price = float(match.group(1).replace(".", "").replace(",", "")) if match else None

            results.append({
                "title": title,
                "price": price,
                "url": url,
                "source": "NewVision"
            })

        return results

    except Exception as e:
        print(f"❌ Error scraping NewVision: {e}")
        return []
