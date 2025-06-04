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
def get_stock_status_elbadrgroup(product_url):
    """
    Fetch the actual stock status from the ElBadrGroup product page
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

def extract_price(price_str):
    """Helper function to extract price from string"""
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None

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
                            "availability": "In Stock"
                        })
            except Exception as e:
                print("❌ Error parsing JSON from ElnourTech:", e)

        return results
    except Exception as e:
        st.error(f"Error scraping ElnourTech: {e}")
        return []
        
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
def get_stock_status_compumarts(product_url):
    """
    Fetch the actual stock status from the CompuMarts product page
    """
    headers = {"User-Agent": "Mozilla/5.0"}
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
            
            # If no sold out indicator found, assume it's in stock
            return "In Stock"
                    
    except Exception as e:
        print(f"Error fetching stock status from CompuMarts: {e}")
        return "Check site"

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
            name_element = card.select_one("p.card__title a")
            if not name_element:
                continue
                
            name = name_element.text.strip()
            relative_url = name_element["href"]
            url = base_url + relative_url

            price_element = card.select_one("span.price__current span.js-value")
            if not price_element:
                continue
                
            price_text = price_element.text.strip()
            price_clean = price_text.replace(",", "").replace("EGP", "").strip()
            price_val = round(float(price_clean))

            # Check stock status directly from the search results page first
            sold_out_label = card.select_one("span.product-label--sold-out")
            if sold_out_label:
                stock_status = "Out of Stock"
            else:
                # If not found in search results, check the product page
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