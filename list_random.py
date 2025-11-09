from bs4 import BeautifulSoup
from selenium import webdriver
import time
import datetime
import re
import random
import logging
import sys
from typing import Optional

def getlink():
    chrome_options = webdriver.ChromeOptions()
    #chrome_options.binary_location = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"    #chrome binary location specified here
    #chrome_options.add_argument('--no-sandbox') #bypass OS security model
    #chrome_options.add_experimental_option("useAutomationExtension", False)
    #chrome_options.add_argument('--headless=old') # 啟動無頭模式
    chrome_options.add_argument('--headless') # 啟動無頭模式
    #chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument('--disable-gpu') # windowsd必須加入此行
    chrome_options.add_argument("--silent")
    chrome_options.add_argument('--ignore-certificate-errors')#忽略 SSL 憑證錯誤
    chrome_options.add_argument('--incognito')#開啟無痕模式
    chrome_options.add_argument('--disable-plugins')
    #chrome_options.add_argument("--disable-notifications")#停用瀏覽器通知。在某些網站上，瀏覽器可能會彈出通知框，詢問使用者是否允許網站發送通知。 透過設定該參數，可以停用這些通知框的顯示，從而防止它們打斷自動化腳本的執行。
    chrome_options.add_argument('--disable-infobars')#停用 Chrome 通知欄
    chrome_options.add_argument("--log-level=3")
    #chrome_options.add_argument("--disable-dev-shm-usage")  # 使用更大的共享內存空間
    #chrome_options.add_argument("--disable-popup-blocking")#停用彈出視窗阻止，瀏覽器通常會阻止視窗彈出，此設定可以停用瀏覽器的彈出視窗阻止功能，允許彈出視窗的顯示。
    #driver = webdriver.Chrome(service=service,options=chrome_options)
    # This function can accept a browser-like object via parameter (see refactor below)
    # Keep signature for backward compatibility by calling inner implementation.
    with Browser() as browser:
        return _getlink_with_browser(browser)


def _getlink_with_browser(browser):
    url = "https://queenienie.pixnet.net/blog?m=off"
    browser.safe_get(url)

    linkdict = {}
    soup = BeautifulSoup(browser.page_source, features="html.parser")
    mylinks = soup.find_all('li', attrs={'data-article-link': re.compile('https')})

    for li in mylinks:
        a = li.find('a')
        if not a:
            continue
        href = a.get('href')
        if not href:
            continue
        simplizelink = href.split('-')[0].strip()
        articlenumber = simplizelink.split("/")[-1].strip().split("?")[0].strip()

        articlecount = "Not Available"
        span = soup.find("span", {"id": f"BlogArticleCount-{articlenumber}"})
        if span and span.get_text():
            articlecount = span.get_text(strip=True)

        simplizetitle = f"({articlecount}) {a.get_text(strip=True)}"
        linkdict[simplizelink] = simplizetitle

    return linkdict


def scraper(url):
    # Backwards-compatible wrapper: create a short-lived browser for single-call usage
    with Browser() as browser:
        return _scraper_with_browser(url, browser)


def _scraper_with_browser(url, browser):
    logging.info("parsing html by BeautifulSoup.....")
    browser.safe_get(url)
    soup = BeautifulSoup(browser.page_source, features="html.parser")

    # 取得文章標題（嘗試多種方法）
    title_tag = soup.find("a", {"href": url})
    if title_tag and title_tag.get_text():
        mytitle = title_tag.get_text(strip=True)
    else:
        og = soup.find('meta', property='og:title')
        mytitle = og['content'] if og and og.get('content') else "No title"

    # 取得文章日期
    dm = soup.find("span", {"class": "month"})
    dateMonth = dm.get_text(strip=True) if dm else "Unknown"
    dy = soup.find("span", {"class": "year"})
    dateYear = dy.get_text(strip=True) if dy else "Unknown"
    dd = soup.find("span", {"class": "date"})
    dateDate = dd.get_text(strip=True) if dd else "Unknown"

    # 取得文章人氣
    myid = url.split("/")[-1].strip().split("?")[0].strip()
    cnt_span = soup.find("span", {"id": f"BlogArticleCount-{myid}"})
    count = cnt_span.get_text(strip=True) if cnt_span else "0"

    # 取得本日人氣
    today_span = soup.find("span", {"id": "blog_hit_daily"})
    todaycount = today_span.get_text(strip=True) if today_span else "0"

    logging.info("%s", "=" * 100)
    logging.info(mytitle)
    logging.info("%s/%s/%s", dateYear, dateMonth, dateDate)
    logging.info("count: %s", count)
    logging.info("%s", "=" * 20)
    logging.info("todaycount: %s", todaycount)
    logging.info("%s", "=" * 100)
    return {
        'title': mytitle,
        'date': (dateYear, dateMonth, dateDate),
        'count': count,
        'todaycount': todaycount,
    }


class Browser:
    """Simple context manager wrapper around selenium webdriver.Chrome.

    Provides .get(url) and .page_source and ensures quit() on exit.
    """

    def __init__(self, headless: bool = True, max_retries: int = 2):
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self.max_retries = max_retries

    def _make_options(self):
        opts = webdriver.ChromeOptions()
        if self.headless:
            opts.add_argument('--headless')
        opts.add_argument('--disable-gpu')
        opts.add_argument("--silent")
        opts.add_argument('--ignore-certificate-errors')
        opts.add_argument('--incognito')
        opts.add_argument('--disable-plugins')
        opts.add_argument('--disable-infobars')
        opts.add_argument("--log-level=3")
        return opts

    def __enter__(self):
        # create driver on enter
        self._ensure_driver()
        return self

    def _make_driver(self):
        return webdriver.Chrome(options=self._make_options())

    def _ensure_driver(self):
        if self.driver is None:
            try:
                self.driver = self._make_driver()
                logging.info('Browser: started driver')
            except Exception:
                logging.exception('Browser: failed to start driver')
                self.driver = None

    def get(self, url):
        # kept for backward compatibility; prefer safe_get
        return self.safe_get(url)

    def safe_get(self, url):
        """Attempt to get `url` with retries and restart on failure."""
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                self._ensure_driver()
                if not self.driver:
                    raise RuntimeError('No webdriver available')
                self.driver.get(url)
                return True
            except Exception as exc:
                last_exc = exc
                logging.exception('Browser: get failed on attempt %s', attempt)
                try:
                    self.restart()
                except Exception:
                    logging.exception('Browser: restart failed')
                time.sleep(1)
        # after retries
        if last_exc is None:
            raise RuntimeError('Browser: safe_get failed without exception')
        raise last_exc

    def restart(self):
        logging.info('Browser: restarting driver')
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
            # attempt to create a new driver
            self.driver = None
            self._ensure_driver()
            if not self.driver:
                raise RuntimeError('Browser: restart could not create driver')
        except Exception:
            logging.exception('Browser: restart encountered exception')
            raise

    @property
    def page_source(self):
        self._ensure_driver()
        if not self.driver:
            return ''
        return self.driver.page_source

    def delete_all_cookies(self):
        try:
            self._ensure_driver()
            if self.driver:
                self.driver.delete_all_cookies()
        except Exception:
            pass

    def quit(self):
        try:
            if self.driver:
                try:
                    self.driver.quit()
                finally:
                    self.driver = None
        except Exception:
            pass

    def __exit__(self, exc_type, exc, tb):
        self.quit()


def run_local_tests():
    """Simple parsing tests using static HTML (no Selenium)."""
    logging.info("Running local parsing tests...")
    sample = """
    <html>
      <head>
        <meta property='og:title' content='Sample OG Title' />
      </head>
      <body>
        <a href='https://example.com/article/123'>Sample Title</a>
        <span class='month'>11</span>
        <span class='year'>2025</span>
        <span class='date'>07</span>
        <span id='BlogArticleCount-123'>42</span>
        <span id='blog_hit_daily'>5</span>
      </body>
    </html>
    """
    soup = BeautifulSoup(sample, features="html.parser")
    # mimic scraper parsing steps
    title_tag = soup.find("a", {"href": 'https://example.com/article/123'})
    title = title_tag.get_text(strip=True) if title_tag else None
    assert title == 'Sample Title', 'title mismatch'
    cnt_span = soup.find("span", {"id": 'BlogArticleCount-123'})
    assert cnt_span and cnt_span.get_text(strip=True) == '42'
    logging.info('Local tests passed')


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    # support quick local tests without launching browser
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        run_local_tests()
        return

    # create a single shared browser instance and reuse it
    with Browser() as browser:
        mylink_dict = _getlink_with_browser(browser)
        mylink_list = list(mylink_dict.keys())
        if not mylink_list:
            logging.error("No links found. Exiting.")
            return

        mycount = 0
        while True:
            logging.info("-- Starting --")
            try:
                mylink = random.choice(mylink_list)
                logging.info(mylink)
                _scraper_with_browser(mylink, browser)
                mycount += 1
                logging.info("mycount: %s", mycount)
            except Exception:
                logging.exception("Exception occurred while scraping")

            logging.info(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            time.sleep(45)
            if mycount == 10:
                break


if __name__ == "__main__":
    main()
