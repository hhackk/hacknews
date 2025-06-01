import requests
import sqlite3
import json
import os
from datetime import datetime, timedelta, timezone
import pytz

def fetch_cls_news():
    """获取财联社新闻数据"""
    url = "https://www.cls.cn/nodeapi/telegraphList"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None

def setup_database():
    """初始化数据库连接和表结构"""
    conn = sqlite3.connect('cls_news.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS telegraph_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cls_id INTEGER,
            title TEXT,
            ctime TEXT,  -- 存储为北京时间字符串
            content TEXT,
            UNIQUE(title, ctime) ON CONFLICT IGNORE
        )
    ''')
    conn.commit()
    return conn

def to_beijing_time(timestamp):
    """将时间戳转换为北京时间字符串"""
    if not timestamp:
        return None
    
    # UTC时间对象
    utc_time = datetime.utcfromtimestamp(timestamp)
    # 设置为UTC时区
    utc_time = utc_time.replace(tzinfo=timezone.utc)
    # 转换为北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    beijing_time = utc_time.astimezone(beijing_tz)
    
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

def process_and_save_news(conn, news_data):
    """处理并保存新闻到数据库（使用北京时间）"""
    if not news_data or 'data' not in news_data or 'roll_data' not in news_data['data']:
        print("无效的数据格式")
        return 0
    
    c = conn.cursor()
    news_list = news_data['data']['roll_data']
    count = 0
    
    for news in news_list:
        cls_id = news.get('id')
        # 如果标题为空，使用内容替代标题
        raw_title = news.get('title', '')
        content_val = news.get('content', '')
        
        # 使用内容替代空标题
        title_val = raw_title if raw_title else content_val
        
        # 使用北京时间
        ctime = to_beijing_time(news.get('ctime'))
        
        try:
            c.execute('''
                INSERT INTO telegraph_news (cls_id, title, ctime, content)
                VALUES (?, ?, ?, ?)
            ''', (cls_id, title_val, ctime, content_val))
            count += 1
        except sqlite3.Error as e:
            print(f"数据库插入错误: {e}")
    
    conn.commit()
    print(f"成功处理{count}条数据，已忽略重复项")
    return count

def clean_old_data(conn, days=10):
    """清理指定天数前的旧数据（使用北京时间）"""
    c = conn.cursor()
    
    # 计算保留数据的日期界限（北京时间）
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now_beijing = datetime.now(beijing_tz)
    cutoff_date = now_beijing - timedelta(days=days)
    cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        c.execute("DELETE FROM telegraph_news WHERE ctime < ?", (cutoff_str,))
        deleted_count = c.rowcount
        conn.commit()
        print(f"已清理{deleted_count}条{days}天前的旧数据（北京时间）")
        return deleted_count
    except sqlite3.Error as e:
        print(f"清理旧数据时出错: {e}")
        return 0

def query_daily_news(conn, target_date):
    """查询指定日期的新闻数据（使用北京时间）"""
    c = conn.cursor()
    
    # 计算日期范围（北京时间）
    start_date = target_date.strftime('%Y-%m-%d') + " 00:00:00"
    end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d') + " 00:00:00"
    
    try:
        c.execute("""
            SELECT cls_id, title, ctime, content 
            FROM telegraph_news 
            WHERE ctime >= ? AND ctime < ?
            ORDER BY ctime ASC
        """, (start_date, end_date))
        
        # 构建结果列表
        results = []
        for row in c.fetchall():
            results.append({
                'cls_id': row[0],
                'title': row[1],
                'ctime': row[2],
                'content': row[3]
            })
        return results
    except sqlite3.Error as e:
        print(f"查询数据时出错: {e}")
        return []

def export_news_to_json(conn):
    """导出当天和前一天的新闻数据到JSON文件（使用北京时间）"""
    # 获取当前北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now_beijing = datetime.now(beijing_tz)
    today = now_beijing.date()
    yesterday = today - timedelta(days=1)
    
    # 查询当天数据
    today_data = query_daily_news(conn, today)
    today_filename = f"/tmp/{today.strftime('%Y%m%d')}_cls_news.json"
    with open(today_filename, 'w', encoding='utf-8') as f:
        json.dump(today_data, f, ensure_ascii=False, indent=2)
    print(f"已导出当天数据到: {today_filename} ({len(today_data)}条记录)")
    
    # 查询前一天数据
    yesterday_data = query_daily_news(conn, yesterday)
    yesterday_filename = f"/tmp/{yesterday.strftime('%Y%m%d')}_cls_news.json"
    with open(yesterday_filename, 'w', encoding='utf-8') as f:
        json.dump(yesterday_data, f, ensure_ascii=False, indent=2)
    print(f"已导出前一天数据到: {yesterday_filename} ({len(yesterday_data)}条记录)")

def main():
    # 初始化数据库
    conn = setup_database()
    
    # 清理旧数据（保留最近10天）
    clean_old_data(conn, days=10)
    
    # 获取新数据
    news_data = fetch_cls_news()
    if news_data:
        process_and_save_news(conn, news_data)
    
    # 导出数据到JSON文件
    export_news_to_json(conn)
    
    # 关闭连接
    conn.close()
    print("数据更新和导出完成")

if __name__ == "__main__":
    main()
