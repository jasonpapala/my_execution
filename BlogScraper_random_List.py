from __future__ import annotations

import random
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


BLOG_URL = "https://queenienie.pixnet.net/blog?m=off"
ARTICLE_LIMIT = 12
ARTICLE_READS_PER_RUN = 2
SLEEP_BETWEEN_READS = 5
PAGE_TIMEOUT = 30
WAIT_TIMEOUT = 8


try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


@dataclass(frozen=True)
class Article:
    url: str
    title: str
    popularity: str


def normalize_count(text: Optional[str]) -> str:
    if not text:
        return "Not Available"
    digits = re.sub(r"[^\d]", "", text)
    return digits or text.strip() or "Not Available"


def extract_article_id(url: str) -> str:
    last = url.split("/")[-1].split("?")[0].strip()
    match = re.match(r"(\d+)", last)
    return match.group(1) if match else last


def make_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--incognito")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--log-level=3")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    )
    options.add_experimental_option(
        "prefs",
        {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        },
    )

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(PAGE_TIMEOUT)
    driver.set_script_timeout(PAGE_TIMEOUT)
    return driver


def wait_for_list_page(driver: webdriver.Chrome) -> None:
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, 'a[href*="/blog/posts/"], a[href*="/blog/post/"]')
        )
    except Exception:
        pass

    try:
        WebDriverWait(driver, 8).until(
            lambda d: any(
                (el.get_attribute("textContent") or "").strip()
                for el in d.find_elements(By.CSS_SELECTOR, 'span.author-views span[data-role="total"]')
            )
        )
    except Exception:
        pass


def get_list_page_count(soup: BeautifulSoup, article_id: str) -> str:
    view_box = soup.find("span", {"class": "author-views", "data-post-id": article_id})
    if view_box:
        total = view_box.find("span", {"data-role": "total"})
        if total:
            return normalize_count(total.get_text(strip=True))

    count_el = soup.find("span", {"id": f"BlogArticleCount-{article_id}"})
    if count_el:
        return normalize_count(count_el.get_text(strip=True))

    container = soup.find(id=f"article-{article_id}")
    if container:
        count_el = container.find("span", id=re.compile(r"^BlogArticleCount"))
        if count_el:
            return normalize_count(count_el.get_text(strip=True))

    return "Not Available"


def fetch_latest_articles(driver: webdriver.Chrome) -> list[Article]:
    driver.get(BLOG_URL)
    wait_for_list_page(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    seen: set[str] = set()
    articles: list[Article] = []

    for link in soup.select('a[href*="/blog/posts/"], a[href*="/blog/post/"]'):
        href = (link.get("href") or "").strip()
        title = link.get_text(strip=True)
        if not href or not title:
            continue
        if href.startswith("/"):
            href = "https://queenienie.pixnet.net" + href
        href = href.split("#", 1)[0]
        href = href.split("-", 1)[0].strip()
        if href in seen:
            continue

        article_id = extract_article_id(href)
        popularity = get_list_page_count(soup, article_id)
        seen.add(href)
        articles.append(Article(url=href, title=title, popularity=popularity))

        if len(articles) >= ARTICLE_LIMIT:
            break

    return articles


def wait_for_article_count(driver: webdriver.Chrome) -> None:
    selectors = 'span#BlogArticleCount, span[id^="BlogArticleCount-"], span.author-views span[data-role="total"]'
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: any((el.get_attribute("textContent") or "").strip() for el in d.find_elements(By.CSS_SELECTOR, selectors))
        )
    except Exception:
        pass


def parse_article_page(driver: webdriver.Chrome, fallback: Article) -> Article:
    driver.get(fallback.url)
    wait_for_article_count(driver)

    selectors = 'span#BlogArticleCount, span[id^="BlogArticleCount-"], span.author-views span[data-role="total"]'
    popularity = "Not Available"
    end_time = time.time() + WAIT_TIMEOUT

    while time.time() < end_time:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, selectors):
                text = (el.get_attribute("textContent") or el.text or "").strip()
                count = normalize_count(text)
                if count != "Not Available":
                    popularity = count
                    raise StopIteration
        except StaleElementReferenceException:
            time.sleep(0.2)
            continue
        except StopIteration:
            break
        time.sleep(0.3)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    title = fallback.title
    if soup.select_one("li.title h2 a"):
        title = soup.select_one("li.title h2 a").get_text(strip=True)
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    return Article(url=fallback.url, title=title, popularity=popularity)


def print_latest_articles(articles: list[Article]) -> None:
    print("最新文章列表：")
    for index, article in enumerate(articles, start=1):
        print(f"{index} : {article.popularity} : {article.title}")
    print()


def main() -> int:
    driver = make_driver()
    read_count = 0

    try:
        articles = fetch_latest_articles(driver)
        if not articles:
            print("沒有抓到文章列表，本次結束。")
            return 0

        print_latest_articles(articles)

        selected_articles = random.sample(articles, k=min(ARTICLE_READS_PER_RUN, len(articles)))
        for run_number, selected in enumerate(selected_articles, start=1):
            result = parse_article_page(driver, selected)
            read_count += 1

            print(f"第 {run_number} 次")
            print(f"{result.popularity} : {result.title}")
            print(f"執行的次數：{read_count}")
            print()

            if run_number < ARTICLE_READS_PER_RUN:
                print(f"等待 {SLEEP_BETWEEN_READS} 秒...")
                time.sleep(SLEEP_BETWEEN_READS)

        print(f"本次執行完成，共讀取文章頁 {read_count} 次")
        return 0
    finally:
        try:
            driver.delete_all_cookies()
        except Exception:
            pass
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
