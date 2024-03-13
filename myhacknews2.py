#!/usr/bin/python
# -*- coding: UTF-8 -*-

from datetime import datetime, timedelta,date
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
from translate import translate_en2zh

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
    def __init__(self, name, url, item, item_title, item_url, item_hacknewslink, item_comments, item_points, item_fromsiteurl, item_fromsitename, item_date, item_ext={}):
        self.name = name
        self.url = url
        self.item = item
        self.item_title = item_title
        self.item_url = item_url
        self.item_hacknewslink = item_hacknewslink
        self.item_comments = item_comments
        self.item_points = item_points
        self.item_fromsiteurl = item_fromsiteurl
        self.item_fromsitename = item_fromsitename
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
    title_zh = db.Column(db.String(256))
    url = db.Column(db.String(512), nullable=False, primary_key=False)
    create_at = db.Column(db.DateTime, default=collectTime)
    date = db.Column(db.String(128))
    points = db.Column(db.Integer)
    comments = db.Column(db.Integer)
    hacknewsid = db.Column(db.Integer, index = True)
    fromsiteurl = db.Column(db.String(512))
    fromsitename = db.Column(db.String(128))
    summary = db.Column(db.String(512))
    text = db.Column(db.String(5120))
    author = db.Column(db.String(128))
    language = db.Column(db.String(16), default="EN", nullable=False)
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


@app.route("/init")
def init_db():
    db.drop_all()
    db.create_all()
    return 'ok'


@app.route('/')
def root():
    return app.send_static_file('index.html')

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
        {0:'我关注的',  1:'SSTI XSS XXE SSRF CSRF SQLI "command inject" ysoserial github codeql RASP javascript java python php vscode powershell LD_PRELOAD ptrace hook javaagent byteman powerful frida ettercap wireshark burp sqlmap commix mimikatz Cobaltstrike "Cobalt strike"'},
        ]
    return jsonify(groups)


@app.route("/api/articles")
def get_articles():
    startDateStr = request.args.get("startDate")
    endDateStr = request.args.get("endDate")
    keywordsStr = request.args.get("keywords")
    keywords = split(keywordsStr.strip())
    print(keywordsStr)
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
        'title_zh':a.title_zh,
        'hacknewslink': '',
        'url':a.url,
        "create_at": a.create_at.strftime('%Y-%m-%d %H:%M'),
        'site_name': p.name})
    return jsonify(articles_view)



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


def filter_article(title, url, fromsiteurl):
    keywords = ['ptrace','LD_PRELOAD','hook','linux','codeql','html','ssrf','csrf','sql','Asynchronous','windows',\
                'data science','github', 'Groovy','javascript','Cyber Security', \
                'react','sqlite','library','debug','jquery','unix', \
                'webpack','tool','virtualbox','virtual box','burpsuite','chrome',\
                'firefox','lightweight','database','Develop','Code Execute','Remote Command', \
                'Kubernetes','k8s',' extension','ssti','command inject','code inject','ddos',\
                'elasticsearch','kibana','openssl','cve-','javaagent','plugin','vs code',\
                'json','python', 'fuzz','open source', 'opensource','open-source','apache', 'java', 'golang',\
                'c++', 'unix',  'simple'\
                'springboot','nginx','docker','nodejs','Vulnerab','css' , 'Decompile', 'blackhat', \
                'Pentest' , 'mysql', 'mongodb', 'bypass', 'Clickjacking','CRLF', \
                'Deserialization', 'http' ,'Race Condition','node.js', 'android',\
                'xpath','burp suite', 'redos','nosql', 'deobfuscator', 'graphql', \
                'security', 'query', 'search', 'checklist', \
                '.js sdk', 'easy', 'collection',  'hacker', \
                'open source', 'performance', 'awesome', 'cybersecurity', \
                'tain analysis', 'code analysis', 'IAST', 'RASP', 'osquery', 'huawei', 'machine learning',\
                'GraphQL', 'terminal', 'dashboard','ftp', 'powerful','recommend', 'lightweight', 'automat', 'roadmap', 'flexible', 'parallel',\
                'instrument','portable', 'command-line', 'command line', 'log4','gpt', 'Large language model', 'llama', 'chatglm','openai'
               ]
    for keyword in keywords:
        if keyword.upper() in title.upper():
            return True
    if 'github' in url:
        return True
    if re.search(r'\bweb\b|\bapi\b|\bjdk\b|\bdll\b|\bvue\b|\basync\b|\bDistributed\b|\bssh\b|\bAPIs\b|\.js\bi|\blearn\b|\bDjango\b|\bOAuth\b|\bxxe\b|\bxss\b|\bcli\b|\bfast\b|\btui\b|\bllm\b|\bsora\b|\bgrok\b', title, re.I):
        return True
    if re.search(r'\bRust\b|\bAI\b', title):
        return True

   # if 'github' in fromsiteurl:
   #     return True

    return False
def send2wechat(news_title, news_url):
    token = 'b2265784519849ef82805359f8cdaff5'
    title= news_title
    content = '<a href="{}">{}</a>'.format(news_url, news_title)
    url = 'http://www.pushplus.plus/send?token='+token+'&title='+title+'&content='+content
    try:
         requests.get(url)
    except:
        print('send2wechat failed')
        pass
    print('send2wechat '+ news_url)


def handle_site(site2):
    print(site2)
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
    newurl = 'https://hacker-news.firebaseio.com/v0/newstories.json'
    newsIds = requests.get(newurl, headers=headers, verify=False, timeout=20).json()
    # print(newsIds)
    for newsId in newsIds:
        print(newsId)
        if db.session.query(Article).filter_by(hacknewsid=newsId).first() is not None:
            break
        itemurl = 'https://hacker-news.firebaseio.com/v0/item/%d.json'%newsId
        item = requests.get(itemurl, headers=headers, verify=False, timeout=20).json()
        if not item:
            print(itemurl)
            continue
        if "title" not in item:
            continue
        if 'url' not in item:
            continue
        print(item["title"])
        if not filter_article(item["title"],item["url"],''):
            continue
        if 'gpt' in item["title"].lower() or 'llama' in item["title"].lower() or 'large language model' in item["title"].lower() \
                or 'machine learning' in item["title"].lower() or re.search(r'\bLLM\b|\bAI\b|openai', item["title"]):
            pass
            #send2wechat(item["title"], item["url"])
        article2 = Article(title=item["title"], url=item["url"], hacknewsid=newsId, comments=0, points=0,\
         fromsiteurl=item["url"],fromsitename=item["url"], date=date.fromtimestamp(item["time"]), ext='')
        article2.category_id = 1
        article2.page_id = 1
        article2.title_zh = '' #translate_en2zh(item['title'])
        db.session.add(article2)
    db.session.commit()
    return "ok"


def data2db(items):
    for item in items:
        article2 = Article(title=item['title'], url=item['url'], date=item['date'], ext=item['ext'], create_at = item['create_at'])
        article2.category_id = 1
        article2.page_id = item['page_id']
        db.session.add(article2)
    db.session.commit()


@app.route("/g_article", methods=['GET'])
def g_article():
    global collectTime
    collectTime = datetime.now
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
            print(item_ext)
        aSite = Site2(site['name'], site['url'], site['item'],
                      site['item_title'], site['item_url'],  site['item_hacknewslink'],site['item_comments'], site['item_points'],  site['item_fromsiteurl'], site['item_fromsitename'], date, item_ext)
        handle_site(aSite)
    return "ok"


@app.route("/api/articles_today")
def get_articles_today():
    articles_view = []
    for a, p, in db.session.query(Article, Page) \
        .filter(Article.page_id == Page.id) \
        .filter(Article.create_at >= datetime.now().strftime('%Y-%m-%d')) \
        .filter(Article.create_at < (datetime.now()+timedelta(days=1) ).strftime('%Y-%m-%d')) \
        .order_by(Article.hacknewsid.desc()) \
        .all():
        articles_view.append({'id':a.id,'hacknewsid':a.hacknewsid,
        'title':a.title,
        'title_zh':a.title_zh,
        'url':a.url,
        "create_at": a.create_at.strftime('%Y-%m-%d %H:%M'),
        'site_name': p.name})
    filename = '/tmp/'+datetime.now().strftime('%Y-%m-%d')+'_articles.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(articles_view, f)
    return json.dumps(articles_view)


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5002, debug=True)  
    #init_db()
    g_article()
    print(get_articles_today())
