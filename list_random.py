from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import datetime
import re
import requests
import os
import random

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
    #chrome_options.add_argument("--window-size=1,1")#設定瀏覽器視窗大小
    #chrome_options.add_argument('--remote-debugging-port=61625')
    #chrome_options.add_argument("--disable-notifications")#停用瀏覽器通知。在某些網站上，瀏覽器可能會彈出通知框，詢問使用者是否允許網站發送通知。 透過設定該參數，可以停用這些通知框的顯示，從而防止它們打斷自動化腳本的執行。
    chrome_options.add_argument('--disable-infobars')#停用 Chrome 通知欄
    chrome_options.add_argument("--log-level=3")
    #chrome_options.add_argument("--disable-dev-shm-usage")  # 使用更大的共享內存空間
    #chrome_options.add_argument("--disable-popup-blocking")#停用彈出視窗阻止，瀏覽器通常會阻止視窗彈出，此設定可以停用瀏覽器的彈出視窗阻止功能，允許彈出視窗的顯示。
    #chrome_options.add_argument("--user-agent=Mozilla/5.0 (Linux; Android 12; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36")#設定瀏覽器的使用者代理字串
    #service = Service("F:\JASON資料\Python\MyCode\BlogScraper\scraper_portable\chromedriver.exe")
    #driver = webdriver.Chrome(service=service,options=chrome_options)
    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://queenienie.pixnet.net/blog?m=off")

    linkdict={}
    soup = BeautifulSoup(driver.page_source, features="html.parser")
    mylink=soup.find_all('li', attrs={'data-article-link':re.compile('https')})


    for onelink in mylink:
        for i in onelink:
            simplizelink = i.find('a')['href']
            simplizelink=simplizelink.split('-')[0].strip()
            articlenumber=simplizelink.split("/")[-1].strip().split("?")[0].strip()
            try:
                articlecount=soup.find("span",{"id":"BlogArticleCount-"+articlenumber}).text
            except:
                articlecount="Not Available"
            simplizetitle = "("+articlecount+")"+i.text
            linkdict[simplizelink]=simplizetitle
 
    return linkdict


def scraper(url):
    print ("webdriver.Chrome calling....")
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless') # 啟動無頭模式
    chrome_options.add_argument('--disable-gpu') # windowsd必須加入此行
    chrome_options.add_argument("--silent")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--incognito')
    chrome_options.add_argument('--disable-plugins')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument("--log-level=3")
    #chrome_options.add_argument("--window-size=1,1")#設定瀏覽器視窗大小
    #driver = webdriver.Chrome(executable_path="D:/JASON資料/Python/MyCode/chromedriver.exe",chrome_options=chrome_options)
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

    #取得本日人氣
    todaycount = soup.find("span",{"id":"blog_hit_daily"}).text
    
    print ("="*100)
    print (mytitle)
    print ("{}/{}/{}".format(dateYear.strip(),dateMonth.strip(),dateDate.strip()))
    print ("count:",count)
    print ("="*20)
    print ("todaycount:",todaycount)
    print ("="*100) 

    driver.delete_all_cookies()
    driver.quit()


mylink_dict=getlink()
mylink_list=list(mylink_dict.keys())
'''for i in range(len(mylink_dict)):
    print ("{}: {:.60}".format(i+1,mylink_dict[mylink_list[i]]))
print ()  
'''

mycount=0
while True:
    print ("-- Starting --")  
    try:
        myinput = random.randint(1, 40)
        mylink=mylink_list[int(myinput)-1]
        print (mylink)
        scraper(mylink)
        mycount+=1
        print ("mycount: "+str(mycount))
    except Exception as e:
        print ("="*40)
        print ("Exception occurred, error message as following:")
        print (e)
        print ("="*40)
        pass
    print (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    time.sleep(60)
    if mycount==4:
        break 
