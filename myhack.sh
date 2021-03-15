cd /root/caiyun/myhack_data
curl -o `date "+%Y-%m-%d"`_articles.json http://127.0.0.1:5002/api/articles_today
git add * 
git commit -m "gh-pages"
git push origin gh-pages 
cd -
