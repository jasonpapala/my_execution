from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time
import datetime
import re
import random
import logging
import sys
from typing import Optional



def _normalize_number(s: str):
    if not s:
        return None
    # remove non-digit separators like commas and spaces
    s2 = re.sub(r"[,\s]", "", s)
    m = re.search(r"(\d+)", s2)
    return int(m.group(1)) if m else None


def scrape_post(url: str, timeout: int = 20, initial_wait: int = 8):
    """Scrape the given Pixnet post URL and return today's hits and the popularity number.

    initial_wait: seconds to wait after navigating to the page to allow dynamic JS content to populate
    """
    logging.info('Scraping %s (initial_wait=%ds)', url, initial_wait)

    opts = webdriver.ChromeOptions()
    opts.add_argument('--headless')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--ignore-certificate-errors')
    opts.add_argument('--incognito')

    driver = webdriver.Chrome(options=opts)

    try:
        driver.get(url)

        # Give dynamic JS a short moment to populate counters (useful when initial values are 0)
        if initial_wait and initial_wait > 0:
            logging.debug('Waiting %ds for dynamic content to load', initial_wait)
            time.sleep(initial_wait)

        wait = WebDriverWait(driver, timeout)
        # wait until one of: BlogArticleCount- span exists, or blog_hit_daily exists, or some text containing '人氣' appears
        try:
            wait.until(lambda d: any((e.get_attribute('textContent') or '').strip() for e in d.find_elements(By.CSS_SELECTOR, 'span[id^="BlogArticleCount-"]'))
                       or any((e.get_attribute('textContent') or '').strip() for e in d.find_elements(By.ID, 'blog_hit_daily'))
                       or d.find_elements(By.XPATH, '//*[contains(text(), "人氣")]'))
        except Exception:
            logging.debug('Timed out waiting for count elements; continuing to parse page source')

        time.sleep(0.1)

        # Prefer the first span with id starting with BlogArticleCount-
        bcounts = driver.find_elements(By.CSS_SELECTOR, 'span[id^="BlogArticleCount-"]')
        popularity = None
        popularity_id = None
        if bcounts:
            # poll until element text becomes a non-zero number (re-find to avoid stale references)
            raw = None
            popularity = None
            end = time.time() + timeout
            while time.time() < end:
                els = driver.find_elements(By.CSS_SELECTOR, 'span[id^="BlogArticleCount-"]')
                if not els:
                    time.sleep(0.3)
                    continue
                el0 = els[0]
                try:
                    popularity_id = el0.get_attribute('id')
                    raw = (el0.get_attribute('textContent') or '').strip() or el0.text.strip()
                except StaleElementReferenceException:
                    logging.debug('Stale element while reading BlogArticleCount; re-finding and retrying')
                    time.sleep(0.2)
                    continue
                if not raw:
                    try:
                        raw_html = el0.get_attribute('innerHTML') or ''
                    except StaleElementReferenceException:
                        logging.debug('Stale element while reading innerHTML; retrying')
                        time.sleep(0.2)
                        continue
                    m_html = re.search(r'([0-9,]+)', raw_html)
                    if m_html:
                        raw = m_html.group(1)
                num = _normalize_number(raw)
                if num and num > 0:
                    popularity = num
                    break
                time.sleep(0.5)
            # final attempt (could be zero)
            if popularity is None and raw:
                popularity = _normalize_number(raw)
            logging.debug('Found BlogArticleCount raw=%r id=%s -> popularity=%s', raw, popularity_id, popularity)

        # Today count (poll until non-zero if possible)
        todaycount = None
        try:
            raw_today = None
            end = time.time() + timeout
            while time.time() < end:
                els = driver.find_elements(By.ID, 'blog_hit_daily')
                if not els:
                    time.sleep(0.3)
                    continue
                el = els[0]
                try:
                    raw_today = (el.get_attribute('textContent') or '').strip() or el.text.strip()
                except StaleElementReferenceException:
                    logging.debug('Stale element while reading blog_hit_daily; retrying')
                    time.sleep(0.2)
                    continue
                if not raw_today:
                    try:
                        raw_html = el.get_attribute('innerHTML') or ''
                    except StaleElementReferenceException:
                        logging.debug('Stale element while reading innerHTML(blog_hit_daily); retrying')
                        time.sleep(0.2)
                        continue
                    m_html = re.search(r'([0-9,]+)', raw_html)
                    if m_html:
                        raw_today = m_html.group(1)
                num = _normalize_number(raw_today)
                if num and num > 0:
                    todaycount = num
                    break
                time.sleep(0.5)
            if todaycount is None and raw_today:
                todaycount = _normalize_number(raw_today)
            logging.debug('Found blog_hit_daily raw=%r -> todaycount=%s', raw_today, todaycount)
        except Exception:
            # not found
            todaycount = None

        # Bracketed '人氣(52)' search anywhere in visible text
        page_html = driver.page_source
        soup = BeautifulSoup(page_html, 'html.parser')
        bracket_val = None
        bracket_candidates = []
        # Search text nodes that include '人氣' and a parenthesized number (collect candidates)
        for text_node in soup.find_all(string=re.compile(r"人氣")):
            # skip script/style and other non-visible containers
            parent_name = getattr(text_node, 'parent', None)
            parent_tag = parent_name.name if parent_name is not None else None
            if parent_tag in ('script', 'style'):
                continue
            txt = text_node.strip()
            # prefer numbers in parentheses in the same visible text node / element
            for m in re.finditer(r'[\(（]\s*([0-9,]+)\s*[\)）]', txt):
                v = _normalize_number(m.group(1))
                if v is not None:
                    bracket_candidates.append((v, txt))
            # also consider inline numbers if parentheses not present
            if not bracket_candidates:
                m2 = re.search(r'([0-9,]{1,})', txt)
                if m2:
                    v = _normalize_number(m2.group(1))
                    if v is not None:
                        bracket_candidates.append((v, txt))

        if bracket_candidates:
            # prefer candidate closest to BlogArticleCount if available
            nums = [v for v, t in bracket_candidates]
            if popularity is not None:
                bracket_val = min(nums, key=lambda x: abs((popularity or 0) - x))
            else:
                bracket_val = nums[0]
            logging.debug('Bracket candidates: %r -> chosen %s', bracket_candidates, bracket_val)

        # If we couldn't find a bracketed popularity but found BlogArticleCount, use it as a fallback
        if bracket_val is None and popularity is not None:
            bracket_val = popularity

        # Extract title from parsed HTML (prefer article header link)
        title = None
        title_tag = soup.select_one('li.title h2 a') or soup.select_one('h2 a')
        if title_tag:
            title = title_tag.get_text(strip=True)
        else:
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

        return {
            'today': todaycount,
            'popularity': popularity,
            'popularity_id': popularity_id,
            'bracket': bracket_val,
            'title': title,
        }

    finally:
        try:
            driver.quit()
        except Exception:
            pass


def pick_random_article(blog_url: str, timeout: int = 10):
    """Visit the blog index and pick a random article URL. Returns full URL or None."""
    logging.info('Selecting a random article from %s', blog_url)
    opts = webdriver.ChromeOptions()
    opts.add_argument('--headless')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--ignore-certificate-errors')
    opts.add_argument('--incognito')

    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(blog_url)
        wait = WebDriverWait(driver, timeout)
        try:
            wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, 'a[href*="/blog/posts/"], a[href*="/blog/post/"]'))
        except Exception:
            logging.debug('Timed out waiting for article links; continuing to find whatever is present')

        links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/blog/posts/"], a[href*="/blog/post/"]')
        hrefs = []
        for a in links:
            try:
                h = a.get_attribute('href')
            except StaleElementReferenceException:
                continue
            if not h:
                continue
            if h.startswith('/'):
                h = 'https://queenienie.pixnet.net' + h
            hrefs.append(h)
        # dedupe while preserving order
        hrefs = list(dict.fromkeys(hrefs))
        if not hrefs:
            logging.warning('No article links found on %s', blog_url)
            return None
        chosen = random.choice(hrefs)
        logging.info('Picked random article: %s', chosen)
        return chosen
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = pick_random_article('https://queenienie.pixnet.net/blog', timeout=15)
        if not url:
            logging.info('Falling back to default article URL')
            #url = 'https://queenienie.pixnet.net/blog/posts/14222990361'

    # If a URL was provided on the command line, just scrape that once.
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        logging.info('Scraping chosen URL: %s', url)
        result = scrape_post(url, timeout=20)
        #print('Result:', result)
        print ("Selected article:", url)
        print ("文章標題: ", result.get('title'))
        print ("BLOG今日人氣: ", result['today'])
        print ("文章今日人氣: ", result['popularity'])
        #print ("Popularity ID: ", result['popularity_id'])
        print ("Bracketed popularity: ", result['bracket'])
    else:
        # No explicit URL provided -> run 10 iterations: pick random article each time
        iterations = 10
        interval_seconds = 40
        logging.info('Starting %d iterations, interval %ds', iterations, interval_seconds)
        success = 0
        for i in range(1, iterations + 1):
            logging.info('Iteration %d/%d', i, iterations)
            # Try to pick an article with up to 2 retries
            picked = None
            retries = 2
            for attempt in range(retries + 1):
                picked = pick_random_article('https://queenienie.pixnet.net/blog', timeout=15)
                if picked:
                    break
                logging.warning('Pick attempt %d failed; retrying...', attempt + 1)
                time.sleep(1)
            if not picked:
                logging.warning('No article picked after %d attempts; skipping iteration %d', retries + 1, i)
                continue

            try:
                res = scrape_post(picked, timeout=20)
                print(f'[{i}] Selected article: {picked}')
                print(f'[{i}] Title: {res.get("title")}')
                print(f'[{i}] BLOG今日人氣: {res.get("today")}')
                print(f'[{i}] 文章今日人氣: {res.get("popularity")}')
                print(f'[{i}] Bracketed popularity: {res.get("bracket")}')
                success += 1
            except Exception:
                logging.exception('Error scraping article on iteration %d', i)

            if i < iterations:
                logging.info('Sleeping %d seconds before next iteration', interval_seconds)
                time.sleep(interval_seconds)

        logging.info('Completed %d iterations (%d successful)', iterations, success)
