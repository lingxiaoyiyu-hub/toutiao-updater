# -*- coding: utf-8 -*-
"""
今日头条文章采集大师 - FastAPI 服务端 (Server API)
===================================================
提供全功能 Web 接口：
1. 头条号作者文章批量采集 & 实时 SSE 进度流
2. 实时热搜热榜 (Hot Board 50 强)
3. 关键词全网文章搜索抓取
4. 单篇/多篇链接直接提取
5. 爆款指数与文章结构拆解 (Viral Analyzer)
6. 多格式导出 (Excel / CSV / JSON / Word .docx / Zip)
7. 离线非对称加密 VIP 会员授权验证
"""

import os
import sys
import re
import json
import asyncio
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 引入本模块与功能子模块
import activation
from activation import get_license_status, verify_license, save_license, get_display_machine_code
from task_manager import task_manager
from modules.toutiao_adapter import toutiao_adapter
from modules.viral_analyzer import viral_analyzer
from modules.docx_exporter import docx_exporter
from modules import media_writer
from modules.remote_updater import remote_updater

from modules.app_config import get_output_dir

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = get_output_dir()

STATIC_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "articles").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "images").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "docx").mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="今日头条文章采集大师 (Toutiao Scraper Studio)",
    version="2.5.0",
    description="今日头条全功能采集、实时热榜、搜索挖掘、排版导出与爆款拆解工作台"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= 数据模型 =================
class StartCrawlRequest(BaseModel):
    author_url: str = Field(..., description="头条作者主页链接")
    max_articles: Optional[int] = Field(None, description="最大采集篇数 (None 表示全部)")
    fetch_content: bool = Field(True, description="是否抓取正文与 Markdown")
    download_images: bool = Field(False, description="是否下载高清插图")
    delay: float = Field(0.6, description="抓取延时秒数")
    headless: bool = Field(True, description="是否无头模式")


class ActivateRequest(BaseModel):
    license_key: str = Field(..., description="激活码密文")


class SearchRequest(BaseModel):
    keyword: str = Field(..., description="搜索关键词")
    limit: int = Field(20, description="搜索结果数量")


class ExtractSingleRequest(BaseModel):
    url: str = Field(..., description="头条文章链接或文章ID")


class AnalyzeViralRequest(BaseModel):
    title: str = Field("", description="文章标题")
    content: str = Field("", description="文章正文 Markdown")
    reads: int = Field(0, description="阅读量")
    likes: int = Field(0, description="点赞量")
    comments: int = Field(0, description="评论量")


# ================= 静态资源挂载 =================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/images", StaticFiles(directory=OUTPUT_DIR / "images"), name="images")


@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return "<h3>前端页面未初始化，请检查 static/index.html 是否存在</h3>"
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


# ================= 权限与系统接口 =================
@app.get("/api/system/info")
async def get_system_info():
    """获取系统基础信息与会员授权状态"""
    license_info = get_license_status()
    return {
        "version": "2.5.0",
        "app_name": "今日头条文章采集大师",
        "license": license_info,
        "default_url": "https://www.toutiao.com/c/user/token/CieeIhGvEaO14h0xyTxCpq78JHrrNR2OEkUvJYqdBOxohBDqG6qF2v4aSQo8AAAAAAAAAAAAAFDR3HgWwBEtvZ4QmzwRtjeMOkuXuqoaRehQKTlqBJQnsFi6GLVWLgk46_DVW3yDsT1oEJCwmg4Yw8WD6gQiAQOrgOkL/?tab=article",
        "output_dir": str(OUTPUT_DIR.resolve())
    }


@app.post("/api/activation/activate")
async def activate_license(req: ActivateRequest):
    """提交激活码进行离线校验与激活"""
    res = verify_license(req.license_key)
    if not res["valid"]:
        raise HTTPException(status_code=400, detail=res["message"])

    saved = save_license(req.license_key)
    if not saved:
        raise HTTPException(status_code=500, detail="保存激活凭据失败")

    new_status = get_license_status()
    return {
        "success": True,
        "message": res["message"],
        "license": new_status
    }


# ================= 远程推送与客户端在线升级接口 =================
@app.get("/api/system/check-update")
async def check_system_update(url: Optional[str] = None):
    """检测云端远程新版本与公告推送"""
    return await remote_updater.check_for_updates(custom_manifest_url=url)


@app.post("/api/system/download-update")
async def download_update(req: dict):
    """启动后台流式下载更新包"""
    dl_url = req.get("download_url", "").strip()
    if not dl_url:
        raise HTTPException(status_code=400, detail="下载地址不能为空")
    started = await remote_updater.start_download(dl_url)
    if not started:
        raise HTTPException(status_code=400, detail="已有正在进行的下载任务")
    return {"success": True, "message": "已在后台启动下载..."}


@app.get("/api/system/update-progress")
async def get_update_progress():
    """获取当前更新包下载百分比进度与状态"""
    return remote_updater.download_state


@app.post("/api/system/apply-update")
async def apply_update():
    """执行更新替换并自动重启程序"""
    res = remote_updater.apply_update_and_restart()
    if not res["success"]:
        raise HTTPException(status_code=500, detail=res["message"])
    return res


@app.post("/api/system/set-update-url")
async def set_update_url(req: dict):
    """开发者设置专属的云端推送地址"""
    url = req.get("update_url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="更新地址不能为空")
    remote_updater.set_custom_update_url(url)
    return {"success": True, "message": "云端更新源配置成功！"}


# ================= 采集任务控制 (作者主页) =================
@app.post("/api/crawl/start")
async def start_crawl(req: StartCrawlRequest):
    """发起采集任务"""
    if not req.author_url.strip():
        raise HTTPException(status_code=400, detail="作者主页链接不能为空")

    license_info = get_license_status()
    max_count = req.max_articles
    download_img = req.download_images

    # 免费体验版拦截与限制
    if not license_info["is_vip"]:
        trial_max = license_info["max_articles_per_crawl"]
        if max_count is None or max_count > trial_max:
            max_count = trial_max
        if download_img:
            download_img = False

    result = await task_manager.start_task(
        author_url=req.author_url,
        max_articles=max_count,
        fetch_content=req.fetch_content,
        download_images=download_img,
        headless=req.headless,
        delay=req.delay
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@app.post("/api/crawl/stop")
async def stop_crawl():
    """中止当前采集任务"""
    result = task_manager.stop_task()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.get("/api/crawl/status")
async def get_crawl_status():
    """获取当前任务状态与指标"""
    return task_manager.get_status()


@app.get("/api/crawl/logs")
async def get_crawl_logs():
    """获取任务日志列表"""
    return {"logs": task_manager.task_logs}


@app.get("/api/crawl/articles")
async def get_articles_list():
    """获取已抓取的文章列表及概要 (自动扫描关联本地已下载的全文 Markdown)"""
    articles = task_manager.latest_articles
    if not articles:
        json_p = OUTPUT_DIR / "articles_data.json"
        if json_p.exists():
            try:
                with open(json_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    articles = data.get("articles", [])
            except Exception:
                pass

    art_dir = OUTPUT_DIR / "articles"
    if art_dir.exists() and articles:
        # 自动关联本地已存在的 .md 全文文件
        for item in articles:
            gid = str(item.get("group_id", ""))
            if gid:
                matches = list(art_dir.glob(f"*{gid}*.md"))
                if matches:
                    item["local_file"] = matches[0].name
                    item["status"] = "downloaded"

    return {"total": len(articles), "articles": articles}


@app.get("/api/crawl/article/content")
async def get_article_content(
    filename: Optional[str] = None,
    group_id: Optional[str] = None,
    url: Optional[str] = None
):
    """读取指定 Markdown 文章的完整纯正文 (支持按文件名、Group ID、模糊匹配或在线实时自动拉取)"""
    art_dir = OUTPUT_DIR / "articles"
    target_file = None

    if filename and filename.strip():
        safe_name = Path(filename).name
        f_path = art_dir / safe_name
        if f_path.exists():
            target_file = f_path

    if not target_file and group_id and group_id.strip():
        matches = list(art_dir.glob(f"*{group_id.strip()}*.md"))
        if matches:
            target_file = matches[0]

    if not target_file and filename and filename.strip():
        # 模糊查找
        matches = list(art_dir.glob(f"*{filename.strip()}*.md"))
        if matches:
            target_file = matches[0]

    if target_file and target_file.exists():
        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                raw_content = f.read()

            # 清洗 YAML frontmatter 与元信息头部，只保留纯正文全文
            clean_content = re.sub(r'^---\n[\s\S]*?\n---\n*', '', raw_content).strip()
            clean_content = re.sub(r'^#\s+.*?\n+', '', clean_content).strip()
            clean_content = re.sub(r'^>\s+\*\*发布时间\*\*[\s\S]*?\n+---\n*', '', clean_content).strip()

            return {
                "filename": target_file.name,
                "group_id": group_id,
                "content": clean_content or raw_content,
                "char_count": len(clean_content or raw_content)
            }
        except Exception:
            pass

    # 若本地未找到但提供了 URL，自动在线动态渲染提取
    if url and url.strip():
        try:
            res = await toutiao_adapter.extract_single_article(url.strip())
            if res and res.get("content_markdown"):
                return {
                    "filename": "",
                    "group_id": group_id or res.get("group_id"),
                    "content": res["content_markdown"],
                    "char_count": len(res["content_markdown"])
                }
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="本地未找到该文章内容，请检查链接或网络！")


@app.get("/api/crawl/article/online")
async def extract_online_article(url: str):
    """在线实时提取单篇头条文章的完整正文"""
    if not url.strip():
        raise HTTPException(status_code=400, detail="文章链接不能为空")
    res = await toutiao_adapter.extract_single_article(url.strip())
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res


# ================= 全网实时热搜榜单 (Hot Board) =================
@app.get("/api/hot-board")
async def get_hot_board():
    """获取今日头条官方实时热搜榜"""
    try:
        items = await toutiao_adapter.get_hot_board(limit=50)
        return {"total": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取热榜失败: {str(e)}")


# ================= 全网关键词文章搜索 =================
@app.post("/api/search")
async def search_toutiao(req: SearchRequest):
    """按关键词搜索全网头条文章"""
    if not req.keyword.strip():
        raise HTTPException(status_code=400, detail="搜索关键词不能为空")
    try:
        items = await toutiao_adapter.search_articles(req.keyword, limit=req.limit)
        return {"keyword": req.keyword, "total": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关键词搜索失败: {str(e)}")


# ================= 单篇/批量链接直接提取 =================
@app.post("/api/extract-single")
async def extract_single(req: ExtractSingleRequest):
    """直接解析单篇头条文章提取正文与配图"""
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="链接不能为空")
    try:
        data = await toutiao_adapter.extract_single_article(req.url)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析文章失败: {str(e)}")


# ================= 爆款文章拆解与分析 =================
@app.post("/api/analyze-viral")
async def analyze_viral(req: AnalyzeViralRequest):
    """拆解文章爆款特征与黄金开头"""
    score_res = viral_analyzer.calculate_score(req.reads, req.comments, req.likes)
    struct_res = viral_analyzer.analyze_content(req.title, req.content)
    return {
        "score_data": score_res,
        "structure_data": struct_res
    }


# ================= 自媒体 AI 写作与二创板块 (Media Writer) =================
@app.get("/api/media/config")
async def get_media_config():
    """获取自媒体 AI 模型设置"""
    return media_writer.load_ai_config()


@app.post("/api/media/config")
async def update_media_config(cfg: dict):
    """保存自媒体 AI 模型设置"""
    media_writer.save_ai_config(cfg)
    return {"success": True, "message": "AI 模型配置已成功保存！"}


@app.post("/api/media/generate")
async def generate_media_article(req: dict):
    """流式生成自媒体文章（支持原创写作与爆款二创）"""
    cfg = media_writer.load_ai_config()
    if not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在【AI 接口配置】中填写 API Key！")

    # 检查会员权益
    lic_status = activation.get_license_status()
    is_vip = lic_status.get("is_vip", False)

    mode = req.get("mode", "original")

    # 免费体验版限制
    if not is_vip:
        req["target_words"] = min(int(req.get("target_words", 400)), 400)
        req["humanize"] = False
        req["strong_hook"] = False
        if mode == "remix" and req.get("rewrite_mode") in ["fusion_mix", "hybrid_rewrite"]:
            req["rewrite_mode"] = "angle_shift"

    client = media_writer.MediaAIClient(cfg)

    if mode == "remix":
        messages = media_writer.build_remix_article_messages(req)
    else:
        messages = media_writer.build_original_article_messages(req)

    # 根据目标字数动态计算所需 token 上限
    target_words = int(req.get("target_words", 1200))
    limit_tokens = 800 if not is_vip else min(max(4096, target_words * 2 + 1000), 16384)

    async def stream_generator():
        try:
            async for chunk in client.chat_stream(
                messages,
                max_tokens=limit_tokens,
                temperature=req.get("temperature", 0.7)
            ):
                yield chunk

            if not is_vip:
                yield "\n\n---\n\n> 🔒 **【免费体验版试读结束】**\n> 以上为前 400 字体验试读小样。升级 **VIP 会员（7天卡 ¥9.9 / 月卡 ¥19.9 / 永久 ¥59.9）** 即可解锁 **3000~5000 字全篇长文、去AI腔调、8大黄金标题与一键导出 Word 文档**！"
        except Exception as e:
            yield f"\n\n[AI 生成异常中断: {str(e)}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")


@app.post("/api/media/topics")
async def generate_media_topics(req: dict):
    """批量生成爆款选题与黄金标题 (带 VIP 限制与离线兜底智能引擎)"""
    cfg = media_writer.load_ai_config()
    api_key = (cfg.get("api_key") or "").strip()
    
    lic_status = activation.get_license_status()
    is_vip = lic_status.get("is_vip", False)

    count = int(req.get("count", 10))
    if not is_vip:
        count = min(count, 3)

    keyword = (req.get("keyword") or "").strip() or "自媒体热点"
    platform = req.get("platform", "今日头条")

    # 1. 若配置了有效 API Key（非默认测试 key），尝试调用在线 LLM
    if api_key and api_key != "sk-test" and not api_key.startswith("sk-placeholder"):
        try:
            client = media_writer.MediaAIClient(cfg)
            messages = media_writer.build_topic_generation_messages(req)
            raw_res = await client.chat(messages, max_tokens=2048, temperature=0.7)
            
            # 清洗 markdown 语法
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw_res.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*```$', '', cleaned).strip()

            json_match = re.search(r'\[\s*\{.*\}\s*\]', cleaned, re.DOTALL)
            topics = []
            if json_match:
                try:
                    topics = json.loads(json_match.group(0))
                except Exception:
                    pass
            
            if not topics:
                try:
                    topics = json.loads(cleaned)
                except Exception:
                    pass

            # 若仍未解析出 JSON，按行匹配提取
            if not topics:
                for line in cleaned.splitlines():
                    m = re.match(r'^(?:\d+[\.、\s]+|[-*•]\s*)(.+)$', line.strip())
                    if m:
                        t_text = m.group(1).strip().strip('\"\'')
                        if len(t_text) >= 5:
                            topics.append({
                                "title": t_text,
                                "viral_score": 5,
                                "reason": "高点击潜力话题",
                                "angle": "焦点洞察"
                            })

            if topics and isinstance(topics, list):
                if not is_vip and len(topics) > 3:
                    topics = topics[:3]
                return {"success": True, "topics": topics, "is_vip": is_vip}
        except Exception as e:
            # 在线 API 失败时，无缝切换到本地离线生成算法
            pass

    # 2. 本地高转化爆款选题生成引擎 (免 API 极速秒出)
    topics = media_writer.generate_fallback_topics(keyword=keyword, platform=platform, count=count)
    if not is_vip and len(topics) > 3:
        topics = topics[:3]

    return {"success": True, "topics": topics, "is_vip": is_vip}


@app.post("/api/media/save-doc")
async def save_media_doc(req: dict):
    """保存生成的自媒体文章为本地 Markdown 与 Word (.docx) (VIP 专属)"""
    lic_status = activation.get_license_status()
    if not lic_status.get("is_vip", False):
        raise HTTPException(
            status_code=403,
            detail="【VIP 专属特权】免费体验版不支持一键导出排版 Word (.docx) 文档。请点击右上角【会员激活】升级 VIP！"
        )

    title = req.get("title", "未命名自媒体文章").strip() or "未命名自媒体文章"
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
    content = req.get("content", "")

    save_dir = OUTPUT_DIR / "ai_articles"
    save_dir.mkdir(parents=True, exist_ok=True)

    md_file = save_dir / f"{safe_title}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(content)

    # 导出 docx
    docx_file = save_dir / f"{safe_title}.docx"
    try:
        docx_exporter.export_article_to_docx({
            "title": title,
            "content_markdown": content,
            "publish_time": "",
            "read_count": 0,
            "digg_count": 0
        }, str(docx_file))
    except Exception:
        pass

    return {
        "success": True,
        "filename": md_file.name,
        "md_path": str(md_file.resolve()),
        "docx_path": str(docx_file.resolve()) if docx_file.exists() else None
    }



# ================= 实时 SSE 事件流 =================
@app.get("/api/crawl/events")
async def crawl_events(request: Request):
    """SSE 实时事件流通道"""
    event_queue = await task_manager.subscribe_events()

    async def event_generator():
        try:
            init_payload = json.dumps({
                "event": "status",
                "data": task_manager.task_state
            }, ensure_ascii=False)
            yield f"data: {init_payload}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(event_queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            task_manager.unsubscribe_events(event_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ================= 导出与本地操作 =================
@app.get("/api/export/{fmt}")
async def export_data(fmt: str, filename: Optional[str] = None):
    """下载指定格式的数据导出文件 (excel, csv, json, zip, docx)"""
    license_info = get_license_status()

    if fmt == "excel":
        file_path = OUTPUT_DIR / "articles_summary.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        dl_name = "今日头条文章汇总.xlsx"
    elif fmt == "csv":
        file_path = OUTPUT_DIR / "articles_summary.csv"
        media_type = "text/csv; charset=utf-8"
        dl_name = "今日头条文章汇总.csv"
    elif fmt == "json":
        file_path = OUTPUT_DIR / "articles_data.json"
        media_type = "application/json"
        dl_name = "今日头条数据完整包.json"
    elif fmt == "zip":
        if not license_info["is_vip"]:
            raise HTTPException(status_code=403, detail="体验版不支持全量一键 Zip 打包下载，请升级 VIP 会员！")
        file_path = OUTPUT_DIR / "articles_package.zip"
        media_type = "application/zip"
        dl_name = "今日头条全部文章与配图包.zip"
    elif fmt == "docx":
        # 导出单篇为 Word 文档
        if not filename:
            raise HTTPException(status_code=400, detail="请指定要导出 Word 的文件名")
        safe_name = Path(filename).name
        md_file = OUTPUT_DIR / "articles" / safe_name
        if not md_file.exists():
            raise HTTPException(status_code=404, detail="指定文章文件不存在")
        
        with open(md_file, "r", encoding="utf-8") as f:
            raw_content = f.read()

        title = safe_name.replace(".md", "")
        m_title = re.search(r'title:\s*"(.*?)"', raw_content)
        if m_title:
            title = m_title.group(1)

        out_docx = OUTPUT_DIR / "docx" / f"{safe_name}.docx"
        docx_exporter.export_article_to_docx({
            "title": title,
            "content_markdown": raw_content,
            "publish_time": "",
            "read_count": 0,
            "digg_count": 0
        }, str(out_docx))

        return FileResponse(
            path=str(out_docx),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{title}.docx"
        )
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="导出文件尚未生成，请先执行采集任务")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=dl_name
    )


@app.post("/api/system/open-folder")
async def open_output_folder():
    """在 Windows 资源管理器中打开数据输出目录"""
    folder_path = str(OUTPUT_DIR.resolve())
    try:
        if sys.platform == "win32":
            os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
        return {"success": True, "path": folder_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件夹失败: {str(e)}")


def run_server(host: str = "127.0.0.1", port: int = 8765, auto_open: bool = True):
    """启动本地服务并自动在浏览器中打开"""
    import webbrowser
    import threading

    if auto_open:
        url = f"http://{host}:{port}/"
        def _open():
            time.sleep(1.0)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    print("=" * 60)
    print("      今日头条文章采集大师 (Toutiao Scraper Studio)")
    print("=" * 60)
    print(f" [*] 后台服务已启动: http://{host}:{port}/")
    print(" [*] 正在自动为您打开浏览器控制台...")
    print(" [*] 如需退出程序，直接关闭当前窗口或按 Ctrl+C")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
