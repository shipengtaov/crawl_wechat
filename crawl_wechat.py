from os import path
import json
import re
import random
import time
from urllib.parse import urljoin
import csv
from argparse import ArgumentParser
import requests
from loguru import logger


base_url = 'https://mp.weixin.qq.com'
current_dir = path.dirname(path.abspath(__file__))
raw_cookie_file = path.join(current_dir, 'raw_cookie.txt')
write_file_pattern = '{name}_articles.csv'


def request_gzh_info(headers, cookies, token, search_text):
    search_url = urljoin(base_url, '/cgi-bin/searchbiz')
    params = {
        'action': 'search_biz',
        'token': token,
        'lang': 'zh_CN',
        'f': 'json',
        'ajax': 1,
        'random': random.random(),
        'query': search_text,
        'begin': 0,
        'count': 5,
    }
    res = requests.get(search_url, headers=headers, cookies=cookies, params=params)
    # 返回第一个
    data = res.json()
    if not data.get('list'):
        logger.debug('未搜到公众号信息')
        raise SystemExit
    return {
        'name': data['list'][0]['nickname'],
        'id': data['list'][0]['alias'],
        'fakeid': data['list'][0]['fakeid'],
    }


def request_articles(headers, cookies, token, gzh_info, max_count=None):
    list_url = urljoin(base_url, '/cgi-bin/appmsg')
    default_count = 5
    begin = 0
    current_count = 0
    total_num = None
    params = {
        'token': token,
        'lang': 'zh_CN',
        'f': 'json',
        'ajax': 1,
        'random': random.random(),
        'action': 'list_ex',
        'begin': begin,
        'count': default_count,
        'query': '',
        'fakeid': gzh_info['fakeid'],
        'type': 9,
    }
    should_break = False
    write_file = write_file_pattern.format(name=gzh_info['name'])
    with open(write_file, 'w') as f:
        writer = csv.DictWriter(f, ['title', 'link'])
        writer.writeheader()
        while True:
            res = requests.get(list_url, headers=headers, cookies=cookies, params=params)
            if not res.ok:
                logger.error('请求列表页出错')
                raise Exception
            data = res.json()
            total_num = data['app_msg_cnt']
            for article in data['app_msg_list']:
                logger.debug(article['title'])
                writer.writerow({
                    'title': article['title'],
                    'link': article['link'],
                })
                current_count += 1
                if max_count is not None and current_count >= max_count:
                    should_break = True
                if current_count >= total_num:
                    should_break = True
                if should_break:
                    break
            params['begin'] += default_count
            if should_break:
                break
            time.sleep(1)


def main():
    parser = ArgumentParser('微信抓取')
    parser.add_argument('-t', '--search-text', help='要抓取的公众号(名称或微信号)')
    parser.add_argument('-f', '--fakeid', help='fakeid')
    parser.add_argument('-c', '--max-count', type=int, help='最多抓取多少文章[可选]')
    args = parser.parse_args()

    if not args.search_text and not args.fakeid:
        # ipdb.set_trace()
        parser.error('-t, -f 必须指定其一')
    gzh_info = None
    if args.fakeid:
        gzh_info = {
            'name': args.fakeid,
            'id': args.fakeid,
            'fakeid': args.fakeid,
        }

    headers = {
        "HOST": "mp.weixin.qq.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0"
    }

    with open(raw_cookie_file, 'rt') as f:
        cookie_str = f.read()
    cookies = dict()
    for k_and_v in cookie_str.split(';'):
        cookie_name, cookie_value = k_and_v.strip().split('=', 1)
        cookies[cookie_name] = cookie_value

    logger.debug('正在请求token')
    res = requests.get(base_url, cookies=cookies)
    token = re.findall(r'token=(\d+)', res.url)[0]

    # 请求fakeid
    if not gzh_info:
        logger.debug('正在请求公众号信息')
        gzh_info = request_gzh_info(headers, cookies, token, args.search_text)

    logger.debug('正在请求公众号文章列表：{}({})'.format(gzh_info['name'], gzh_info['id']))
    request_articles(headers, cookies, token, gzh_info, max_count=args.max_count)

if __name__ == '__main__':
    main()
