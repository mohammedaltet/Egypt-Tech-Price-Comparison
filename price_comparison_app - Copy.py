import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def extract_price(price_str):
    numbers = re.findall(r'\d+', price_str.replace(",", ""))
    return int("".join(numbers)) if numbers else None

def extract_price_european_format(text):
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
    r = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for li in soup.select("ul#country-list li"):
        a = li.find("a")
        span = li.find("span")
        if a and span:
            results.append({
                "name": a.text.strip(),
                "url": "https://www.sigma-computer.com/" + a['href'],
                "price": extract_price(span.text),
                "store": "Sigma",
                "availability": "Check site"
            })
    return results

# ✅ 2. Elnekhely Technology (JSON)
def scrape_elnekhely(query):
    url = f"https://www.elnekhelytechnology.com/index.php?route=journal3/search&search={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    r = requests.get(url, headers=headers)
    results = []

    if r.status_code == 200 and "response" in r.json():
        for item in r.json()["response"]:
            if "href" in item and "name" in item and (item.get("special") or item.get("price")):
                price_str = item.get("special") or item.get("price")
                results.append({
                    "name": item["name"],
                    "url": item["href"],
                    "price": extract_price(price_str),
                    "store": "Elnekhely",
                    "availability": "In Stock" if item.get("quantity", 0) > 0 else "Out of Stock"
                })
    return results

#✅ 3. elbadrgroupeg
def scrape_elbadrgroupe(query):
    url = f"https://elbadrgroupeg.store/index.php?route=journal3/search&search={query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    r = requests.get(url, headers=headers)
    results = []

    if r.status_code == 200:
        try:
            data = r.json()
            if "response" in data:
                for item in data["response"]:
                    if "name" in item and (item.get("special") or item.get("price")):
                        price_str = item.get("special") or item.get("price")
                        results.append({
                            "name": item["name"],
                            "url": item.get("href", "#"),
                            "price": extract_price(price_str),
                            "store": "ElBadrGroup",
                            "availability": "In Stock" if item.get("quantity", 0) > 0 else "Out of Stock"
                        })
        except Exception as e:
            print("❌ Error parsing JSON from ElBadrGroup:", e)

    return results

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

    r = requests.get(url, headers=headers)
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
                        if price:
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

    r = requests.get(url, headers=headers)
    results = []

    if r.status_code == 200:
        try:
            data = r.json()
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    name = item.get("name") or item.get("title")
                    link = "https://delta-computer.net/product/" + str(item.get("slug", ""))
                    price = extract_price(item.get("price"))
                    if name and price:
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
                        "store": "ElnourTech",
                        "availability": "Check site"
                    })
        except Exception as e:
            print("❌ Error parsing JSON from ElnourTech:", e)

    return results
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

# ✅ Combine all scrapers
def scrape_all(query):
    all_data = []
    for func in [
        scrape_sigma,
        scrape_elnekhely,
        scrape_elbadrgroupe,
        scrape_barakacomputer,
        scrape_deltacomputer,
        scrape_elnourtech,
        scrape_solidhardware,
        scrape_alfrensia,
        scrape_ahwstore,
        scrape_kimostore,
        scrape_uptodate,
        scrape_abcshop,
        scrape_compumarts,
        scrape_compunilestore,
        scrape_compuscience  
    ]:
        try:
            all_data.extend(func(query))
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
    return pd.DataFrame(all_data).sort_values("price", na_position="last")

# === Streamlit UI ===
st.title("💻 Egypt Tech Price Comparison")
query = st.text_input("🔍 Search for a product (e.g. RTX 4070):")

if query:
    with st.spinner("🔄 Fetching data..."):
        df = scrape_all(query)
        if df.empty:
            st.warning("No results found.")
        else:
            for row in df.itertuples():
                st.markdown(f"### [{row.name}]({row.url})")
                st.write(f"💰 **{row.price:,} EGP**  | 🏪 *{row.store}* | 📦 {row.availability}")