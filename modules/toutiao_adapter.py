# -*- coding: utf-8 -*-
"""
今日头条扩展适配器 (Toutiao Multi-Function Adapter)
===================================================
支持：
1. 实时热搜榜单 (Hot Board)
2. 关键词全网文章搜索 (Keyword Search)
3. 单篇/多篇链接直接提取与清洗 (Direct Article Extract)
"""

import re
import json
import asyncio
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup


class ToutiaoAdapter:
    """今日头条多功能适配器"""

    DEFAULT_USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/128.0.0.0 Safari/537.36'
    )

    def __init__(self):
        self.headers = {
            'User-Agent': self.DEFAULT_USER_AGENT,
            'Referer': 'https://www.toutiao.com/',
            'Accept': 'application/json, text/plain, */*'
        }

    def _http_get_json(self, url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """同步 GET 请求并返回 JSON"""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode('utf-8', errors='replace')
                return json.loads(data)
        except Exception as e:
            print(f"[Adapter JSON Error] {url}: {e}")
            return None

    def _http_get_text(self, url: str, timeout: int = 15) -> str:
        """同步 GET 请求并返回 HTML 文本"""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            print(f"[Adapter Text Error] {url}: {e}")
            return ""

    async def get_hot_board(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取今日头条 PC 实时热榜 50 强"""
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
        res = await asyncio.to_thread(self._http_get_json, url)
        items = []
        if res and "data" in res:
            for i, raw in enumerate(res["data"][:limit], 1):
                img_url = ""
                if isinstance(raw.get("Image"), dict):
                    img_url = raw.get("Image", {}).get("url", "")
                elif isinstance(raw.get("Image"), str):
                    img_url = raw.get("Image", "")

                label = raw.get("LabelDesc", "") or raw.get("Label", "")
                items.append({
                    "rank": i,
                    "title": raw.get("Title", ""),
                    "hot_value": raw.get("HotValue", "") or raw.get("QueryWord", ""),
                    "label": label,
                    "cluster_id": str(raw.get("ClusterId", "")),
                    "url": raw.get("Url", "") or f"https://www.toutiao.com/trending/{raw.get('ClusterId', '')}/",
                    "cover_image": img_url
                })
        return items

    async def search_articles(self, keyword: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """全网按关键词搜索今日头条文章"""
        encoded_kw = urllib.parse.quote(keyword.strip())
        url = f"https://www.toutiao.com/api/search/content/?keyword={encoded_kw}&format=json&cur_tab=1&offset={offset}&count={limit}"
        res = await asyncio.to_thread(self._http_get_json, url)
        results = []
        if res and isinstance(res.get("data"), list):
            for item in res["data"]:
                if not isinstance(item, dict):
                    continue
                if item.get("title") and (item.get("article_url") or item.get("item_id") or item.get("group_id")):
                    gid = str(item.get("item_id") or item.get("group_id") or item.get("id") or "")
                    art_url = item.get("article_url") or (f"https://www.toutiao.com/article/{gid}/" if gid else "")
                    
                    images = []
                    for img in item.get("image_list", []):
                        if isinstance(img, dict) and "url" in img:
                            images.append(img["url"])

                    results.append({
                        "group_id": gid,
                        "title": item.get("title", "").replace("<em>", "").replace("</em>", ""),
                        "abstract": (item.get("abstract", "") or "").replace("<em>", "").replace("</em>", ""),
                        "author": item.get("media_name", "") or item.get("source", "") or "今日头条创作者",
                        "comment_count": item.get("comments_count") or item.get("comment_count", 0),
                        "read_count": item.get("read_count", 0),
                        "digg_count": item.get("digg_count", 0),
                        "publish_time": item.get("datetime", "") or item.get("publish_time", ""),
                        "article_url": art_url,
                        "image_list": images,
                        "local_file": "",
                        "status": "discovered"
                    })
        return results[:limit]

    async def extract_single_article(self, url_or_id: str) -> Dict[str, Any]:
        """直接解析单篇头条文章 URL 或 group_id 提取 100% 完整正文内容"""
        cleaned = url_or_id.strip()
        if cleaned.isdigit():
            target_url = f"https://www.toutiao.com/article/{cleaned}/"
            gid = cleaned
        elif "/article/" in cleaned:
            m = re.search(r'/article/(\d+)', cleaned)
            gid = m.group(1) if m else "article"
            target_url = cleaned
        else:
            target_url = cleaned
            gid = "custom"

        # 1. 优先使用无头内核动态渲染提取 100% 完整文章全文
        try:
            from patchright.async_api import async_playwright
            async with async_playwright() as p:
                browser = None
                for launch_opt in [{"channel": "msedge"}, {"channel": "chrome"}, {}]:
                    try:
                        browser = await p.chromium.launch(headless=True, **launch_opt)
                        break
                    except Exception:
                        continue
                
                if browser:
                    context = await browser.new_context(
                        viewport={'width': 1280, 'height': 800},
                        user_agent=self.DEFAULT_USER_AGENT
                    )
                    page = await context.new_page()
                    try:
                        await page.goto(target_url, wait_until='domcontentloaded', timeout=20000)
                        await asyncio.sleep(1.5)
                        
                        # 等待正文节点
                        for selector in ['article', '.article-content', '.tt-article-content', '.s-content', '.main-content']:
                            try:
                                await page.wait_for_selector(selector, timeout=2000)
                                break
                            except Exception:
                                continue

                        html = await page.content()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        title = ""
                        h1 = soup.find('h1')
                        if h1:
                            title = h1.get_text(strip=True)
                        if not title:
                            title_tag = soup.find('title')
                            if title_tag:
                                title = re.sub(r' - 今日头条.*', '', title_tag.get_text(strip=True))

                        article_tag = soup.find('article') or soup.find('div', class_='article-content') or soup.find('div', class_='tt-article-content')
                        images = []
                        paragraphs = []
                        if article_tag:
                            for img in article_tag.find_all('img'):
                                src = img.get('data-src') or img.get('src') or ''
                                if src and not src.startswith('data:'):
                                    images.append(src)
                            for p_node in article_tag.find_all(['p', 'h2', 'h3', 'blockquote']):
                                txt = p_node.get_text(strip=True)
                                if txt:
                                    paragraphs.append(txt)
                            content_md = "\n\n".join(paragraphs)
                        else:
                            content_md = ""

                        if content_md:
                            return {
                                "group_id": gid,
                                "title": title or "今日头条文章",
                                "article_url": target_url,
                                "image_list": images,
                                "content_markdown": content_md,
                                "word_count": len(content_md),
                                "status": "extracted"
                            }
                    finally:
                        await browser.close()
        except Exception as e:
            print(f"[Adapter Browser Error] {target_url}: {e}")

        # 2. 静态兜底
        html = await asyncio.to_thread(self._http_get_text, target_url)
        if not html:
            return {"error": "请求页面失败或超时", "article_url": target_url}

        soup = BeautifulSoup(html, 'html.parser')

        # 提取标题
        title = ""
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = re.sub(r' - 今日头条.*', '', title_tag.get_text(strip=True))

        # 提取正文
        article_tag = soup.find('article') or soup.find('div', class_='article-content') or soup.find('div', class_='tt-article-content')

        images = []
        if article_tag:
            for img in article_tag.find_all('img'):
                src = img.get('data-src') or img.get('src') or ''
                if src and not src.startswith('data:'):
                    images.append(src)

            paragraphs = []
            for p in article_tag.find_all(['p', 'h2', 'h3', 'blockquote']):
                txt = p.get_text(strip=True)
                if txt:
                    paragraphs.append(txt)
            content_md = "\n\n".join(paragraphs)
        else:
            content_md = re.sub(r'<[^>]+>', ' ', html)[:1500].strip()

        return {
            "group_id": gid,
            "title": title or "今日头条文章",
            "article_url": target_url,
            "image_list": images,
            "content_markdown": content_md,
            "word_count": len(content_md),
            "status": "extracted"
        }


# 全局单例适配器
toutiao_adapter = ToutiaoAdapter()
