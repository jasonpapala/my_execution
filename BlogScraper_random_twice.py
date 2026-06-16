from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import time
import datetime
import re
import os
import random

# Configuration Constants
BLOG_URL = "https://queenienie.pixnet.net/blog?m=off"
SCRAPE_SLEEP_INTERVAL = 30
CLEAR_SCREEN_INTERVAL = 5
DRIVER_QUIT_DELAY = 2
INPUT_RANGE = 10


def get_chrome_options():
    """Create and configure Chrome options for headless browsing"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--silent")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--incognito')
    chrome_options.add_argument('--disable-plugins')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument("--log-level=3")
    return chrome_options

def get_article_count(soup, article_id):
    """Get the article count from the soup.

    Handles two page contexts:
    - List page:    <span class="author-views" data-post-id="{id}"><span data-role="total">N</span>
    - Article page: <span id="BlogArticleCount" data-post-id="{id}">N</span>
    """
    try:
        # List page: data-post-id on the outer span matches the article ID exactly.
        el = soup.find("span", {"class": "author-views", "data-post-id": article_id})
        if el:
            total = el.find("span", {"data-role": "total"})
            if total and total.get_text(strip=True):
                txt = total.get_text(strip=True)
                digits = re.sub(r"[^\d]", "", txt)
                return digits if digits else txt

        # Article page: single span with id="BlogArticleCount" (no dash, no ID suffix).
        el = soup.find("span", {"id": "BlogArticleCount"})
        if el and el.get_text(strip=True):
            txt = el.get_text(strip=True)
            digits = re.sub(r"[^\d]", "", txt)
            return digits if digits else txt
    except Exception:
        pass
    return "Not Available"
def get_link():
    """Fetch all article links from blog list page"""
    chrome_options = get_chrome_options()
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(BLOG_URL)

    # Wait for dynamically loaded popularity counts to populate.
    try:
        WebDriverWait(driver, 20).until(
            lambda d: any(
                el.text.strip()
                for el in d.find_elements(By.CSS_SELECTOR, 'span.author-views span[data-role="total"]')
            )
        )
    except Exception:
        pass

    link_dict = {}
    soup = BeautifulSoup(driver.page_source, features="html.parser")
    article_items = soup.find_all('li', attrs={'data-article-link': re.compile('https')})

    for item in article_items:
        # Find the anchor tag directly within this item
        link_element = item.find('a')
        if not link_element:
            continue

        href = link_element.get('href', '')
        if isinstance(href, (list, tuple)):
            href = href[0] if href else ''
        href = str(href).strip()
        if not href:
            continue

        link = href.split('-', 1)[0].strip()
        article_number = extract_article_id(link)

        # Try to find the popularity inside the article container first (id="article-<id>")
        article_count = get_article_count(soup, article_number)
        container = soup.find(id=f"article-{article_number}")
        if container:
            el = container.find("span", id=re.compile(r"^BlogArticleCount-"))
            if el:
                el_text = (el.get_text() or '').strip()
                if el_text:
                    article_count = re.sub(r"[^\d]", "", el_text)

        # Fallback: check list page span with exact id
        if not article_count:
            try:
                el = soup.find("span", {"id": f"BlogArticleCount-{article_number}"})
                if el:
                    el_text = (el.get_text() or '').strip()
                    if el_text:
                        article_count = re.sub(r"[^\d]", "", el_text)
            except (AttributeError, TypeError):
                article_count = None

        if not article_count:
            article_count = "Not Available"

        title = f"({article_count}){link_element.get_text(strip=True)}"
        link_dict[link] = title
    
    driver.delete_all_cookies()
    driver.quit()
    return link_dict


def extract_article_id(url):
    """Extract article ID from URL (return leading numeric ID if present)"""
    last = url.split("/")[-1].strip().split("?")[0].strip()
    m = re.match(r"(\d+)", last)
    if m:
        return m.group(1)
    return last

def parse_article_data(soup, url):
    """Parse article data from soup with robust fallbacks and normalization"""
    article_id = extract_article_id(url)

    # Title: try og:title, then h1/title tag, then link with full URL
    title = None
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og.get("content").strip()
    if not title:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
    if not title:
        a = soup.find("a", {"href": url})
        if a and a.get_text(strip=True):
            title = a.get_text(strip=True)
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        title = "Unknown Title"

    # Date pieces with fallbacks
    def get_span_class(cls):
        try:
            el = soup.find("span", {"class": cls})
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        except Exception:
            pass
        return "Unknown"

    month = get_span_class("month")
    year = get_span_class("year")
    date = get_span_class("date")

    # Popularity count: first try author-views widget used on Pixnet pages.
    count = get_article_count(soup, article_id)
    if count == "Not Available":
        try:
            # Fallback to first available author-views total if post-id mapping differs.
            el = soup.find("span", {"class": "author-views"})
            if el:
                total = el.find("span", {"data-role": "total"})
                if total and (txt := total.get_text(strip=True)):
                    count = txt
        except Exception:
            count = "Not Available"

    # Then try BlogArticleCount-* patterns for older/alternative templates.
    if not count or count == "Not Available":
        count = None
    try:
        container = soup.find(id=f"article-{article_id}")
        if container:
            el = container.find("span", id=re.compile(r"^BlogArticleCount-"))
            if el and (txt := el.get_text(strip=True)):
                count = re.sub(r"[^\d]", "", txt)
    except Exception:
        count = None

    # If not found inside container, search globally for the first BlogArticleCount- span
    if not count:
        try:
            el = soup.find("span", id=re.compile(r"^BlogArticleCount-"))
            if el and (txt := el.get_text(strip=True)):
                count = re.sub(r"[^\d]", "", txt)
        except Exception:
            count = None

    # As a final fallback, regex-search the HTML for BlogArticleCount-.*>(digits)</span>
    if not count:
        try:
            raw = str(soup)
            m = re.search(r"<span[^>]*id=[\"']BlogArticleCount-[^\"']+[\"'][^>]*>([\d,]+)</span>", raw)
            if m:
                count = re.sub(r"[^\d]", "", m.group(1))
        except Exception:
            count = None

    if not count:
        count = "Not Available"

    # Today's count
    today_count = "Not Available"
    try:
        el = soup.find("span", {"id": "blog_hit_daily"})
        if el and (txt := el.get_text(strip=True)):
            today_count = re.sub(r"[^\d]", "", txt)
    except Exception:
        pass

    data = {
        'title': title,
        'month': month,
        'year': year,
        'date': date,
        'count': count,
        'today_count': today_count
    }
    return data

def print_article_info(data):
    """Print article information in formatted way"""
    print("=" * 100)
    print(data['title'])
    print(f"{data['year']}/{data['month']}/{data['date']}")
    print(f"文章人氣: {data['count']}")
    print("=" * 20)
    print(f"部落格本日人氣: {data['today_count']}")
    print("=" * 100)

def scraper(url):
    """Scrape article data from given URL"""
    print("webdriver.Chrome calling....")
    chrome_options = get_chrome_options()
    driver = None
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # Wait until key counters are present to reduce transient Not Available results.
        try:
            WebDriverWait(driver, 10).until(
                lambda d: (
                    d.find_elements(By.ID, "BlogArticleCount")
                    or d.find_elements(By.ID, "blog_hit_daily")
                    or any(
                        el.text.strip()
                        for el in d.find_elements(By.CSS_SELECTOR, 'span.author-views span[data-role="total"]')
                    )
                )
            )
        except Exception:
            # Continue parsing with fallbacks even if wait times out.
            pass
        
        print("Parsing html by BeautifulSoup.....")
        soup = BeautifulSoup(driver.page_source, features="html.parser")
        
        data = parse_article_data(soup, url)
        print_article_info(data)
        
    finally:
        if driver:
            driver.delete_all_cookies()
            time.sleep(DRIVER_QUIT_DELAY)
            driver.quit()

def format_time(timestamp):
    """Format timestamp to string"""
    return timestamp.strftime("%Y-%m-%d")

def format_datetime(timestamp):
    """Format timestamp to datetime string"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def get_user_input(link_dict):
    """Get and validate user input for article selection"""
    link_list = list(link_dict.keys())
    
    print_article_list(link_dict)
    
    while True:
        user_input = input(f"Please enter the number: '1-{INPUT_RANGE}'\nor Enter the link directly:\n")
        
        if "queenienie.pixnet.net" in user_input:
            return user_input
        
        try:
            index = int(user_input)
            if 1 <= index <= len(link_dict):
                return link_list[index - 1]
        except ValueError:
            pass
        
        print("****Please Enter the correct Input****\n")

def print_article_list(link_dict):
    """Print all available article options"""
    link_list = list(link_dict.keys())

    for i in range(len(link_dict)):
        print(f"{i+1}: {link_dict[link_list[i]]:.60}")
    print()

def select_random_link(link_dict):
    """Randomly select one article link from the list"""
    link_list = list(link_dict.keys())
    if not link_list:
        return None
    return random.choice(link_list)

def run_scraper_loop(link, max_runs=None):
    """Main loop for scraping with daily reset"""
    count = 0
    current_date = format_time(datetime.datetime.now())
    
    try:
        while True:
            print("-- Starting --")
            
            try:
                scraper(link)
                count += 1
                print(f"流覽次數: {count}")
                if max_runs is not None and count >= max_runs:
                    print(f"Completed {count} runs. Closing scraper.")
                    break
                
            except Exception as e:
                print("=" * 40)
                print("Exception occurred, error message as following:")
                print(f"{type(e).__name__}: {e}")
                print("=" * 40)
            
            print(format_datetime(datetime.datetime.now()))
            time.sleep(SCRAPE_SLEEP_INTERVAL)
            
            if count % CLEAR_SCREEN_INTERVAL == 0:
                os.system("cls")
            
            new_date = format_time(datetime.datetime.now())
            if new_date != current_date:
                count = 0
                current_date = new_date
                
    except KeyboardInterrupt:
        print("\nScraper stopped by user.")

if __name__ == "__main__":
    link_dict = get_link()
    print_article_list(link_dict)
    selected_link = select_random_link(link_dict)
    if not selected_link:
        print("No article links found. Closing scraper.")
    else:
        print(selected_link)
        #selected_link = "https://queenienie.pixnet.net/blog/posts/14223129105"
        run_scraper_loop(selected_link, max_runs=2)
