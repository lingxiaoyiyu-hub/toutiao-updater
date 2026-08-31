"""
自媒体智能写作模块 (Self-Media AI Creation Engine)
从 WritingStudio 提取并优化的自媒体原创写作、模仿二创、爆款选题与文风解构引擎。
基于纯原生 httpx 异步流式实现，兼容所有 OpenAI 接口规范 (DeepSeek / OpenAI / 通义千问 / 阶跃星辰 / SiliconFlow 等)。
"""

import json
import os
import re
from typing import Dict, Any, List, Optional, AsyncGenerator
import httpx

from pathlib import Path

try:
    from modules.app_config import get_app_data_dir
except ImportError:
    from app_config import get_app_data_dir

PERSISTENT_CONFIG_FILE = get_app_data_dir() / "ai_config.json"
LOCAL_CONFIG_FILE = Path(__file__).parent.parent / "data" / "ai_config.json"
LOCAL_EXAMPLE_FILE = Path(__file__).parent.parent / "data" / "ai_config.json.example"

DEFAULT_AI_CONFIG = {
    "api_base": "https://api.deepseek.com/v1",
    "api_key": "",
    "model_name": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 4096
}

def load_ai_config() -> Dict[str, Any]:
    """
    加载 AI 模型配置。
    优先从用户全局 AppData 目录加载（确保重启、重新打包、免安装解压后配置 100% 保持）；
    若不存在，则按顺序检查本地 data/ 目录及示例文件。
    """
    # 1. 优先从全局持久化目录读取
    if PERSISTENT_CONFIG_FILE.exists():
        try:
            with open(PERSISTENT_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("api_key") is not None:
                    return data
        except Exception:
            pass

    # 2. 从本地 data 目录读取
    if LOCAL_CONFIG_FILE.exists():
        try:
            with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    save_ai_config(data)
                    return data
        except Exception:
            pass

    # 3. 从本地 example 模板读取
    if LOCAL_EXAMPLE_FILE.exists():
        try:
            with open(LOCAL_EXAMPLE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    clean_data = {k: v for k, v in data.items() if not k.startswith("_")}
                    return {**DEFAULT_AI_CONFIG, **clean_data}
        except Exception:
            pass

    return DEFAULT_AI_CONFIG.copy()

def save_ai_config(cfg: Dict[str, Any]):
    """保存 AI 模型配置至 AppData 全局持久化目录，并尝试同步至本地 data/ 目录"""
    # 1. 必须保存到 AppData 全局持久化目录
    try:
        PERSISTENT_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PERSISTENT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[AI Config Error] 保存至 AppData 失败: {e}")

    # 2. 尝试同步保存到本地 data/ 目录（如果环境可写）
    try:
        LOCAL_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class MediaAIClient:
    """自媒体 LLM 客户端，支持标准 OpenAI 兼容接口与实时流式输出 (SSE)"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_ai_config()
        self.api_base = self.config.get("api_base", "https://api.openai.com/v1").rstrip("/")
        self.api_key = self.config.get("api_key", "").strip()
        self.model_name = self.config.get("model_name", "gpt-4o-mini")

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        return headers

    def _get_endpoint(self) -> str:
        base = self.api_base
        if not base.endswith("/chat/completions"):
            if not base.endswith("/v1"):
                base = f"{base}/v1"
            base = f"{base}/chat/completions"
        return base

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """异步 SSE 逐 token 流式输出"""
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": min(max_tokens or self.config.get("max_tokens", 4096), 16384),
            "temperature": min(max(temperature if temperature is not None else self.config.get("temperature", 0.7), 0.0), 1.5),
            "stream": True
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=300.0, write=30.0, pool=5.0)) as client:
            async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    yield f"[API 请求失败 ({response.status_code})]: {err_body.decode('utf-8', errors='ignore')}"
                    return

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_str)
                            choices = data_json.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except Exception:
                            pass

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """非流式调用"""
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": min(max_tokens or self.config.get("max_tokens", 4096), 16384),
            "temperature": min(max(temperature if temperature is not None else self.config.get("temperature", 0.7), 0.0), 1.5),
            "stream": False
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=5.0)) as client:
            res = await client.post(endpoint, headers=headers, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"API Error {res.status_code}: {res.text}")
            data = res.json()
            return data["choices"][0]["message"]["content"]


# =========================================================================
#  平台规则字典
# =========================================================================

PLATFORM_TOPIC_RULES: Dict[str, Dict[str, str]] = {
    "今日头条": {
        "char_range": "25-30字",
        "style": "数字化+悬念式，三段式结构",
        "requirements": "强冲突、强数字、强悬念，吸引点击",
        "example": "90%的人不知道：这3个习惯正在毁掉你的健康",
    },
    "微信公众号": {
        "char_range": "20-30字",
        "style": "情感共鸣式，简洁有共鸣",
        "requirements": "简洁有力，引发情感共鸣",
        "example": "每个成年人，都需要学会的一课",
    },
    "知乎": {
        "char_range": "15-30字",
        "style": "问题导向，疑问式讨论",
        "requirements": "用问句引发思考和讨论",
        "example": "为什么越来越多人选择不结婚？",
    },
    "小红书": {
        "char_range": "10-20字（含emoji）",
        "style": "分享式，口语化",
        "requirements": "口语化、加emoji、制造惊喜感",
        "example": "🔥姐妹们！这个方法真的绝了",
    },
    "抖音": {
        "char_range": "8-15字",
        "style": "强钩子，极简冲击力",
        "requirements": "极简、强冲击、制造好奇",
        "example": "千万别这样做！",
    },
    "通用": {
        "char_range": "25-30字",
        "style": "通用式，平衡各平台",
        "requirements": "平衡各平台特点，适用性强",
        "example": "关于XX，你需要知道的3件事",
    },
}

PLATFORM_RULES = {
    "今日头条": "标题要强冲突、强数字、强悬念。开头前三句必须抓人。每段不超过3句，节奏极快。多用口语，少用书面语。结尾引导评论互动。",
    "微信公众号": "适合深度长文，1500-3000字最佳。标题控制在20字以内。段落间距大，每段2-4句。结尾引导关注、点赞、在看。读者有耐心，接受一定专业深度。",
    "知乎": "读者有知识水平，接受深度分析。标题用问句或观点句。可以有数据、引用、逻辑推理。结构清晰，适当用小标题分层。语气略带学术但不干燥。",
    "小红书": "标题加emoji。正文每段1-2句，大量换行。多用emoji分隔段落。语气亲切像朋友聊天。结尾加话题标签建议。字数500-800字最佳。",
    "抖音": "内容节奏快，开头强钩子。语言口语化，每段简短有力。适合各类视频内容的文案风格，包括解说、科普、观点等。结尾有行动号召。",
    "B站": "语言年轻化、有梗。内容可以有深度但保持趣味性。适当加互动引导。可以引用网络用语和亚文化。结尾三连引导。",
    "通用": "结构清晰，观点鲜明。语言通俗易懂。节奏适中，每段3-5句。",
}


# =========================================================================
#  Prompt 构建逻辑 (从 WritingStudio 提取)
# =========================================================================

def build_original_article_messages(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """原创写作模式 Prompt"""
    platform = payload.get("platform", "今日头条")
    article_type = payload.get("article_type", "观点文")
    topic_domain = payload.get("topic_domain", "社会热点")
    topic = payload.get("topic", "")
    keywords = payload.get("keywords", "")
    target_words = payload.get("target_words", 1200)
    tone = payload.get("tone", "观点鲜明")
    humanize = payload.get("humanize", True)
    safe_mode = payload.get("safe_mode", True)
    paragraph_count = payload.get("paragraph_count", 8)
    structure = payload.get("structure", "自动")
    add_emoji = payload.get("add_emoji", False)
    strong_hook = payload.get("strong_hook", True)
    reference_material = payload.get("reference_material", "")
    user_instruction = payload.get("user_instruction", "")

    platform_rule = PLATFORM_RULES.get(platform, PLATFORM_RULES["今日头条"])

    extra_rules = []
    if humanize:
        extra_rules.append(
            "【去AI腔核心禁令】\n"
            "- 禁用词汇：首先其次最后、总而言之、综上所述、值得一提的是、不得不说、可以说、不得不承认\n"
            "- 禁止使用排比句，三段式并列结构一律不要\n"
            "- 段落之间不要使用小标题，直接自然过渡\n"
            "- 过渡词只用最基础的常用词，禁用书面连接词（然而、因此、由此可见、与此同时）\n"
            "- 禁止段落末尾做总结句（这说明了、这体现了、由此可见）\n"
            "- 禁止泛泛而谈，每段必须有具体信息、事实或细节支撑，不能只讲道理\n"
            "- 多用短句推进，少用长句；多用具体细节，少用抽象概括"
        )
    
    if safe_mode:
        extra_rules.append(
            "【合规要求】\n"
            "- 避免极端化表达和绝对化判断\n"
            "- 涉及敏感话题时保持客观中立\n"
            "- 用理性分析代替情绪宣泄"
        )
    extra_rules_text = "\n\n".join(extra_rules)

    system_prompt = f"""你是一个成熟的真人自媒体作者，不是AI助手。你的任务不是"写一篇正确的文章"，而是写出能让人愿意点、愿意读、愿意读完、愿意互动的爆款稿件。

【总原则】
1. 标题负责把人拉进来，正文负责把人留下来。
2. 文章开头必须立刻进入问题、冲突、反常识、代入场景或强观点，不能慢热。
3. 每一段都要有作用：推进信息、加重冲突、补足案例、抬高观点、制造下一段阅读动力。
4. 不要写成"正确但无聊"的说明文，要写成有人味、有判断、有推进感的成稿。
5. 围着标题里的矛盾、反差、疑问展开，全篇一气呵成。

【标题怎么写】
- 优先使用：疑问、反常识、数字反差、身份反差、结果反差、现实冲突。
- 8个标题角度要拉开，不要只是换词重复。

【正文怎么写】
- 开头前3句必须完成一件事：把读者拉进具体问题里。
- 正文不要空讲道理，要用事实、例子、场景、对比把观点顶出来。
- 一段一个重点，多写"发生了什么""为什么会这样""这意味着什么"。
- 结尾不要假大空升华，最好收在明确判断、现实余味、反问或互动点上。

【{platform}平台规范】
{platform_rule}

{extra_rules_text}"""

    extra_controls = []
    if structure != "自动":
        extra_controls.append(f"文章结构：采用{structure}结构组织内容")
    if add_emoji:
        extra_controls.append("适当在标题和段落开头加入emoji，增强视觉层次")
    if strong_hook:
        extra_controls.append("第一句话必须是强钩子，用数字、反常识或强冲突开篇")
    if reference_material:
        extra_controls.append(f"【参考文风】请深度模仿以下文章的写作风格与节奏腔调（不抄内容）：\n{reference_material}")
    extra_controls_text = "\n".join(extra_controls) if extra_controls else "无特殊控制"

    user_prompt = f"""【创作任务】
文章类型：{article_type}
热点领域：{topic_domain}
核心选题：{topic}
关键词：{keywords}
目标字数：{target_words}字
段落数量：约{paragraph_count}段
语气风格：{tone}

【格式与控制】
{extra_controls_text}

【额外要求】
{user_instruction or "无特殊要求"}

【字数要求】正文不少于{target_words}字，不要提前收尾。

---

【输出格式】
【标题候选】
请生成8个标题（含悬念型、冲突型、数字型、口语型等）。

【正文】
直接开始正文，第一段必须立刻抓人。"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_remix_article_messages(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """模仿二创模式 Prompt"""
    platform = payload.get("platform", "今日头条")
    article_type = payload.get("article_type", "观点文")
    target_words = payload.get("target_words", 1200)
    tone = payload.get("tone", "观点鲜明")
    humanize = payload.get("humanize", True)
    safe_mode = payload.get("safe_mode", True)
    source_material = payload.get("source_material", "")
    rewrite_mode = payload.get("rewrite_mode", "angle_shift")
    reference_strength = payload.get("reference_strength", "medium")
    remix_angle = payload.get("remix_angle", "")
    remix_style = payload.get("remix_style", "")
    fusion_requirement = payload.get("fusion_requirement", "")
    user_instruction = payload.get("user_instruction", "")

    platform_rule = PLATFORM_RULES.get(platform, PLATFORM_RULES["今日头条"])

    strength_map = {
        "light": "弱参考：只借鉴选题角度和结构框架，内容完全重写",
        "medium": "中参考：借鉴选题、结构和部分观点，表达方式和案例全新",
        "strong": "强参考：深度借鉴原文逻辑和论证方式，但必须用自己的语言重新表达",
    }
    ref_instruction = strength_map.get(reference_strength, strength_map["medium"])

    mode_instructions = {
        "angle_shift": f"换角度重写：从「{remix_angle or '全新反转视角'}」切入同一话题，提出不同见解",
        "style_shift": f"换风格重写：保持核心观点，改用「{remix_style or '接地气口语化'}」的表达风格",
        "fusion_mix": f"深度提炼融合：从来源文章中提取核心骨架，融合以下补充观点：{fusion_requirement or '自由补充相关事实'}",
        "hybrid_rewrite": f"角度+风格双改：从「{remix_angle or '新锐视角'}」切入，用「{remix_style or '犀利热点评述'}」风格表达",
    }
    mode_instruction = mode_instructions.get(rewrite_mode, "参考原文进行创作性改写")

    extra_rules = []
    if humanize:
        extra_rules.append(
            "【去AI腔核心禁令】\n"
            "- 禁用词汇：首先其次最后、总而言之、综上所述、值得一提的是、不得不说、可以说\n"
            "- 禁止使用排比句与小标题，多用短句推进，自然段过渡"
        )
    extra_rules_text = "\n\n".join(extra_rules)

    system_prompt = f"""你是一个真人自媒体作者，擅长参考爆文进行高品质创作性改写。

【改写核心原则】
1. 换角度：同一话题，不同切入点
2. 换案例：同样观点，不同论证材料  
3. 换表达：同样意思，不同说法（口语化、接地气）
4. 换节奏：短句推进，制造小高潮
5. 换情绪：有态度、有情绪、有人味

【绝对禁止】
❌ 照搬原文句子（观点可借，表达全部重写）
❌ 首先其次最后、总而言之
❌ 段落结尾做假大空总结

【参考强度】
{ref_instruction}

【创作模式】
{mode_instruction}

【{platform}平台规范】
{platform_rule}

{extra_rules_text}"""

    user_prompt = f"""【来源文章】
{source_material}

【创作任务】
文章类型：{article_type}
目标字数：{target_words}字
语气风格：{tone}

【额外要求】
{user_instruction or "无特殊要求"}

【字数要求】正文不少于{target_words}字。

---

【输出格式】
【标题候选】
（生成8个标题）

【正文】
（第一句话就要抓人，直接抛冲突，像真人在说话）"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_topic_generation_messages(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """爆款选题灵感生成 Prompt"""
    mode = payload.get("mode", "keyword")
    platform = payload.get("platform", "今日头条")
    count = min(max(int(payload.get("count", 10)), 1), 20)
    keyword = (payload.get("keyword") or "").strip() or "热点话题"
    news_content = (payload.get("news_content") or "").strip()

    rule = PLATFORM_TOPIC_RULES.get(platform, PLATFORM_TOPIC_RULES["今日头条"])

    system_prompt = f"""你是一个顶尖自媒体选题导师，深谙爆款标题的心理学与流量机制。

【{platform}平台规则】
- 字数要求：{rule['char_range']}
- 风格要求：{rule['style']}
- 爆点逻辑：{rule['requirements']}

【输出格式】
严格输出 JSON 数组（不要 markdown 代码块包裹，纯 JSON 字符串）：
[
  {{"title": "标题内容", "viral_score": 5, "reason": "爆点理由说明", "angle": "切入角度"}}
]"""

    if mode == "keyword":
        user_content = f"请为【{platform}】平台，围绕关键词/领域「{keyword}」，生成 {count} 个高点击率爆款选题与标题。"
    else:
        user_content = f"请基于以下热点资讯/文章内容，为【{platform}】平台提取并生成 {count} 个爆款选题与标题：\n\n{news_content[:3000]}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def generate_fallback_topics(keyword: str, platform: str = "今日头条", count: int = 10) -> List[Dict[str, Any]]:
    """本地内置的高转化爆款选题生成算法 (免 API Key 离线极速生成)"""
    kw = (keyword or "热点话题").strip()
    
    templates = [
        {"pattern": "90%的人都不知道！关于{kw}的3个隐蔽真相，早看早受益", "reason": "打破认知差 + 悬念感", "angle": "深度揭秘", "score": 5},
        {"pattern": "2026年{kw}新规落地！这几类人群要注意了，少做一步亏大了", "reason": "政策风向 + 损失厌恶", "angle": "政策解读", "score": 5},
        {"pattern": "建议收藏！普通人搞懂{kw}的5个底层逻辑，少走10年弯路", "reason": "实用干货 + 避坑指南", "angle": "方法干货", "score": 5},
        {"pattern": "为什么越来越多人不再盲目追求{kw}？老行家说了3句大实话", "reason": "反向思辨 + 行内人揭底", "angle": "犀利洞察", "score": 5},
        {"pattern": "同样是{kw}，为什么别人月入过万你却亏损？差距就在这4点", "reason": "强反差对比 + 痛点直击", "angle": "对比剖析", "score": 4},
        {"pattern": "突发！关于{kw}的重要提醒，家家户户都用得上，别等吃亏才后悔", "reason": "突发急迫感 + 普适共鸣", "angle": "民生热点", "score": 5},
        {"pattern": "干了20年老手掏心窝：{kw}千万别踩这3个雷区，句句是教训", "reason": "权威背书 + 真实经验", "angle": "经验传授", "score": 4},
        {"pattern": "{kw}真的靠谱吗？深度实测一个月后，我发现了惊人内幕", "reason": "第一人称真实体验 + 猎奇心理", "angle": "实测拆解", "score": 5},
        {"pattern": "千万别大意！关于{kw}的这2个常见误区，很多人天天都在犯", "reason": "警示纠错 + 焦虑唤醒", "angle": "避坑科普", "score": 4},
        {"pattern": "看懂这篇就够了！一文讲透{kw}的前世今生与未来趋势", "reason": "全景指南 + 终极省流", "angle": "深度全景", "score": 4},
        {"pattern": "邻居老王因为做对了一件事，靠{kw}打了个漂亮翻身仗，方法值得借鉴", "reason": "故事化叙事 + 榜样效应", "angle": "故事案例", "score": 4},
        {"pattern": "{kw}最新风口已来？抓住这波红利的3个关键动作，建议提早布局", "reason": "前瞻风口 + 行动指引", "angle": "趋势前瞻", "score": 5},
        {"pattern": "为什么专家总劝你慎重对待{kw}？背后真实原因让人深思", "reason": "权威视角 + 探寻本质", "angle": "深度思辨", "score": 4},
        {"pattern": "一算吓一跳！在{kw}这件事上，聪明人早就用上了这套极简法则", "reason": "收益惊艳 + 高效法则", "angle": "技巧拆解", "score": 5},
        {"pattern": "老实人必看：关于{kw}的4条潜规则，没人会主动告诉你", "reason": "社会人情世故 + 扎心真理", "angle": "底层人情", "score": 5}
    ]
    
    import random
    selected = templates.copy()
    random.shuffle(selected)
    
    results = []
    for t in selected[:count]:
        results.append({
            "title": t["pattern"].replace("{kw}", kw),
            "viral_score": t["score"],
            "reason": t["reason"],
            "angle": t["angle"]
        })
    return results
