# -*- coding: utf-8 -*-
"""
今日头条文章采集大师 - 任务调度与状态管理器 (Task Manager)
=========================================================
- 负责单例/并发采集任务状态的维护。
- 维护 SSE (Server-Sent Events) 事件广播通道，向所有连接的前端客户端实时推送事件。
- 维护历史文章缓存与任务运行指标。
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from spider_core import ToutiaoSpiderCore


class TaskManager:
    """采集任务与事件调度管理器 (单例)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.current_spider: Optional[ToutiaoSpiderCore] = None
        self.current_task_future: Optional[asyncio.Task] = None
        self.sse_subscribers: Set[asyncio.Queue] = set()

        self.last_summary: Optional[Dict[str, Any]] = None
        self.latest_articles: List[Dict[str, Any]] = []
        self.task_logs: List[Dict[str, Any]] = []
        self.task_state: Dict[str, Any] = {
            "state": "idle",  # idle, running, completed, failed, cancelled
            "step": "idle",
            "progress": 0,
            "current_index": 0,
            "total": 0,
            "current_title": "",
            "author_name": "",
            "discovered_count": 0,
            "start_time": None,
            "elapsed_seconds": 0
        }

    async def subscribe_events(self) -> asyncio.Queue:
        """为新的前端客户端创建 SSE 事件通道队列"""
        q = asyncio.Queue(maxsize=100)
        self.sse_subscribers.add(q)
        return q

    def unsubscribe_events(self, q: asyncio.Queue):
        """移除已断开连接的前端客户端通道"""
        self.sse_subscribers.discard(q)

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """向所有前端客户端广播 SSE 事件"""
        payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False)
        disconnected = set()
        for q in list(self.sse_subscribers):
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                q.put_nowait(payload)
            except Exception:
                disconnected.add(q)
        for q in disconnected:
            self.sse_subscribers.discard(q)

    async def handle_spider_event(self, event_type: str, data: Dict[str, Any]):
        """处理来自 Spider Core 抛出的事件"""
        if event_type == "log":
            self.task_logs.append(data)
            if len(self.task_logs) > 500:
                self.task_logs.pop(0)

        elif event_type == "status":
            self.task_state.update(data)
            if self.task_state.get("start_time"):
                self.task_state["elapsed_seconds"] = round(time.time() - self.task_state["start_time"], 1)

        elif event_type == "author_info":
            self.task_state["author_name"] = data.get("name", "")

        elif event_type == "article_discovered":
            self.task_state["discovered_count"] = data.get("total_count", 0)

        elif event_type == "article_processed":
            item = data.get("item")
            if item:
                # 检查是否已在列表中，更新或追加
                existing = False
                for idx, a in enumerate(self.latest_articles):
                    if a.get("group_id") == item.get("group_id"):
                        self.latest_articles[idx] = item
                        existing = True
                        break
                if not existing:
                    self.latest_articles.append(item)

        elif event_type == "export_ready":
            self.last_summary = data

        await self.broadcast(event_type, data)

    async def start_task(
        self,
        author_url: str,
        max_articles: Optional[int] = None,
        fetch_content: bool = True,
        download_images: bool = False,
        headless: bool = True,
        delay: float = 0.6
    ) -> Dict[str, Any]:
        """发起新的采集任务"""
        if self.current_spider and self.task_state.get("state") == "running":
            return {"success": False, "message": "已有采集任务正在运行中，请等待其完成或先点击中止。"}

        # 重置状态
        self.task_logs.clear()
        self.latest_articles.clear()
        self.last_summary = None
        self.task_state = {
            "state": "running",
            "step": "initializing",
            "progress": 0,
            "current_index": 0,
            "total": 0,
            "current_title": "",
            "author_name": "",
            "discovered_count": 0,
            "start_time": time.time(),
            "elapsed_seconds": 0
        }

        self.current_spider = ToutiaoSpiderCore(
            author_url=author_url,
            output_dir="./toutiao_output",
            max_articles=max_articles,
            fetch_content=fetch_content,
            download_images=download_images,
            headless=headless,
            delay=delay,
            event_callback=self.handle_spider_event
        )

        async def _run_wrapper():
            try:
                res = await self.current_spider.run()
                if res.get("status") == "completed":
                    self.latest_articles = res.get("articles", [])
            except Exception as e:
                self.task_state["state"] = "failed"
                await self.broadcast("status", {"state": "failed", "error": str(e)})

        self.current_task_future = asyncio.create_task(_run_wrapper())
        return {"success": True, "message": "采集任务已成功启动"}

    def stop_task(self) -> Dict[str, Any]:
        """中止当前采集任务"""
        if self.current_spider and self.task_state.get("state") == "running":
            self.current_spider.cancel()
            self.task_state["state"] = "cancelled"
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.broadcast("status", {
                        "state": "cancelled",
                        "step": "cancelled",
                        "progress": self.task_state.get("progress", 0)
                    }))
            except Exception:
                pass
            return {"success": True, "message": "已成功中止采集任务"}
        return {"success": False, "message": "当前没有正在运行的任务"}

    def get_status(self) -> Dict[str, Any]:
        """获取当前综合运行状态快照"""
        if self.task_state.get("start_time") and self.task_state.get("state") == "running":
            self.task_state["elapsed_seconds"] = round(time.time() - self.task_state["start_time"], 1)

        return {
            "task_state": self.task_state,
            "articles_count": len(self.latest_articles),
            "logs_count": len(self.task_logs),
            "has_summary": self.last_summary is not None
        }


# 全局单例管理器
task_manager = TaskManager()
