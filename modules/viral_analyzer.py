# -*- coding: utf-8 -*-
"""
今日头条文章爆款分析器 (Viral Scorer & Structure Analyzer)
==========================================================
支持：
1. 爆款综合指数计算 (互动加权)
2. 黄金开头 (Golden Hook) 自动提取
3. 情绪触发词识别 (冲突/悬念/共情/干货利他)
4. 文章结构体检与改写建议
"""

import re
from typing import Dict, Any, List


class ViralAnalyzer:
    """文章爆款特征分析器"""

    @staticmethod
    def calculate_score(reads: int = 0, comments: int = 0, likes: int = 0) -> Dict[str, Any]:
        """
        计算爆款互动热度指数与转化率评级
        - 评论互动权重最高 (5.0)
        - 点赞认同权重 (1.5)
        - 阅读转化基数 (0.1)
        """
        raw_score = (comments * 5.0) + (likes * 1.5) + (reads * 0.05)
        
        # 评级划分
        if raw_score >= 10000 or reads >= 100000:
            level = "S+ 超级爆款"
            level_color = "rose"
        elif raw_score >= 3000 or reads >= 30000:
            level = "S 头部大热文"
            level_color = "orange"
        elif raw_score >= 800 or reads >= 8000:
            level = "A 优质互动文"
            level_color = "emerald"
        else:
            level = "B 常规文章"
            level_color = "slate"

        interaction_rate = round((likes + comments) / max(reads, 1) * 100, 2)

        return {
            "score": round(raw_score, 1),
            "level": level,
            "level_color": level_color,
            "interaction_rate": f"{interaction_rate}%"
        }

    @staticmethod
    def analyze_content(title: str, content: str) -> Dict[str, Any]:
        """
        拆解文章结构、黄金开头与情绪触发点
        """
        paragraphs = [p.strip() for p in content.split("\n") if p.strip() and not p.startswith("#") and not p.startswith(">")]
        hook = paragraphs[0] if paragraphs else title

        emotion_keywords = {
            "冲突对立": ["没想到", "翻脸", "争吵", "隐瞒", "拒绝", "断绝", "怒斥", "反悔", "闹翻", "不讲理"],
            "悬念好奇": ["其实", "秘密", "真相", "居然", "竟然", "万万没想到", "谁料", "到底为什么", "原来"],
            "现实共情": ["心酸", "委屈", "不容易", "扎心", "泪目", "感动", "现实", "生活不易", "老百姓", "父母"],
            "干货实用": ["建议", "干货", "收藏", "避坑", "诀窍", "方法", "省钱", "牢记", "注意这几点"]
        }

        detected_triggers = []
        for trigger_name, kws in emotion_keywords.items():
            matched = [kw for kw in kws if kw in content or kw in title]
            if matched:
                detected_triggers.append({
                    "name": trigger_name,
                    "matched": matched[:3]
                })

        # 结尾是否有号召互动 CTA
        has_cta = any(q in (paragraphs[-1] if paragraphs else "") for q in ["？", "?", "你怎么看", "留言", "评论区", "觉得呢", "说说你的看法"])

        word_count = len(content)
        read_time_min = round(word_count / 350.0, 1)

        suggestions = []
        if len(hook) < 15:
            suggestions.append("开头吸引力较短，建议扩充前30字制造冲突或提问悬念。")
        if not detected_triggers:
            suggestions.append("文章情感触发词较平淡，可适当加入生活痛点或共鸣词汇。")
        if not has_cta:
            suggestions.append("结尾未检测到互动提问，建议在文末增加引导读者评论留言的引导句。")
        if word_count > 1800:
            suggestions.append("字数较长，建议增加小标题或段落图片以提升完播率。")

        return {
            "title": title,
            "word_count": word_count,
            "estimated_reading_min": read_time_min,
            "golden_hook": hook[:120],
            "paragraph_count": len(paragraphs),
            "triggers": detected_triggers,
            "has_cta_ending": has_cta,
            "suggestions": suggestions
        }


viral_analyzer = ViralAnalyzer()
