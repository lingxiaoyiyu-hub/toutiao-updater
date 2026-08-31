/**
 * XCbot · 今日头条采集与自媒体AI创作工作台 - 前端主控制器 (App Controller)
 */

let systemInfo = null;
let articlesList = [];
let eventSource = null;
let isTaskRunning = false;
let currentTab = "author";
let currentMediaSubmode = "original";
let currentTopicMode = "keyword";
let generatedMarkdown = "";

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  loadSystemInfo();
  loadArticles();
  loadAiConfigForm();
  initSSE();
  fetchUpdateCheck(true);

  // 初始化滑动指示器
  const activeTab = document.querySelector(".tab.active");
  if (activeTab) {
    moveIndicator(activeTab);
  }
  window.addEventListener("resize", () => {
    const cur = document.querySelector(".tab.active");
    if (cur) moveIndicator(cur);
  });
});

// 滑动下划线指示器
function moveIndicator(tab) {
  const indicator = document.getElementById("tabIndicator");
  if (indicator && tab) {
    indicator.style.width = tab.offsetWidth + "px";
    indicator.style.transform = "translateX(" + tab.offsetLeft + "px)";
  }
}

// 切换顶级选项卡 (作者采集 / 自媒体写作 / 全网热搜)
function switchTab(tabId, el) {
  currentTab = tabId;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  if (el) {
    el.classList.add("active");
    moveIndicator(el);
  }

  const authorPane = document.getElementById("tab-content-author");
  const mediaPane = document.getElementById("tab-content-media");
  const hotPane = document.getElementById("tab-content-hot");

  authorPane.style.display = "none";
  mediaPane.style.display = "none";
  hotPane.style.display = "none";

  if (tabId === "author") {
    authorPane.style.display = "contents";
  } else if (tabId === "media") {
    mediaPane.style.display = "block";
  } else if (tabId === "hot") {
    hotPane.style.display = "block";
    loadHotBoard();
  }
}

// 切换自媒体写作台子模式 (原创写作 / 模仿二创 / 爆款选题 / AI 配置)
function switchMediaSubmode(submode, btn) {
  currentMediaSubmode = submode;
  document.querySelectorAll(".media-subtab").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");

  document.querySelectorAll(".media-subpane").forEach(p => p.style.display = "none");
  const targetPane = document.getElementById(`media-subpane-${submode}`);
  if (targetPane) targetPane.style.display = "block";
}

function toggleTopicMode(mode) {
  currentTopicMode = mode;
  document.getElementById("topic-pill-keyword").classList.toggle("active", mode === "keyword");
  document.getElementById("topic-pill-news").classList.toggle("active", mode === "news");

  document.getElementById("topic-mode-keyword-box").style.display = mode === "keyword" ? "block" : "none";
  document.getElementById("topic-mode-news-box").style.display = mode === "news" ? "block" : "none";
}

// ================= AI 模型配置管理 =================
async function loadAiConfigForm() {
  try {
    const res = await fetch("/api/media/config");
    if (res.ok) {
      const cfg = await res.json();
      document.getElementById("ai-cfg-base").value = cfg.api_base || "https://api.openai.com/v1";
      document.getElementById("ai-cfg-key").value = cfg.api_key || "";
      document.getElementById("ai-cfg-model").value = cfg.model_name || "gpt-4o-mini";
      document.getElementById("ai-cfg-temp").value = cfg.temperature || 0.7;
    }
  } catch (err) {
    console.error("加载 AI 配置失败:", err);
  }
}

async function saveAiConfigForm() {
  const base = document.getElementById("ai-cfg-base").value.trim();
  const key = document.getElementById("ai-cfg-key").value.trim();
  const model = document.getElementById("ai-cfg-model").value.trim();
  const temp = parseFloat(document.getElementById("ai-cfg-temp").value) || 0.7;
  const msgEl = document.getElementById("ai-cfg-msg");

  if (!key) {
    msgEl.innerText = "请输入 API Key！";
    msgEl.style.color = "#d6336c";
    msgEl.style.display = "block";
    return;
  }

  try {
    const res = await fetch("/api/media/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_base: base,
        api_key: key,
        model_name: model,
        temperature: temp
      })
    });
    const data = await res.json();
    if (res.ok) {
      msgEl.innerText = `✓ ${data.message}`;
      msgEl.style.color = "#0d9488";
      msgEl.style.display = "block";
      setTimeout(() => { msgEl.style.display = "none"; }, 3000);
    } else {
      msgEl.innerText = `保存失败: ${data.detail}`;
      msgEl.style.color = "#d6336c";
      msgEl.style.display = "block";
    }
  } catch (err) {
    msgEl.innerText = `请求异常: ${err.message}`;
    msgEl.style.color = "#d6336c";
    msgEl.style.display = "block";
  }
}

function fillAiPreset(preset) {
  if (preset === "deepseek") {
    document.getElementById("ai-cfg-base").value = "https://api.deepseek.com";
    document.getElementById("ai-cfg-model").value = "deepseek-chat";
  } else if (preset === "zhipu") {
    document.getElementById("ai-cfg-base").value = "https://open.bigmodel.cn/api/paas/v4";
    document.getElementById("ai-cfg-model").value = "glm-4-flash";
  } else if (preset === "openai") {
    document.getElementById("ai-cfg-base").value = "https://api.openai.com/v1";
    document.getElementById("ai-cfg-model").value = "gpt-4o-mini";
  } else if (preset === "silicon") {
    document.getElementById("ai-cfg-base").value = "https://api.siliconflow.cn/v1";
    document.getElementById("ai-cfg-model").value = "deepseek-ai/DeepSeek-V3";
  } else if (preset === "qwen") {
    document.getElementById("ai-cfg-base").value = "https://dashscope.aliyuncs.com/compatible-mode/v1";
    document.getElementById("ai-cfg-model").value = "qwen-plus";
  }
}

// ================= AI 文章流式生成 (原创与二创) =================
async function startGenerateArticle(mode) {
  const outputView = document.getElementById("media-output-view");
  const streamPill = document.getElementById("mw-streaming-pill");

  let payload = { mode: mode };

  if (mode === "original") {
    const topic = document.getElementById("mw-topic-input").value.trim();
    if (!topic) {
      alert("请输入文章核心选题！");
      return;
    }
    payload.topic = topic;
    payload.platform = document.getElementById("mw-platform-select").value;
    payload.article_type = document.getElementById("mw-type-select").value;
    payload.target_words = parseInt(document.getElementById("mw-words-input").value, 10) || 1200;
    payload.tone = document.getElementById("mw-tone-select").value;
    payload.humanize = document.getElementById("mw-humanize-toggle").checked;
    payload.strong_hook = document.getElementById("mw-hook-toggle").checked;
    payload.reference_material = document.getElementById("mw-ref-style-input").value.trim();
  } else {
    const source = document.getElementById("mw-remix-source").value.trim();
    if (!source) {
      alert("请粘贴来源文章正文或素材！");
      return;
    }
    payload.source_material = source;
    payload.rewrite_mode = document.getElementById("mw-remix-mode-select").value;
    payload.reference_strength = document.getElementById("mw-remix-strength-select").value;
    payload.target_words = parseInt(document.getElementById("mw-remix-words-input").value, 10) || 1200;
    payload.remix_style = document.getElementById("mw-remix-style-select").value;
    payload.platform = "今日头条";
    payload.humanize = true;
  }

function setRemixWords(val) {
  const el = document.getElementById("mw-remix-words-input");
  if (el) {
    el.value = val;
    el.focus();
  }
}

function setOriginalWords(val) {
  const el = document.getElementById("mw-words-input");
  if (el) {
    el.value = val;
    el.focus();
  }
}

  // 准备流式接收
  generatedMarkdown = "";
  outputView.innerHTML = '<div style="color:var(--muted); font-size:12px;">正在连接 AI 模型并进行构思规划...</div>';
  streamPill.style.display = "inline-flex";

  try {
    const res = await fetch("/api/media/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      let errMsg = "请求失败";
      try {
        const err = await res.json();
        errMsg = err.detail || err.message || JSON.stringify(err);
      } catch (e) {
        errMsg = await res.text() || `HTTP ${res.status}`;
      }
      outputView.innerHTML = `<div style="color:#d6336c; font-size:12px; line-height:1.6;">⚠️ 生成失败: ${errMsg}</div>`;
      streamPill.style.display = "none";
      if (errMsg.includes("API Key")) {
        switchMediaSubmode("config", document.querySelectorAll(".media-subtab")[3]);
      }
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      generatedMarkdown += text;
      outputView.innerHTML = marked.parse(generatedMarkdown);
      outputView.scrollTop = outputView.scrollHeight;
    }

    streamPill.style.display = "none";
  } catch (err) {
    outputView.innerHTML = `<div style="color:#d6336c; font-size:12px;">生成异常: ${err.message}</div>`;
    streamPill.style.display = "none";
  }
}

// 批量生成选题
async function fetchTopicIdeas() {
  const container = document.getElementById("topics-results-list");
  let payload = {
    mode: currentTopicMode,
    platform: document.getElementById("mw-topic-platform").value,
    count: parseInt(document.getElementById("mw-topic-count").value, 10) || 10
  };

  if (currentTopicMode === "keyword") {
    payload.keyword = document.getElementById("mw-topic-keyword").value.trim();
  } else {
    payload.news_content = document.getElementById("mw-topic-news-content").value.trim();
  }

  container.innerHTML = '<div style="text-align:center; padding:16px; color:var(--muted); font-size:12px;">正在分析热点规律生成高点击率爆款选题...</div>';

  try {
    const res = await fetch("/api/media/topics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      container.innerHTML = `<div style="color:#d6336c; font-size:12px;">生成失败: ${data.error || data.detail}</div>`;
      return;
    }

    const topics = data.topics || [];
    if (topics.length === 0) {
      container.innerHTML = '<div style="color:var(--muted-2); font-size:12px;">未能提取到选题，请重试</div>';
      return;
    }

    container.innerHTML = topics.map((t, idx) => `
      <div class="topic-card">
        <div style="min-width:0;">
          <div style="font-weight:600; font-size:12.5px; color:var(--fg); line-height:1.4;">${idx + 1}. ${t.title}</div>
          <div style="font-size:11px; color:var(--muted-2); margin-top:2px;">
            ${t.reason ? `<span style="color:#b08900;">★ ${t.reason}</span>` : ''}
            ${t.angle ? `<span style="margin-left:6px; color:var(--muted);">视角: ${t.angle}</span>` : ''}
          </div>
        </div>
        <button onclick="useTopicForOriginal('${encodeURIComponent(t.title)}')" class="action-btn-mini" style="background:#0a0a0a; color:#fff; flex-shrink:0;">
          以此写作
        </button>
      </div>
    `).join("");

  } catch (err) {
    container.innerHTML = `<div style="color:#d6336c; font-size:12px;">请求异常: ${err.message}</div>`;
  }
}

function useTopicForOriginal(encTitle) {
  const title = decodeURIComponent(encTitle);
  document.getElementById("mw-topic-input").value = title;
  switchMediaSubmode("original", document.querySelectorAll(".media-subtab")[0]);
}

// 联动功能：从抓取到的头条文章一键发送到二创 (自动获取 100% 完整正文全文)
async function sendToRemix(item) {
  const remixInput = document.getElementById("mw-remix-source");
  remixInput.value = "正在读取完整正文全文内容...";

  // 切换到自媒体 Tab，并激活模仿二创子面板
  const mediaTabBtn = document.querySelectorAll(".tab")[1];
  switchTab("media", mediaTabBtn);
  switchMediaSubmode("remix", document.querySelectorAll(".media-subtab")[1]);

  let fullContent = "";

  // 1. 优先通过 filename 与 group_id 从服务端读取清洗后的纯正文
  try {
    const filenameParam = item.local_file ? encodeURIComponent(item.local_file) : "";
    const gidParam = item.group_id ? encodeURIComponent(item.group_id) : "";
    const res = await fetch(`/api/crawl/article/content?filename=${filenameParam}&group_id=${gidParam}`);
    const data = await res.json();
    if (res.ok && data.content && data.content.length > 50) {
      fullContent = data.content;
    }
  } catch (e) {}

  // 2. 如果本地文件不存在或较短，则实时在线提取该文章的完整正文
  if (!fullContent && item.article_url) {
    try {
      const res = await fetch(`/api/crawl/article/online?url=${encodeURIComponent(item.article_url)}`);
      const data = await res.json();
      if (res.ok && data.content_markdown && data.content_markdown.length > 50) {
        fullContent = data.content_markdown;
      }
    } catch (e) {}
  }

  // 3. 填充到二创输入框
  if (fullContent) {
    remixInput.value = `【参考文章标题】${item.title}\n\n【参考文章正文】\n${fullContent}`;
  } else {
    remixInput.value = `${item.title}\n\n${item.abstract || ""}`;
  }
}

// 联动功能：从热搜榜一键发送到原创写作
function sendToOriginalTopic(title) {
  document.getElementById("mw-topic-input").value = title;
  const mediaTabBtn = document.querySelectorAll(".tab")[1];
  switchTab("media", mediaTabBtn);
  switchMediaSubmode("original", document.querySelectorAll(".media-subtab")[0]);
}

function copyGeneratedContent() {
  if (!generatedMarkdown) {
    alert("暂无可复制的正文内容！");
    return;
  }
  navigator.clipboard.writeText(generatedMarkdown).then(() => {
    alert("文章 Markdown 正文已全部复制到剪贴板！");
  });
}

async function saveGeneratedDoc() {
  if (!generatedMarkdown) {
    alert("暂无生成的文章内容可供保存！");
    return;
  }

  // 从 Markdown 中智能提取标题
  let firstTitle = "自媒体生成文章";
  const m = generatedMarkdown.match(/^#+\s*(.+)$/m) || generatedMarkdown.match(/【标题候选】[\s\S]*?1[、. ]\s*(.+)/);
  if (m && m[1]) {
    firstTitle = m[1].replace(/[#*`]/g, "").trim();
  }

  try {
    const res = await fetch("/api/media/save-doc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: firstTitle,
        content: generatedMarkdown
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`🎉 文章已成功保存至本地！\n文件: ${data.filename}\nWord文档已同步生成。`);
    } else {
      alert(`保存失败: ${data.detail}`);
    }
  } catch (err) {
    alert(`请求异常: ${err.message}`);
  }
}

function clearGeneratedContent() {
  generatedMarkdown = "";
  document.getElementById("media-output-view").innerHTML = `
    <div style="text-align:center; padding:60px 20px; color:var(--muted-2);">
      <svg viewBox="0 0 24 24" width="36" height="36" stroke="currentColor" stroke-width="1.5" fill="none" style="margin:0 auto 12px; opacity:0.4;"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
      <p>在左侧配置创作参数或选题，点击「生成自媒体文章」</p>
      <p style="font-size:11px; margin-top:4px;">生成的 8 大黄金标题候选与正文将在此逐字流式呈现</p>
    </div>
  `;
}

// ================= 系统信息与爬虫基础功能 =================
async function loadSystemInfo() {
  try {
    const res = await fetch("/api/system/info");
    const data = await res.json();
    systemInfo = data;

    const machineCode = data.license.machine_code || "-";
    document.getElementById("header-machine-code").value = machineCode;
    document.getElementById("modal-machine-code").innerText = machineCode;

    const isVip = data.license.is_vip;
    const badgeContainer = document.getElementById("license-badge-container");
    const limitBadge = document.getElementById("articles-limit-badge");

    if (isVip) {
      badgeContainer.innerHTML = `
        <span class="tool-tag tag-teal">
          <span>${data.license.tier_name || "VIP 会员"}</span>
        </span>
      `;
      if (limitBadge) {
        limitBadge.innerText = "VIP 无限制";
        limitBadge.style.color = "#0d9488";
      }
    } else {
      badgeContainer.innerHTML = `
        <span class="tool-tag tag-amber">
          <span id="license-badge-text">免费体验版</span>
        </span>
      `;
      if (limitBadge) {
        limitBadge.innerText = `体验版限 ${data.license.max_articles_per_crawl} 篇`;
        limitBadge.style.color = "#b08900";
      }
    }
  } catch (err) {
    console.error("加载系统信息失败:", err);
  }
}

function initSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/crawl/events");

  eventSource.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleRealtimeEvent(msg.event, msg.data);
    } catch (e) {}
  };

  eventSource.onerror = () => {
    console.warn("SSE 连接重试中...");
  };
}

function handleRealtimeEvent(eventType, data) {
  if (eventType === "log") {
    appendLog(data.timestamp, data.level, data.message);
  } else if (eventType === "status") {
    updateTaskStatus(data);
  } else if (eventType === "author_info") {
    if (data.name) {
      document.getElementById("stat-author").innerText = data.name;
    }
  } else if (eventType === "article_processed") {
    const item = data.item;
    if (item) {
      const idx = articlesList.findIndex(a => a.group_id === item.group_id);
      if (idx >= 0) {
        articlesList[idx] = item;
      } else {
        articlesList.push(item);
      }
      renderArticlesTable();
      updateStatistics();
    }
  } else if (eventType === "export_ready") {
    appendLog(new Date().toLocaleTimeString(), "success", "所有文章与导出报表已全部就绪！");
    loadArticles();
  }
}

let tableSyncTimer = null;

function updateTaskStatus(state) {
  const statusPill = document.getElementById("task-status-pill");
  const stepText = document.getElementById("progress-step-text");
  const pctText = document.getElementById("progress-pct-text");
  const barFill = document.getElementById("progress-bar-fill");
  const curTitleText = document.getElementById("current-title-text");
  const elapsedText = document.getElementById("elapsed-time-text");
  const btnStart = document.getElementById("btn-start-crawl");
  const btnStop = document.getElementById("btn-stop-crawl");

  const progress = state.progress || 0;
  pctText.innerText = `${progress}%`;
  barFill.style.width = `${progress}%`;

  if (state.elapsed_seconds !== undefined) {
    elapsedText.innerText = `耗时: ${state.elapsed_seconds}s`;
  }

  if (state.current_title) {
    curTitleText.innerText = `当前文章: ${state.current_title}`;
  }

  if (state.state === "running") {
    isTaskRunning = true;
    statusPill.innerText = "RUNNING 采集中";
    statusPill.className = "tool-tag tag-blue";
    btnStart.disabled = true;
    btnStart.style.opacity = "0.5";
    btnStart.style.pointerEvents = "none";
    btnStart.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>采集中...</span>';

    btnStop.disabled = false;
    btnStop.style.background = "#fee2e2";
    btnStop.style.color = "#dc2626";
    btnStop.style.borderColor = "#fca5a5";
    btnStop.style.cursor = "pointer";
    btnStop.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="18" height="18" rx="2"></rect></svg><span>🛑 中止采集</span>';

    if (state.step === "fetching_list") {
      stepText.innerText = "正在滚动加载作者主页文章列表...";
    } else if (state.step === "fetching_details") {
      stepText.innerText = `正在抓取文章正文与排版 (${state.current_index || 0}/${state.total || 0})...`;
    } else {
      stepText.innerText = "采集进行中...";
    }

    if (!tableSyncTimer) {
      tableSyncTimer = setInterval(loadArticles, 2500);
    }

  } else if (state.state === "completed") {
    isTaskRunning = false;
    if (tableSyncTimer) { clearInterval(tableSyncTimer); tableSyncTimer = null; }
    statusPill.innerText = "COMPLETED 完成";
    statusPill.className = "tool-tag tag-teal";
    stepText.innerText = "任务已完成！所有文章已就绪。";
    btnStart.disabled = false;
    btnStart.style.opacity = "1";
    btnStart.style.pointerEvents = "auto";
    btnStart.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>启动采集任务</span>';
    btnStop.disabled = true;
    btnStop.style.background = "var(--bg-subtle)";
    btnStop.style.color = "var(--muted)";
    btnStop.style.borderColor = "var(--border)";
    btnStop.style.cursor = "default";
    btnStop.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="18" height="18" rx="2"></rect></svg><span>停止</span>';
    loadArticles();
  } else if (state.state === "cancelled") {
    isTaskRunning = false;
    if (tableSyncTimer) { clearInterval(tableSyncTimer); tableSyncTimer = null; }
    statusPill.innerText = "CANCELLED 已中止";
    statusPill.className = "tool-tag tag-amber";
    stepText.innerText = "任务已由用户手动中止。";
    btnStart.disabled = false;
    btnStart.style.opacity = "1";
    btnStart.style.pointerEvents = "auto";
    btnStart.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>启动采集任务</span>';
    btnStop.disabled = true;
    btnStop.style.background = "var(--bg-subtle)";
    btnStop.style.color = "var(--muted)";
    btnStop.style.borderColor = "var(--border)";
    btnStop.style.cursor = "default";
    btnStop.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="18" height="18" rx="2"></rect></svg><span>已中止</span>';
    loadArticles();
  } else if (state.state === "failed") {
    isTaskRunning = false;
    if (tableSyncTimer) { clearInterval(tableSyncTimer); tableSyncTimer = null; }
    statusPill.innerText = "FAILED 异常中断";
    statusPill.className = "tool-tag tag-pink";
    stepText.innerText = `执行出错: ${state.error || "网络异常"}`;
    btnStart.disabled = false;
    btnStart.style.opacity = "1";
    btnStart.style.pointerEvents = "auto";
    btnStart.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>启动采集任务</span>';
    btnStop.disabled = true;
    btnStop.style.background = "var(--bg-subtle)";
    btnStop.style.color = "var(--muted)";
    btnStop.style.borderColor = "var(--border)";
    btnStop.style.cursor = "default";
    btnStop.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="18" height="18" rx="2"></rect></svg><span>停止</span>';
    loadArticles();
  }
}

function appendLog(timeStr, level, msg) {
  const terminal = document.getElementById("terminal-logs");
  const entry = document.createElement("div");
  entry.className = "log-entry";

  const levelClass = `log-level-${level || "info"}`;
  entry.innerHTML = `
    <span class="log-time">[${timeStr}]</span>
    <span class="${levelClass}">${msg}</span>
  `;
  terminal.appendChild(entry);
  terminal.scrollTop = terminal.scrollHeight;
}

function clearLogs() {
  document.getElementById("terminal-logs").innerHTML = `
    <div style="color:var(--muted-2);">[日志已清空]</div>
  `;
}

async function startCrawlTask() {
  const url = document.getElementById("input-author-url").value.trim();
  if (!url) {
    alert("请输入头条作者主页链接！");
    return;
  }

  const maxArticlesVal = document.getElementById("input-max-articles").value.trim();
  const maxArticles = maxArticlesVal ? parseInt(maxArticlesVal, 10) : null;
  const fetchContent = document.getElementById("check-fetch-content").checked;
  const downloadImages = document.getElementById("check-download-images").checked;
  const delay = parseFloat(document.getElementById("input-delay").value);

  if (downloadImages && systemInfo && !systemInfo.license.is_vip) {
    if (!confirm("【VIP 会员特权】免费体验版不支持批量下载高清配图。是否直接升级 VIP？")) {
      openActivationModal();
      return;
    }
  }

  try {
    const res = await fetch("/api/crawl/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        author_url: url,
        max_articles: maxArticles,
        fetch_content: fetchContent,
        download_images: downloadImages,
        delay: delay,
        headless: true
      })
    });

    const data = await res.json();
    if (!res.ok) {
      alert(`启动失败: ${data.detail || data.message || "未知错误"}`);
    } else {
      appendLog(new Date().toLocaleTimeString(), "info", "作者采集任务已成功启动！");
    }
  } catch (err) {
    alert(`请求异常: ${err.message}`);
  }
}

async function stopCrawlTask() {
  try {
    const res = await fetch("/api/crawl/stop", { method: "POST" });
    if (res.ok) {
      appendLog(new Date().toLocaleTimeString(), "warning", "已发送中止信号...");
    }
  } catch (err) {}
}

// ================= TAB 3: 热搜雷达 (1:1 XCbot tools-grid) =================
async function loadHotBoard() {
  const grid = document.getElementById("hot-board-grid");
  const timeLabel = document.getElementById("hot-last-updated");
  
  if (timeLabel) timeLabel.innerText = "正在刷新...";

  try {
    const res = await fetch("/api/hot-board");
    const data = await res.json();
    const items = data.items || [];

    if (timeLabel) {
      const now = new Date();
      timeLabel.innerText = `更新于 ${now.toLocaleTimeString()}`;
    }

    if (items.length === 0) {
      grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:36px; color:var(--muted-2);">暂无热榜数据</div>';
      return;
    }

    grid.innerHTML = items.map(item => {
      let rankClass = "hot-rank-n";
      if (item.rank === 1) rankClass = "hot-rank-1";
      else if (item.rank === 2) rankClass = "hot-rank-2";
      else if (item.rank === 3) rankClass = "hot-rank-3";

      let labelTag = item.label ? `<span class="tool-tag tag-pink" style="padding:1px 6px; font-size:10px;">${item.label}</span>` : '';

      return `
        <div class="tool-card" onclick="openHotUrl('${item.url}')">
          <div class="hot-card-top">
            <div style="display:flex; align-items:center; gap:8px;">
              <span class="hot-rank-badge ${rankClass}">${item.rank}</span>
              <span style="font-family:var(--mono); font-size:11px; color:var(--muted);">🔥 ${item.hot_value}</span>
            </div>
            ${labelTag}
          </div>
          <div class="tool-name" style="font-size:13.5px; line-height:1.45;" title="${item.title}">${item.title}</div>
          <div style="display:flex; justify-content:flex-end; gap:6px; margin-top:6px;">
            <button onclick="event.stopPropagation(); sendToOriginalTopic('${encodeURIComponent(item.title)}')" class="action-btn-mini" style="background:#0a0a0a; color:#fff;" title="以此热搜为选题快速写文章">
              AI 写作
            </button>
            <button onclick="event.stopPropagation(); copyText('${item.title}')" class="action-btn-mini" title="复制热搜标题">
              复制选题
            </button>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:36px; color:#d6336c;">加载失败: ${err.message}</div>`;
  }
}

function openHotUrl(url) {
  if (url) window.open(url, "_blank");
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert(`热搜选题【${text}】已复制到剪贴板！`);
  });
}

// 加载文章数据
async function loadArticles() {
  try {
    const res = await fetch("/api/crawl/articles");
    const data = await res.json();
    articlesList = data.articles || [];
    renderArticlesTable();
    updateStatistics();
  } catch (err) {
    console.error("加载文章失败:", err);
  }
}

function updateStatistics() {
  const total = articlesList.length;
  let totalReads = 0;
  let totalLikes = 0;
  let totalComments = 0;

  articlesList.forEach(a => {
    totalReads += parseInt(a.read_count || 0, 10);
    totalLikes += parseInt(a.digg_count || 0, 10);
    totalComments += parseInt(a.comment_count || 0, 10);
  });

  document.getElementById("stat-articles").innerText = `${total} 篇`;
  document.getElementById("stat-reads").innerText = totalReads.toLocaleString();
  document.getElementById("stat-likes").innerText = totalLikes.toLocaleString();
  document.getElementById("stat-comments").innerText = totalComments.toLocaleString();
  document.getElementById("table-count-badge").innerText = `${total} 篇`;
}

function renderArticlesTable() {
  const tbody = document.getElementById("articles-table-body");
  const keyword = document.getElementById("search-input").value.trim().toLowerCase();
  const sortMode = document.getElementById("sort-select").value;

  let filtered = articlesList.filter(a => {
    if (!keyword) return true;
    return (a.title && a.title.toLowerCase().includes(keyword)) ||
           (a.abstract && a.abstract.toLowerCase().includes(keyword));
  });

  if (sortMode === "reads_desc") {
    filtered.sort((a, b) => (b.read_count || 0) - (a.read_count || 0));
  } else if (sortMode === "likes_desc") {
    filtered.sort((a, b) => (b.digg_count || 0) - (a.digg_count || 0));
  } else if (sortMode === "comments_desc") {
    filtered.sort((a, b) => (b.comment_count || 0) - (a.comment_count || 0));
  } else if (sortMode === "time_desc") {
    filtered.sort((a, b) => (b.publish_timestamp || 0) - (a.publish_timestamp || 0));
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align:center; padding:36px; color:var(--muted-2);">
          暂无匹配文章数据
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map((item, idx) => {
    let statusHtml = '<span class="tool-tag tag-gray" style="padding:1px 6px; font-size:10.5px;">待下载</span>';
    if (item.status === "downloaded") {
      statusHtml = '<span class="tool-tag tag-teal" style="padding:1px 6px; font-size:10.5px;">已完成</span>';
    } else if (item.status === "cached") {
      statusHtml = '<span class="tool-tag tag-blue" style="padding:1px 6px; font-size:10.5px;">已缓存</span>';
    } else if (item.status && item.status.startsWith("failed")) {
      statusHtml = '<span class="tool-tag tag-pink" style="padding:1px 6px; font-size:10.5px;">失败</span>';
    }

    const hasLocal = item.local_file ? true : false;

    return `
      <tr>
        <td style="text-align:center; font-family:var(--mono); color:var(--muted);">${idx + 1}</td>
        <td>
          <div style="font-weight:600; color:var(--fg); max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${item.title}">${item.title}</div>
          <div style="font-size:11px; color:var(--muted-2); max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:2px;">${item.abstract || ""}</div>
        </td>
        <td style="text-align:center; font-family:var(--mono); font-size:11px; color:var(--muted);">${item.publish_time || "-"}</td>
        <td style="text-align:right; font-family:var(--mono); font-weight:600; color:#2f6fed;">${(item.read_count || 0).toLocaleString()}</td>
        <td style="text-align:right; font-family:var(--mono); color:#d6336c;">${(item.digg_count || 0).toLocaleString()}</td>
        <td style="text-align:right; font-family:var(--mono); color:#7c4dff;">${(item.comment_count || 0).toLocaleString()}</td>
        <td style="text-align:center;">${statusHtml}</td>
        <td style="text-align:center;">
          <div style="display:flex; align-items:center; justify-content:center; gap:4px;">
            <button onclick='sendToRemix(${JSON.stringify(item).replace(/'/g, "&apos;")})' class="action-btn-mini" style="background:#0a0a0a; color:#fff;" title="将此爆文正文发送到自媒体二创">
              AI 二创
            </button>
            <button onclick="previewArticle('${item.local_file || ''}', '${encodeURIComponent(item.title || '')}', '${item.group_id || ''}', '${item.article_url || ''}')" class="action-btn-mini" title="预览文章 Markdown 正文">
              预览
            </button>
            <a href="${item.article_url}" target="_blank" class="action-btn-mini" title="打开原文">
              原文
            </a>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

// 预览 Markdown 全文 (支持本地秒开与在线极速抓取展示)
async function previewArticle(filename, encodedTitle, groupId = "", articleUrl = "") {
  const title = decodeURIComponent(encodedTitle || "文章详情预览");
  document.getElementById("preview-title").innerText = title;
  const bodyEl = document.getElementById("preview-body");
  bodyEl.innerHTML = '<div style="text-align:center; padding:40px 20px; color:var(--muted); font-size:13px;">正在加载文章完整内容...</div>';
  document.getElementById("preview-modal").style.display = "flex";

  try {
    const fnParam = filename ? encodeURIComponent(filename) : "";
    const gidParam = groupId ? encodeURIComponent(groupId) : "";
    const urlParam = articleUrl ? encodeURIComponent(articleUrl) : "";
    
    const res = await fetch(`/api/crawl/article/content?filename=${fnParam}&group_id=${gidParam}&url=${urlParam}`);
    const data = await res.json();
    
    if (!res.ok || !data.content) {
      bodyEl.innerHTML = `<div style="color:#d6336c; text-align:center; padding:30px;">读取失败: ${data.detail || "无法读取该文章内容"}</div>`;
      return;
    }
    
    bodyEl.innerHTML = marked.parse(data.content || "");
  } catch (err) {
    bodyEl.innerHTML = `<div style="color:#d6336c; text-align:center; padding:30px;">请求异常: ${err.message}</div>`;
  }
}

function closePreviewModal() {
  document.getElementById("preview-modal").style.display = "none";
}

// 会员激活 Modal
function openActivationModal() {
  document.getElementById("activation-modal").style.display = "flex";
  document.getElementById("activation-msg").style.display = "none";
}

function closeActivationModal() {
  document.getElementById("activation-modal").style.display = "none";
}

function copyMachineCode() {
  const mc = document.getElementById("modal-machine-code").innerText.trim();
  if (mc && mc !== "-") {
    navigator.clipboard.writeText(mc).then(() => {
      alert(`机器码 [${mc}] 已复制到剪贴板！\n请将该码发送给开发者以获取您的 VIP 激活码。`);
    });
  }
}

async function submitActivation() {
  const key = document.getElementById("input-license-key").value.trim();
  const msgEl = document.getElementById("activation-msg");

  if (!key) {
    msgEl.innerText = "请输入激活码！";
    msgEl.style.color = "#d6336c";
    msgEl.style.display = "block";
    return;
  }

  msgEl.innerText = "正在验证授权...";
  msgEl.style.color = "var(--muted)";
  msgEl.style.display = "block";

  try {
    const res = await fetch("/api/activation/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ license_key: key })
    });

    const data = await res.json();
    if (!res.ok) {
      msgEl.innerText = `激活失败: ${data.detail || "激活码无效"}`;
      msgEl.style.color = "#d6336c";
    } else {
      msgEl.innerText = `🎉 恭喜！${data.message}`;
      msgEl.style.color = "#0d9488";
      msgEl.style.fontWeight = "bold";
      setTimeout(() => {
        closeActivationModal();
        loadSystemInfo();
      }, 1200);
    }
  } catch (err) {
    msgEl.innerText = `网络异常: ${err.message}`;
    msgEl.style.color = "#d6336c";
  }
}

function downloadExport(fmt) {
  if (fmt === "zip" && systemInfo && !systemInfo.license.is_vip) {
    alert("【VIP 专属特权】免费体验版不支持一键 Zip 打包导出全部文章及图片。\n请点击顶部【会员激活】升级 VIP！");
    openActivationModal();
    return;
  }
  window.open(`/api/export/${fmt}`, "_blank");
}

async function openLocalFolder() {
  try {
    const res = await fetch("/api/system/open-folder", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(`无法打开文件夹: ${data.detail}`);
    }
  } catch (err) {
    alert(`请求异常: ${err.message}`);
  }
}

function fillSampleUrl() {
  if (systemInfo && systemInfo.default_url) {
    document.getElementById("input-author-url").value = systemInfo.default_url;
  }
}

function updateDelayText(val) {
  document.getElementById("delay-val-text").innerText = `${val}s`;
}

function copyContact(val, name) {
  navigator.clipboard.writeText(val).then(() => {
    alert(`已复制 ${name}：${val}`);
  }).catch(() => {
    prompt(`请手动复制 ${name}：`, val);
  });
}

// ================= 远程更新与云端推送逻辑 =================
let latestUpdateData = null;
let updatePollTimer = null;
let hasAutoPromptedUpdate = false; // 避免单次会话重复自动弹窗打扰

async function fetchUpdateCheck(isManualClick = false) {
  try {
    const res = await fetch("/api/system/check-update");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    latestUpdateData = data;

    // 1. 更新顶部版本号
    const badgeText = document.getElementById("update-badge-text");
    const pulseDot = document.getElementById("update-pulse-dot");
    const updateBtn = document.getElementById("btn-check-update");

    if (badgeText) {
      badgeText.innerText = `v${data.current_version}`;
    }

    if (data.has_update) {
      if (pulseDot) pulseDot.style.display = "inline-block";
      if (updateBtn) {
        updateBtn.classList.add("has-new");
        updateBtn.title = `✨ 发现新版本 v${data.latest_version}，点击立即更新！`;
      }

      // 🌟 有更新时直接弹出更新提示弹窗（启动或手动触发）
      if (!hasAutoPromptedUpdate || isManualClick) {
        hasAutoPromptedUpdate = true;
        openUpdateModal();
      }
    } else {
      if (pulseDot) pulseDot.style.display = "none";
      if (updateBtn) {
        updateBtn.classList.remove("has-new");
        updateBtn.title = "已是最新版本";
      }
      // 手动点击且无更新时弹窗告知
      if (isManualClick) {
        openUpdateModal();
      }
    }
  } catch (err) {
    console.error("检查更新失败:", err);
    if (isManualClick) {
      openUpdateModal();
      const latVerEl = document.getElementById("modal-latest-version");
      const changeListEl = document.getElementById("update-changelog-list");
      if (latVerEl) latVerEl.innerText = "网络异常";
      if (changeListEl) changeListEl.innerHTML = `<div style="color:#d6336c;">• 检查更新失败: ${err.message}</div>`;
    }
  }
}

function openUpdateModal() {
  const modal = document.getElementById("update-modal");
  if (!modal) return;
  modal.style.display = "flex";

  const progressWrap = document.getElementById("update-progress-wrap");
  const msgEl = document.getElementById("update-msg");

  if (progressWrap) progressWrap.style.display = "none";
  if (msgEl) msgEl.style.display = "none";

  if (!latestUpdateData) {
    const latVerEl = document.getElementById("modal-latest-version");
    const changeListEl = document.getElementById("update-changelog-list");
    if (latVerEl) latVerEl.innerText = "正在查询...";
    if (changeListEl) changeListEl.innerHTML = "正在连接云端服务器...";
    fetchUpdateCheck(true).then(() => renderUpdateModalContent());
  } else {
    renderUpdateModalContent();
  }
}

function renderUpdateModalContent() {
  if (!latestUpdateData) return;
  const d = latestUpdateData;

  const curVerEl = document.getElementById("modal-cur-version");
  const latVerEl = document.getElementById("modal-latest-version");
  const changeListEl = document.getElementById("update-changelog-list");
  const titleEl = document.getElementById("update-modal-title");
  const btnGroup = document.getElementById("update-btn-group");
  const calloutEl = document.getElementById("update-announcement-callout");
  const calloutText = document.getElementById("update-announcement-callout-text");

  if (curVerEl) curVerEl.innerText = `v${d.current_version}`;
  if (latVerEl) {
    latVerEl.innerText = `v${d.latest_version}`;
    latVerEl.style.color = d.has_update ? "#0d9488" : "#64748b";
  }

  // 广播公告
  if (d.announcement && d.announcement.content && calloutEl && calloutText) {
    calloutText.innerText = d.announcement.content;
    calloutEl.style.display = "block";
  } else if (calloutEl) {
    calloutEl.style.display = "none";
  }

  if (d.has_update) {
    if (titleEl) titleEl.innerHTML = `<span>🚀</span> <span>发现新版本 v${d.latest_version}</span>`;
    if (changeListEl) {
      if (d.changelog && d.changelog.length > 0) {
        changeListEl.innerHTML = d.changelog.map(item => `<div>${item}</div>`).join("");
      } else {
        changeListEl.innerHTML = `<div>• 发现新版本 v${d.latest_version}，包含重要性能优化与功能升级。</div>`;
      }
    }

    if (btnGroup) {
      btnGroup.innerHTML = `
        <button id="btn-cancel-update" onclick="closeUpdateModal()" class="telegram-btn" style="flex:1; justify-content:center; padding:10px; font-size:13px; background:#f1f5f9; border:1px solid var(--border); color:var(--fg);">
          稍后更新
        </button>
        <button id="btn-auto-upgrade" onclick="startAutoUpgrade()" class="shop-btn" style="flex:1.5; justify-content:center; padding:10px; font-size:13px; background:#0f1013; color:#fff;">
          立即更新
        </button>
      `;
    }
  } else {
    if (titleEl) titleEl.innerHTML = `<span>🛡️</span> <span>云端版本检测</span>`;
    if (changeListEl) {
      changeListEl.innerHTML = `<div>✓ 当前已是最新版本 (v${d.current_version})，运行稳定，无需更新。</div>`;
    }
    if (btnGroup) {
      btnGroup.innerHTML = `
        <button onclick="closeUpdateModal()" class="shop-btn" style="flex:1; justify-content:center; padding:10px; font-size:13px; background:#0f1013; color:#fff;">
          我知道了
        </button>
      `;
    }
  }
}

function closeUpdateModal() {
  const modal = document.getElementById("update-modal");
  if (modal) modal.style.display = "none";
  if (updatePollTimer) {
    clearInterval(updatePollTimer);
    updatePollTimer = null;
  }
}

function manualDownloadUpdate() {
  if (latestUpdateData && latestUpdateData.download_url) {
    window.open(latestUpdateData.download_url, "_blank");
  }
}

async function startAutoUpgrade() {
  if (!latestUpdateData || !latestUpdateData.download_url) {
    alert("未找到有效的云端下载地址！");
    return;
  }

  const dlUrl = latestUpdateData.download_url;
  const isDirectFile = dlUrl.endsWith(".exe") || dlUrl.endsWith(".zip") || dlUrl.endsWith(".7z") || dlUrl.includes("/releases/download/");
  if (!isDirectFile) {
    // 若配置的是网页链接，直接在默认浏览器中拉起下载页面
    window.open(dlUrl, "_blank");
    closeUpdateModal();
    return;
  }

  const btnAuto = document.getElementById("btn-auto-upgrade");
  const progressWrap = document.getElementById("update-progress-wrap");
  const msgEl = document.getElementById("update-msg");

  if (btnAuto) {
    btnAuto.disabled = true;
    btnAuto.innerText = "正在准备更新...";
  }
  if (progressWrap) progressWrap.style.display = "block";
  if (msgEl) msgEl.style.display = "none";

  try {
    const res = await fetch("/api/system/download-update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ download_url: latestUpdateData.download_url })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "启动下载失败");
    }

    // 轮询下载进度
    if (updatePollTimer) clearInterval(updatePollTimer);
    updatePollTimer = setInterval(pollUpdateProgress, 400);
  } catch (err) {
    if (msgEl) {
      msgEl.innerText = `下载异常: ${err.message}`;
      msgEl.style.color = "#d6336c";
      msgEl.style.display = "block";
    }
    if (btnAuto) {
      btnAuto.disabled = false;
      btnAuto.innerText = "重试升级";
    }
  }
}

async function pollUpdateProgress() {
  try {
    const res = await fetch("/api/system/update-progress");
    if (!res.ok) return;
    const st = await res.json();

    const bar = document.getElementById("update-progress-bar");
    const percentEl = document.getElementById("update-progress-percent");
    const speedEl = document.getElementById("update-speed-text");
    const sizeEl = document.getElementById("update-size-text");
    const statusEl = document.getElementById("update-progress-status");
    const msgEl = document.getElementById("update-msg");

    const pct = Math.min(st.progress || 0, 100);
    if (bar) bar.style.width = `${pct}%`;
    if (percentEl) percentEl.innerText = `${pct}%`;
    if (speedEl) speedEl.innerText = `${st.speed_kb || 0} KB/s`;
    
    const dlMb = ((st.downloaded_bytes || 0) / (1024 * 1024)).toFixed(1);
    const totMb = ((st.total_bytes || 0) / (1024 * 1024)).toFixed(1);
    if (sizeEl) sizeEl.innerText = `${dlMb} / ${totMb} MB`;

    if (st.status === "completed") {
      clearInterval(updatePollTimer);
      updatePollTimer = null;
      if (statusEl) statusEl.innerText = "下载完成，正在自动安装并重启...";
      if (msgEl) {
        msgEl.innerText = "🎉 下载完成！程序正在应用补丁并重启，请稍候...";
        msgEl.style.color = "#0d9488";
        msgEl.style.display = "block";
      }
      
      // 触发应用更新
      setTimeout(async () => {
        try {
          await fetch("/api/system/apply-update", { method: "POST" });
        } catch (e) {
          // 预期内服务端即将关闭重启
        }
      }, 800);
    } else if (st.status === "error") {
      clearInterval(updatePollTimer);
      updatePollTimer = null;
      if (statusEl) statusEl.innerText = "下载失败";
      if (msgEl) {
        msgEl.innerText = `错误: ${st.error || "网络中断"}`;
        msgEl.style.color = "#d6336c";
        msgEl.style.display = "block";
      }
      const btnAuto = document.getElementById("btn-auto-upgrade");
      if (btnAuto) {
        btnAuto.disabled = false;
        btnAuto.innerText = "重试升级";
      }
    }
  } catch (err) {
    console.error("查询更新进度失败:", err);
  }
}

