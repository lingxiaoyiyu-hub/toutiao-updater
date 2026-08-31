# -*- coding: utf-8 -*-
"""
今日头条作者文章爬虫启动入口
=============================
使用方法：
    # 爬取目标作者全部文章（默认包含正文与排版）
    python run.py

    # 爬取前 20 篇文章进行测试
    python run.py --max-articles 20

    # 同时下载配图到本地
    python run.py --download-images

    # 仅爬取文章列表和数据统计（不抓取正文）
    python run.py --no-content

    # 自定义输出目录
    python run.py --output-dir ./my_toutiao_articles
"""

import sys

# 解决 Windows 控制台编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import argparse
import asyncio
from scraper import ToutiaoSpider

DEFAULT_URL = "https://www.toutiao.com/c/user/token/CieeIhGvEaO14h0xyTxCpq78JHrrNR2OEkUvJYqdBOxohBDqG6qF2v4aSQo8AAAAAAAAAAAAAFDR3HgWwBEtvZ4QmzwRtjeMOkuXuqoaRehQKTlqBJQnsFi6GLVWLgk46_DVW3yDsT1oEJCwmg4Yw8WD6gQiAQOrgOkL/?tab=article"

def parse_args():
    parser = argparse.ArgumentParser(
        description="今日头条作者文章批量爬虫工具 (Toutiao Author Article Scraper)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                                     # 抓取默认作者的所有文章
  python run.py --max-articles 10                  # 仅抓取最新 10 篇文章
  python run.py --download-images                  # 抓取文章并下载配图到本地
  python run.py --output-dir ./toutiao_articles    # 指定输出目录
  python run.py --no-content                       # 仅导出文章列表与阅读点赞数据
        """
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default=DEFAULT_URL,
        help="头条作者主页链接 (默认: 用户提供的目标作者主页)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./toutiao_output",
        help="数据保存根目录 (默认: ./toutiao_output)"
    )
    parser.add_argument(
        "--max-articles", "-m",
        type=int,
        default=None,
        help="最大抓取文章数量 (默认全部抓取)"
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="不抓取文章详细正文，仅抓取文章列表与互动数据"
    )
    parser.add_argument(
        "--download-images", "-d",
        action="store_true",
        help="是否下载文章内的配图到本地 images/ 目录"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="抓取每篇文章正文的休眠间隔秒数，防止被限流 (默认: 0.8s)"
    )
    parser.add_argument(
        "--scroll-delay",
        type=float,
        default=1.2,
        help="列表滚动加载的休眠间隔秒数 (默认: 1.2s)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="显示浏览器运行界面 (用于可视化调试)"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    spider = ToutiaoSpider(
        author_url=args.url,
        output_dir=args.output_dir,
        max_articles=args.max_articles,
        fetch_content=not args.no_content,
        download_images=args.download_images,
        headless=not args.no_headless,
        delay=args.delay,
        scroll_delay=args.scroll_delay
    )
    asyncio.run(spider.run())

if __name__ == '__main__':
    main()
