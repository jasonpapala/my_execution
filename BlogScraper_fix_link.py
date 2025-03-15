from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import datetime
import re
import os

def scraper(url):
    print ("webdriver.Chrome calling....")
    chrome_options = Options()
    #chrome_options.add_argument('--headless=old') # 啟動無頭模式
    chrome_options.add_argument('--headless') # 啟動無頭模式
    #chrome_options.add_argument("--remote-debugging-port=9222")  # 添加遠程調試
    chrome_options.add_argument('--disable-gpu') # windowsd必須加入此行
    #chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--incognito')
    chrome_options.add_argument('--disable-plugins')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument("--log-level=3")
    #chrome_options.add_argument("--no-sandbox")  # 避免沙盒問題
    #chrome_options.add_argument("--disable-dev-shm-usage")  # 使用更大的共享內存空間
    #chrome_options.binary_location = "C:\Program Files\Google\Chrome\Application\chrome.exe"  # 修改為你的 Chrome 路徑

    #chrome_options.add_argument("--window-size=1,1")#設定瀏覽器視窗大小
    #driver = webdriver.Chrome(executable_path="F:\JASON資料\Python\MyCode\BlogScraper\scraper_portable\chromedriver.exe",chrome_options=chrome_options)

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    print ("parsering html by BeautifulSoup.....")
    soup = BeautifulSoup(driver.page_source, features="html.parser")
    
    #取得文章標題
    mytitle = soup.find("a",{"href":url}).text 

    #取得文章日期
    dateMonth = soup.find("span",{"class":"month"}).text 
    dateYear = soup.find("span",{"class":"year"}).text 
    dateDate = soup.find("span",{"class":"date"}).text
    
    #取得文章人氣
    myid=url.split("/")[-1].strip().split("?")[0].strip()
    count = soup.find("span",{"id":"BlogArticleCount-"+myid}).text

    #取得文章內容
    #contents = soup.find("div",{"class":"article-content-inner"})
    #content = str(contents)  

    #取得下一篇文章連結
    '''nextarticle = soup.findAll("link",{"rel":"prev"}, href = re.compile('http'))
    for n in nextarticle:
        mynextarticle = n['href']
        mynextarticle = mynextarticle.split("-")[0].strip()
	'''
    #取得本日人氣
    todaycount = soup.find("span",{"id":"blog_hit_daily"}).text
    print ("AA"+todaycount)


    print ("="*100)
    print (mytitle)
    print ("{}/{}/{}".format(dateYear.strip(),dateMonth.strip(),dateDate.strip()))
    print ("文章人氣:",count)
    print ("="*20)
    print ("部落格本日人氣:",todaycount)
    print ("="*100) 

    driver.delete_all_cookies()
    time.sleep(2)
    driver.quit()


#inputurl= input("Please enter the link: ")
inputurl= "https://queenienie.pixnet.net/blog/post/222278428"
if inputurl == "":
    inputurl= "https://queenienie.pixnet.net/blog/post/222278428"
elif "%" in inputurl:
    inputurl=inputurl.split("-")[0].strip()
    
mycount=0
time1=datetime.datetime.now().strftime("%Y-%m-%d")
while True:
    print ("-- Starting --")  
    try:
        scraper(inputurl)
        mycount+=1
        print ("流覽次數: "+str(mycount))
    except Exception as e:
        print ("-"*50)
        print ("Exception occurred, error message as following:")
        print (e)
        print ("-"*50)
        pass
    print (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    time.sleep(60)
    if mycount==3:
        break 
