#!/usr/bin/python
# -*- coding: UTF-8 -*-

from datetime import datetime, timedelta
from flask import flash
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import exists
from sqlalchemy.sql import func
import json
from parsel import Selector
import yaml
import requests
import html2text
import csv
import os
import re
import glob 
import math
from shlex import split
from urllib.parse import urlparse
from flask_cors import CORS
#from gne import GeneralNewsExtractor
#from flashtext import KeywordProcessor
from collections import Counter,OrderedDict

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__,
            static_url_path='',
            static_folder='static')
app.config.from_pyfile("hello3.cfg")
db = SQLAlchemy(app)
CORS(app, supports_credentials=True)
collectTime = datetime.now
doonsec_page = None


class Site2():
    def __init__(self, name, url, item, item_title, item_url, item_date, item_ext={}):
        self.name = name
        self.url = url
        self.item = item
        self.item_title = item_title
        self.item_url = item_url
        self.item_date = item_date
        self.item_ext = item_ext


class Article_View():
    def __init__(self, id, title='', url='', create_at='', site_name='', date='', quote='', tags=[], text=''):
        self.id = id
        self.title = title
        self.url = url
        self.create_at = create_at
        self.date = date
        self.site_name = site_name
        self.quote = quote
        self.tags = tags
        self.text = text


tags = db.Table('tags',
                db.Column('tag_id', db.Integer, db.ForeignKey(
                    'tag.id'), primary_key=True),
                db.Column('article_id', db.Integer, db.ForeignKey(
                    'article.id'), primary_key=True)
                )


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False, primary_key=False, index = True)
    url = db.Column(db.String(512), nullable=False, primary_key=False)
    create_at = db.Column(db.DateTime, default=collectTime)
    date = db.Column(db.String(128))
    summary = db.Column(db.String(512))
    text = db.Column(db.String(5120))
    author = db.Column(db.String(128))
    language = db.Column(db.String(16), default="zh_CN", nullable=False)
    tags = db.relationship('Tag', secondary=tags, lazy='subquery',
                           backref=db.backref('article', lazy=True))
    page_id = db.Column(db.Integer, db.ForeignKey('page.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey(
        'category.id'), nullable=False)
    is_delete = db.Column(db.Boolean, default=False)
    ext = db.Column(db.String(2048))


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    type = db.Column(db.String(32), default="system", nullable=False)


class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    articles = db.relationship('Article', backref='category', lazy=True)


class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    url = db.Column(db.String(512), nullable=False)
    priority = db.Column(db.Integer, default=0, nullable=False)
    articles = db.relationship('Article', backref='page', lazy=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(512), nullable=False)
    pages = db.relationship('Page', backref='site', lazy=True)


@app.route("/initabcdez")
def init_db():
    db.drop_all()
    db.create_all()
    return 'ok'


@app.route('/')
def root():
    return app.send_static_file('index.html')


"""
@app.route("/")
def show_all():
  article_views = []
  for a, p,count in db.session.query(Article, Page, func.count(Article.title)).filter(Article.page_id==Page.id).filter(Article.create_at>=datetime.now()-timedelta(days=3)).group_by(Article.title).order_by(Article.create_at.desc()).all():
    article_view = Article_View(a.id, a.title, a.url, a.create_at, p.name, a.date, count, a.tags, a.text)
    article_views.append(article_view)
  return render_template('index.html',
    sites = Site.query.all(),
    articles=article_views,
    #articles = Article.query.filter(Article.create_at>='2020-11-24').order_by(Article.create_at.desc()).all(),
    categorys=Category.query.all(), 
    tags=Tag.query.all())
"""


@app.route("/api/delete_article/<id>")
def del_article(id):
    a = Article.query.filter_by(id=int(id)).update({'is_delete': 1})
    db.session.commit()
    return 'ok'


@app.route('/api/multi_articles')
def get_multi_articles():
    article_views = []
    for a, count in db.session.query(Article, func.count(Article.title)).filter(Article.is_delete == False).group_by(Article.title).order_by(Article.create_at.desc()).all():
        if count > 1:
            article_views.append(
                {'title': a.title, 'url': a.url, 'count': count})
    return jsonify(article_views)

@app.route('/api/groups')
def get_groups():
    groups = [
        {0:'工具',  1:'神器 利器 好用 工具 无敌 顶级 一款 强大的 强大 扫描工具 扫描器 蚁剑 冰蝎 开源 反编译 插件 ettercap wireshark burp sqlmap commix mimikatz "Cobalt strike"'},
        {0:'总结',  1:'总结 汇总  整理 大全 收集 合集  集合 杂烩 收藏 最佳实践 常见 各种 入门'},
        {0:'技巧',  1:'技巧 姿势 绕过 绕waf bypass waf'},        
        {0:'分析研究',  1:'研究 分析 浅谈  浅析 剖析 深入 探索 玩转 初探 一步步 进阶 指南 原理 思路'}, 
        {0:'干货',  1:'干货  推荐 最佳实践 史上'},               
        {0:'白盒',  1:'代码审计 审计 白盒 代码分析 静态分析'},        
        {0:'红蓝对抗',  1:'红队 蓝队 红蓝 红军 蓝军'},        
        {0:'经历',  1:'一次 记一次'},        
        {0: '命令注入', 1:'命令注入 命令执行 "command inject" "code inject"'},
        {0:'反序列化',  1:'反序列化 ysoserial fastjson'},        
        {0:'XSS',  1:'XSS 跨站脚本'},
        {0:'XXE',  1:'XXE xml注入'},
        {0:'SSRF',  1:'SSRF'},
        {0:'CSRF',  1:'CSRF 请求伪造'},
        {0:'sql注入',  1:'sql注入 sqli'},
        {0:'模板注入',  1:'模板注入 SSTI'},
        {0:'二进制',  1:'二进制 逆向 溢出 内存泄漏 地址随机化 内核 越界'},
        {0:'逃逸',  1:'逃逸 沙箱'},
        {0:'fuzz',  1:'fuzz 模糊测试'},
        {0:'渗透',  1:'渗透 内网 域控 内网渗透 横向移动 子域'},
        {0:'我关注的',  1:'LD_PRELOAD ptrace hook javaagent byteman 字节码 插桩 codeql 条件竞争 污点分析 请求走私 调试 动态分析 RASP'},
        {0:'未分类',  1:'零信任 新型 att&ck 注入 灰盒 安全加固 实战 黑盒 本地提权 目录穿越 跨目录 逻辑漏洞 \
         CTF 越权 符号执行 越权 任意文件读，任意文件写 远程控制 应急响应 入侵检测 蜜罐 混淆 \
         爬虫 靶场 危险函数 反调试 中间人 OAuth JWT 弱口令 弱密码 点击劫持 LDAP OGNL注入 漏洞'},        ]
    return jsonify(groups)    


@app.route("/api/articles")
def get_articles():
    startDateStr = request.args.get("startDate")
    endDateStr = request.args.get("endDate")
    keywordsStr = request.args.get("keywords")
    keywords = split(keywordsStr.strip())
    #print(keywordsStr)
    mapKeyword2Article = OrderedDict()
    if len(keywords):
        for keyword in keywords:
            mapKeyword2Article[keyword] = []
        mapKeyword2Article['未匹配到关键字的文章'] = []
    startDate = datetime.strptime(startDateStr, "%Y%m%d")
    endDate = datetime.strptime(endDateStr, "%Y%m%d")+timedelta(days=1)
    article_views = []
    article_views_filter_keywords = []
    for a, p, count in db.session.query(Article, Page, func.count(Article.title)) \
        .filter(Article.page_id == Page.id) \
        .filter(Article.create_at >= startDate) \
        .filter(Article.create_at < endDate) \
        .filter(Article.is_delete == False) \
        .group_by(Article.title) \
        .order_by(Article.create_at.desc()) \
            .all():
                  
        if len(mapKeyword2Article):
            foundKeyWord = False
            for keyword in mapKeyword2Article.keys():
                if keyword == '未匹配到关键字的文章':
                    continue
                if keyword.upper() in a.title.upper():
                    if not foundKeyWord:                  
                        article_views_filter_keywords.append(a.id)
                        foundKeyWord = True                                      
                    mapKeyword2Article[keyword].append(a.id)
            if not foundKeyWord:
                mapKeyword2Article['未匹配到关键字的文章'].append(a.id)
        else:
            article_views_filter_keywords.append(a.id)
    print('====ok')  
    all_num = len(article_views_filter_keywords)
    listKeyword2Article = []
    #print(mapKeyword2Article)
    for key, value in mapKeyword2Article.items():
        if len(value) > 0:
            listKeyword2Article.append({'name': key, 'ids':value})
    return jsonify({'total':all_num, 'articles': article_views_filter_keywords, 'keywords': listKeyword2Article})

@app.route("/api/articlesbyids")
def get_articlesbyids():
    idsStr = request.args.get("ids")
    ids = idsStr.strip().split(',')
    print(ids)
    articles_view = []
    for a, p, in db.session.query(Article, Page) \
        .filter(Article.page_id == Page.id) \
        .filter(Article.id.in_(ids)) \
        .order_by(Article.create_at.desc()) \
            .all():       
        articles_view.append({'id':a.id,
        'title':a.title, 
        'url':a.url,
        "create_at": a.create_at.strftime('%Y-%m-%d %H:%M'),
        'site_name': p.name})
    return jsonify(articles_view)

@app.route("/api/articles_today")
def get_articles_today():
    articles_view = []
    for a, p, in db.session.query(Article, Page) \
        .filter(Article.page_id == Page.id) \
        .filter(Article.create_at >= datetime.now().strftime('%Y-%m-%d')) \
        .filter(Article.create_at < (datetime.now()+timedelta(days=1) ).strftime('%Y-%m-%d')) \
        .order_by(Article.create_at.desc()) \
            .all():       
        articles_view.append({'id':a.id,
        'title':a.title, 
        'url':a.url,
        "create_at": a.create_at.strftime('%Y-%m-%d %H:%M'),
        'site_name': p.name})
    filename = '/tmp/'+datetime.now().strftime('%Y-%m-%d')+'_articles.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(articles_view, f)                  
    return json.dumps(articles_view)  


@app.route("/getjson")
def getjson():
    return jsonify({"name": "123"})


@app.route("/article/<id>")
def getAritcle(id):
    article = Article.query.get(int(id))
    return article.text


headers = {
    'Accept-Language': "zh-CN,zh;q=0.8",
    'Accept-Encoding': "gzip, deflate",
    'Content-Type': "application/x-www-form-urlencoded",
    'Connection': "keep-alive",
    'Referer': "http://localhost/login",
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.86 Safari/537.36"
}


@app.route("/test")
def mytest():
    url = request.args.get("url")
    return '<pre>'+extractMainBody(url)+'</pre>'


"""
@app.route("/test2")
def mytest2():
  id = request.args.get("id")
  article = Article.query.get(int(id))
  keyword_processor = KeywordProcessor()
  with open('word.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()
  for line in lines:
    for word in line.split(' '):
      if word.strip():
        keyword_processor.add_keyword(word)
  keywords_found = keyword_processor.extract_keywords(article.text, False)
  return ' '.join(Counter(keywords_found).keys())
"""


@app.route("/test3")
def mytest3():
    articles = Article.query.order_by(Article.create_at.desc()).all()
    with open('title_keywords.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    keywords = []
    article2keyword = {}
    keyword2article = {}
    keyword2article['其他'] = []
    for article in articles:
        found = False
        for line in lines:
            for word in line.split(' '):
                if word.strip():
                    if article.title.upper().find(word.upper()) != -1:
                        found = True
                        if word in keyword2article.keys():
                            keyword2article[word].append(Article_View(
                                id=article.id, title=article.title))
                        else:
                            keyword2article[word] = [Article_View(
                                id=article.id, title=article.title)]
        if not found:
            keyword2article['其他'].append(Article_View(
                id=article.id, title=article.title))
    return render_template('keywords_index.html', keyword2article=keyword2article)



@app.route("/test_getsites")
def getall_real_site():
    realurls = []
    articles = Article.query.filter(
        Article.url.like("%https://sec.today%")).all()
    for article in articles:
        req = requests.get(article.url, headers=headers, verify=False)
        realUrl = req.url
        realurls.append(urlparse(realUrl).hostname)
    #print(dict(Counter(realurls)))
    return dict(Counter(realurls))


def extractMainBody(url):
    req = requests.get(url, headers=headers, verify=False)
    realUrl = req.url
    body_xpath_str = None
    body_xpaths = yaml.load_all(
        open('extractBody.yaml', encoding='utf-8'), Loader=yaml.FullLoader)
    for body_xpath in body_xpaths:
        if body_xpath['url'] in realUrl:
            body_xpath_str = body_xpath['body']
            break
    if body_xpath_str is None:
        return ''
    selector = Selector(req.text)
    #print(req.text)
    body = selector.xpath(body_xpath_str)
    if body.get() is None:
        return ''
    #print(body)
    h = html2text.HTML2Text()
    h.ignore_links = True
    return h.handle(body.get())


def handle_site(site2):
    global doonsec_page
    #doonsec_page = None
    page = None
    page_text = None
    if db.session.query(Site).filter_by(url=site2.url).scalar() is None:
        # print(site2.url)
        page = Page(url=site2.url, name=site2.name)
        site = Site(url=site2.url)
        site.pages = [page]
        db.session.add(page)
        db.session.add(site)
        db.session.commit()
    if site2.url.find('https://i.hacking8.com/nodes/doonsec/') != -1:
        if doonsec_page is None:
            print(site2.url)
            page_text = requests.get(
                site2.url, headers=headers, verify=False, timeout=20).text
            doonsec_page = page_text
        else:
            page_text = doonsec_page
    else:
        page_text = requests.get(site2.url, headers=headers, verify=False, timeout=20).text
    # print(page_text)
    selector = Selector(page_text)
    articles = selector.xpath(site2.item)
    #article_lst = []
    ext = ''
    for index, article in enumerate(articles):
        if article.xpath(site2.item_title).get() is None:
            continue
        title = article.xpath(site2.item_title).get().strip()
        url = article.xpath(site2.item_url).get()
        if site2.item_date:
            date = article.xpath(site2.item_date).get()
            if date:
                date = date.strip()
        else:
            date = ''

        if '刚刚' in date:
            date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        elif '分钟' in date:
            minute = int(re.compile(r'\d*').findall(date)[0])
            date =(datetime.now() - timedelta(minutes=minute)).strftime('%Y-%m-%d %H:%M:%S')
        elif '小时' in date:
            hour = int(re.compile(r'\d*').findall(date)[0])
            date =(datetime.now() - timedelta(hours=hour)).strftime('%Y-%m-%d %H:%M:%S')
        elif '天' in date:
            day = int(re.compile(r'\d*').findall(date)[0])
            date =(datetime.now() - timedelta(days=day) ).strftime('%Y-%m-%d %H:%M:%S')  

        if site2.item_ext:
            if 'item_ext.catalog' in site2.item_ext.keys():
                catalog = article.xpath(site2.item_ext['item_ext.catalog']).get()
                if catalog:
                    catalog = catalog.strip()
                ext = json.dumps({'catalog': catalog})
                #print(ext)
            if 'item_ext.tags' in site2.item_ext.keys():
                tags = article.xpath(site2.item_ext['item_ext.tags']).get()
                if tags:
                    tags = tags.strip()
                ext = json.dumps({'tags': catalog})                 
                #print(ext)                  
        #print(url)
        if db.session.query(Article).filter_by(url=url, title=title).scalar() is not None:
            continue
        # print(title.encode('utf-8'))
        page = db.session.query(Page).filter_by(url=site2.url).first()
        # print(page.url)
        article2 = Article(title=title, url=url, date=date, ext=ext)
        article2.category_id = 1
        article2.page_id = page.id
        #html = requests.get(url, headers=headers, verify=False).text
        #extractor = GeneralNewsExtractor()
        #result = extractor.extract(html)
        #article2.text = extractMainBody(url)
        db.session.add(article2)
        # article_lst.append(article2)
    #page.articles = article_lst
    db.session.commit()
    return "ok"

def import_csv_db(file):
    date_format = {
        'www.4hou.com': '%Y-%m-%d %H:%M:%S',     
        'www.secpulse.com': '%Y-%m-%d %H:%M:%S',                       
        'wiki.ioin.in': '%Y-%m-%d',
        'paper.seebug.org': '%Y-%m-%d',
        'xz.aliyun.com': '%Y-%m-%d',
        'sec-wiki.com': '%Y-%m-%d',
    }
    print('import {}'.format(file))
    csvFile = open(file, "r")
    reader = csv.reader(csvFile)
    for item in reader:
        title = item[0]
        date = item[1]
        ext = item[2]
        url = item[3]
        site_url = urlparse(url).hostname
        if db.session.query(Article).filter_by(url=url, title=title).scalar() is not None:
            continue
        
        page_id=-1
        create_at = None
        if 'secwiki' in csvFile.name:
            page_id = 9
            create_at = datetime.strptime(date, '%Y-%m-%d')    
        else:
            page = Page.query.filter(Page.url.like('%%%s%%'%site_url)).first()
            if page:
                page_id = page.id
            try:
                create_at = datetime.strptime(date, date_format[site_url])
            except  ValueError:
                create_at = datetime.now()       

        article2 = Article(title=item[0], url=url, date=date, ext=ext, create_at = create_at)
        article2.category_id = 1
        article2.page_id = page_id
        db.session.add(article2)  
    csvFile.close()
    db.session.commit()

def data2db(items):
    for item in items:
        article2 = Article(title=item['title'], url=item['url'], date=item['date'], ext=item['ext'], create_at = item['create_at'])    
        article2.category_id = 1    
        article2.page_id = item['page_id']
        db.session.add(article2)  
    db.session.commit()        
        
def import_json_db(file):    
    mydata = json.load(open(file, 'r'))
    items = []
    if 'freebuf' in file:
        for item in mydata['data']['list']:
            title = item['post_title']
            url = 'https://www.freebuf.com'+item['url']
            date =  item['post_date']
            ext = item['category']
            page_id = 4
            date_format = '%Y-%m-%d %H:%M:%S'
            create_at = datetime.strptime(date, date_format)
            items.append({'title':title, 'url':url, 'date':create_at, 'ext':ext, 'page_id':page_id, 'create_at':create_at})
    elif 'anquanke' in file:
        for item in mydata['data']:
            title = item['title']
            url = 'https://www.anquanke.com/post/id/'+str(item['id'])
            date =  item['date']
            ext = item['category_name']
            page_id = 5
            date_format = '%Y-%m-%d %H:%M:%S'
            create_at = datetime.strptime(date, date_format)
            items.append({'title':title, 'url':url, 'date':create_at, 'ext':ext, 'page_id':page_id, 'create_at':create_at})                  
    #print(items)        
    data2db(items)
@app.route("/import_db", methods=['GET'])
def import_db():
    filepaths = [
        'data/csv/4hou.csv',
        'data/csv/secnews.csv',
        'data/csv/seebug.csv',
        'data/csv/xz.csv',
         ]
    for filepath in filepaths:
        import_csv_db(filepath)

    #for file in glob.glob('./data/*/*/*.json'):
    #    import_json_db(file)
    return 'ok'

@app.route("/g_article", methods=['GET'])
def g_article():
    global collectTime
    collectTime = datetime.now
    global doonsec_page
    doonsec_page = None
    sites = yaml.load_all(
        open('my.yaml', encoding='utf-8'), Loader=yaml.FullLoader)
    for site in sites:
        item_ext = {}
        date = None
        if 'item_date' in site:
            date = site['item_date']
        if 'item_ext.tags'  in site:
            item_ext['item_ext.tags'] = site['item_ext.tags']
        if 'item_ext.catalog'  in site:
            item_ext['item_ext.catalog'] = site['item_ext.catalog']     
            #print(item_ext)  
        aSite = Site2(site['name'], site['url'], site['item'],
                      site['item_title'], site['item_url'], date, item_ext)
        try:
            #print("%s"%site['url'])
            handle_site(aSite)
        except Exception as e:
            print("e:url:%s %s"%(site['url'],e))
    return "ok"


if __name__ == "__main__":
    g_article()
    print(get_articles_today())
