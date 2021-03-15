#!/usr/bin/env python

# -*- coding: utf-8 -*-

import yaml
import requests
from parsel import Selector

headers = {
    'Accept-Language':"zh-CN,zh;q=0.8",
    'Accept-Encoding':"gzip, deflate",
    'Content-Type':"application/x-www-form-urlencoded",
    'Connection':"keep-alive",
    'Referer':"http://localhost/login",
    'User-Agent':"Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.86 Safari/537.36"
}

class Site():
  def __init__(self,url, item, title, item_url, item_date, item_hacknewslink, item_points, item_comments, item_fromsite, item_fromsitename):
    self.url = url
    self.item = item
    self.item_title = title
    self.item_url = item_url
    self.item_date = item_date
    self.item_hacknewslink = item_hacknewslink
    self.item_points = item_points
    self.item_comments = item_comments
    self.item_fromsite = item_fromsite
    self.item_fromsitename = item_fromsitename
  
sites = yaml.load_all(open('my_tmp.yaml',encoding='utf-8' ), Loader=yaml.FullLoader)

def handle_site(site):
  print(site.url)
  page = requests.get(site.url, headers=headers, verify=False).text
  print(page)
  selector = Selector(page)
  articles = selector.xpath(site.item)
  print(articles)
  i=0
  for index, article in enumerate(articles):
      print(index)
      title = article.xpath(site.item_title).get()
      url = article.xpath(site.item_url).get()
      if site.item_date:
        date = article.xpath(site.item_date).get()
        print(date)
      print(title.encode('utf-8'))
      hacknewslink = article.xpath(site.item_hacknewslink).get()
      print(hacknewslink)
      points = article.xpath(site.item_points).get()
      print('x'+points+'x')
      comments = article.xpath(site.item_comments).get()
      print('x'+comments+'x')           
      fromsite = article.xpath(site.item_fromsite).get()
      print(fromsite)  
      fromsitename = article.xpath(site.item_fromsitename).get()
      print(fromsitename)               
      if i != index:
        print('error')
      i = i + 1
      print(url)
  
for site in sites:
   date = None
   if 'item_date' in site:
      date = site['item_date']
   aSite = Site(site['url'], site['item'], site['item_title'],site['item_url'], date, site['item_hacknewslink'],  site['item_points'],  site['item_comments'] , site['item_fromsite'], site['item_fromsitename'])
   handle_site(aSite)
    

