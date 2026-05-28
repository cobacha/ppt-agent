"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchStyles, importUrl, StylePreset } from "@/lib/api";
import { useHistory } from "@/hooks/useHistory";
import { useGenerationContext } from "@/context/GenerationContext";
import TemplateCard from "@/components/TemplateCard";
import GenerationFloat from "@/components/GenerationFloat";

const SLIDE_COUNT_OPTIONS = [
  { value: "", label: "自动页数" },
  { value: "5-8", label: "5-8 页" },
  { value: "8-12", label: "8-12 页" },
  { value: "12-15", label: "12-15 页" },
  { value: "15-20", label: "15-20 页" },
  { value: "20-30", label: "20-30 页" },
  { value: "30-40", label: "30-40 页" },
];

const EXAMPLES = [
  { label: "产品发布", content: "# AI Assistant 3.0 发布\n\n## 核心亮点\n- 推理速度提升 40%\n- 支持 128K 上下文\n- 多模态理解能力\n\n## 技术架构\n- 混合专家模型 (MoE)\n- 动态量化推理\n- 端云协同部署\n\n## 应用场景\n- 智能助手\n- 文档理解\n- 代码生成\n\n## 未来规划\n- 开源社区建设\n- 行业垂直模型\n- Agent 能力增强" },
  { label: "季度汇报", content: "# Q1 2025 业务回顾\n\n## 核心指标\n- 月活用户增长 25%\n- 营收同比增长 35%\n- 客户满意度提升 12%\n\n## 重点项目\n- 产品 2.0 发布\n- 多语言支持\n- 性能优化\n\n## 挑战与应对\n- 基础设施成本优化\n- 用户留存提升\n- 产品差异化\n\n## 下季度计划\n- API 平台发布\n- 核心功能迭代\n- 开发者生态建设" },
  { label: "技术分享", content: "# Transformer 架构演进\n\n## 从注意力到一切\n- Self-Attention 机制回顾\n- Multi-Head Attention 的直觉\n\n## 关键变体\n- GPT: 自回归生成\n- BERT: 双向理解\n- T5: 统一框架\n\n## 效率革命\n- Flash Attention\n- Sparse Attention\n- Linear Attention\n\n## 未来方向\n- State Space Models\n- 混合架构\n- 端侧部署挑战" },
];

function getTimeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins}分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}天前`;
  return new Date(isoDate).toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function estimateSlideCount(content: string): number {
  if (!content.trim()) return 0;
  const MIN_CONTENT_SLIDES = 5;
  const EXTRA = 2; // cover + closing
  const headings = (content.match(/^#{1,3}\s/gm) || []).length;
  if (headings >= 3) return Math.max(MIN_CONTENT_SLIDES, headings) + EXTRA;
  const paragraphs = content.split(/\n\s*\n/).filter(p => p.trim()).length;
  return Math.max(MIN_CONTENT_SLIDES, paragraphs) + EXTRA;
}

export default function Home() {
  const router = useRouter();
  const { generate: ctxGenerate, state: genState, onDone, genId } = useGenerationContext();
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [selectedStyle, setSelectedStyle] = useState<string>("");
  const [content, setContent] = useState("");
  const [slideCountPref, setSlideCountPref] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "url">("text");
  const [urlInput, setUrlInput] = useState("");
  const [urlLoading, setUrlLoading] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [styleError, setStyleError] = useState<string | null>(null);
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const { history, deleteItem: deleteHistoryItem, reload: reloadHistory } = useHistory();

  useEffect(() => {
    fetchStyles().then((data) => {
      setPresets(data.presets);
      if (data.presets.length > 0 && !selectedStyle) {
        setSelectedStyle(data.presets[0].id);
      }
    }).catch(() => {
      setStyleError("无法加载风格列表，请检查后端服务是否正常运行");
    });
  }, []);

  // Reload history when background generation completes
  useEffect(() => onDone(() => reloadHistory()), [onDone, reloadHistory]);

  // Auto-save draft to localStorage
  useEffect(() => {
    const saved = localStorage.getItem("ppt-draft");
    if (saved) {
      try {
        const draft = JSON.parse(saved);
        if (draft.content) setContent(draft.content);
        if (draft.style) setSelectedStyle(draft.style);
        if (draft.language) setLanguage(draft.language);
        if (draft.aspectRatio) setAspectRatio(draft.aspectRatio);
        if (draft.slideCountPref) setSlideCountPref(draft.slideCountPref);
      } catch {}
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (content.trim()) {
        localStorage.setItem("ppt-draft", JSON.stringify({ content, style: selectedStyle, language, aspectRatio, slideCountPref }));
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [content, selectedStyle, language, aspectRatio, slideCountPref]);


  const handleImportUrl = async () => {
    if (!urlInput.trim()) return;
    setUrlLoading(true);
    setUrlError(null);
    try {
      const result = await importUrl(urlInput.trim());
      setContent(result.content);
      setInputMode("text");
      setUrlInput("");
    } catch (err: unknown) {
      setUrlError(err instanceof Error ? err.message : "导入失败");
    } finally {
      setUrlLoading(false);
    }
  };

  const handleGenerate = () => {
    if (!content.trim() || !selectedStyle) return;
    localStorage.removeItem("ppt-draft");
    // Keep sessionStorage as fallback for page refresh
    sessionStorage.setItem("ppt-agent-content", content);
    sessionStorage.setItem("ppt-agent-style", selectedStyle);
    sessionStorage.setItem("ppt-agent-aspect-ratio", aspectRatio);
    if (slideCountPref) {
      sessionStorage.setItem("ppt-agent-slide-count", slideCountPref);
    } else {
      sessionStorage.removeItem("ppt-agent-slide-count");
    }
    // Start generation in context (persists across navigation)
    const finalContent = slideCountPref
      ? `${content}\n\n[页数要求: ${slideCountPref} 页]`
      : content;
    ctxGenerate(finalContent, selectedStyle, language, aspectRatio);
    router.push("/editor");
  };

  const handleHistoryClick = (id: string) => {
    router.push(`/editor?history=${id}`);
  };

  const selectedPreset = presets.find(p => p.id === selectedStyle);
  // Filter out the active session's DB record to avoid duplication
  const recentHistory = history.filter(h => !genId || h.id !== genId).slice(0, 5);
  const hasActiveSession = genState.generating;

  return (
    <main className="flex-1 flex flex-col items-center min-h-screen p-6 pt-20 relative">
      <a
        href="/settings"
        className="absolute top-5 right-5 flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 bg-white border border-gray-200 hover:border-gray-300 rounded-lg shadow-sm transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992.014.378.16.75.452.99l1.005.828c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.214 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.01c-.008-.378-.158-.75-.45-.99l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>
        设置
      </a>

      {/* Centered header */}
      <header className="text-center mb-8">
        <h1 className="text-3xl font-bold">PPT Agent</h1>
        <p className="text-gray-400 mt-1 text-sm">描述你的内容，AI 生成专业演示文稿</p>
      </header>

      {/* Example quick-start chips */}
      <div className="flex gap-2 mb-4 flex-wrap justify-center items-center">
        <span className="text-xs text-gray-400">试试：</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            onClick={() => setContent(ex.content)}
            className="text-xs px-3 py-1 rounded-full border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-all"
          >
            {ex.label}
          </button>
        ))}
      </div>

      {/* Main input card */}
      <div className="w-full max-w-2xl">
        <div className="border border-gray-200 rounded-2xl p-4 shadow-sm bg-white">
          {/* Input mode toggle */}
          <div className="flex items-center gap-1 mb-3">
            <button
              onClick={() => setInputMode("text")}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                inputMode === "text"
                  ? "bg-blue-100 text-blue-700 font-medium"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              }`}
            >
              文本
            </button>
            <button
              onClick={() => setInputMode("url")}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                inputMode === "url"
                  ? "bg-blue-100 text-blue-700 font-medium"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              }`}
            >
              URL 导入
            </button>
          </div>

          {inputMode === "text" ? (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="粘贴演示文稿内容 — 支持 Markdown、大纲或纯文本..."
              aria-label="演示文稿内容输入"
              className="w-full h-28 text-sm resize-none border-0 focus:outline-none font-mono placeholder:font-sans"
            />
          ) : (
            <div className="h-28 flex flex-col justify-center gap-3">
              <div className="flex gap-2">
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => { setUrlInput(e.target.value); setUrlError(null); }}
                  placeholder="输入文章 URL，自动提取内容..."
                  className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400"
                  onKeyDown={(e) => { if (e.key === "Enter") handleImportUrl(); }}
                />
                <button
                  onClick={handleImportUrl}
                  disabled={!urlInput.trim() || urlLoading}
                  className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {urlLoading ? "导入中..." : "导入"}
                </button>
              </div>
              {urlError && (
                <p className="text-xs text-red-500">{urlError}</p>
              )}
              <p className="text-[11px] text-gray-400">支持博客、文档、新闻等网页链接，自动提取正文内容</p>
            </div>
          )}

          {/* Bottom bar: controls + generate button */}
          <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-gray-100">
            {/* Selected style indicator */}
            {selectedPreset && (
              <span className="flex items-center gap-1.5 text-xs text-gray-500">
                <span
                  className="w-3 h-3 rounded-sm"
                  style={{ background: selectedPreset.colors?.bg_primary || selectedPreset.colors?.accent || '#666' }}
                />
                {selectedPreset.name}
              </span>
            )}
            {!selectedPreset && (
              <span className="text-xs text-amber-500">↓ 请选择风格</span>
            )}

            {/* Slide count */}
            <select
              value={slideCountPref}
              onChange={(e) => setSlideCountPref(e.target.value)}
              className="text-xs text-gray-600 border border-gray-200 rounded-lg px-2 py-1.5 hover:border-gray-300 transition-colors"
            >
              {SLIDE_COUNT_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>

            {/* Language */}
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as "zh" | "en")}
              className="text-xs text-gray-600 border border-gray-200 rounded-lg px-2 py-1.5 hover:border-gray-300 transition-colors"
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>

            {/* Aspect Ratio */}
            <select
              value={aspectRatio}
              onChange={(e) => setAspectRatio(e.target.value)}
              className="text-xs text-gray-600 border border-gray-200 rounded-lg px-2 py-1.5 hover:border-gray-300 transition-colors"
            >
              <option value="16:9">16:9 宽屏</option>
              <option value="4:3">4:3 标准</option>
              <option value="16:10">16:10</option>
              <option value="1:1">1:1 方形</option>
            </select>

            {/* Content stats + estimated page count */}
            {content.trim() && (
              <span className="text-[11px] text-gray-400">
                {content.length > 5000
                  ? <span className="text-amber-500">{content.length.toLocaleString()}字 · 内容较长</span>
                  : `${content.length.toLocaleString()}字`}
                {" · ~"}{estimateSlideCount(content)} 页
              </span>
            )}

            {/* Spacer pushes button to end */}
            <div className="flex-1" />

            <button
              onClick={handleGenerate}
              disabled={!content.trim() || !selectedStyle}
              title={!content.trim() ? "请先输入内容" : !selectedStyle ? "请选择一个风格" : undefined}
              className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              生成 →
            </button>
          </div>
        </div>
      </div>

      {/* Style grid — wider container for bigger cards */}
      <section className="w-full max-w-5xl mt-8">
        <h2 className="text-sm font-semibold text-gray-500 mb-3">
          选择风格 <span className="font-normal text-gray-400">（{presets.length} 种）</span>
        </h2>
        {styleError && (
          <p className="text-sm text-red-500 mb-3">{styleError}</p>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {presets.map((preset) => (
            <TemplateCard
              key={preset.id}
              preset={preset}
              selected={selectedStyle === preset.id}
              onClick={() => setSelectedStyle(preset.id)}
            />
          ))}
        </div>
      </section>

      {/* History + Current session */}
      <div className="w-full max-w-5xl">
        {(hasActiveSession || recentHistory.length > 0) && (
          <div className="mt-10">
            <h3 className="text-xs font-semibold text-gray-500 mb-3 px-1">最近生成</h3>
            <div className="flex gap-4 overflow-x-auto pb-3 snap-x snap-mandatory">
              {/* Current active session */}
              {hasActiveSession && (
                <button
                  onClick={() => router.push("/editor")}
                  className={`group snap-start shrink-0 w-[260px] text-left rounded-xl border overflow-hidden transition-all hover:shadow-lg ${
                    genState.generating
                      ? "border-blue-200 bg-gradient-to-b from-blue-50 to-white"
                      : "border-gray-200 bg-white hover:border-blue-300"
                  }`}
                >
                  <div className="relative aspect-[16/10] bg-gray-900/[0.02] overflow-hidden">
                    {genState.slides[0]?.html ? (
                      <iframe
                        srcDoc={`<!DOCTYPE html><html><head><style>html,body{margin:0;padding:0;overflow:hidden;height:100%;pointer-events:none;}</style></head><body>${genState.slides[0].html}</body></html>`}
                        className="w-full h-full border-0 pointer-events-none"
                        sandbox=""
                        tabIndex={-1}
                        loading="lazy"
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50">
                        <span className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                      </div>
                    )}
                    <span className={`absolute top-2 right-2 text-[10px] font-semibold px-2 py-0.5 rounded-md backdrop-blur-sm ${
                      genState.generating
                        ? "bg-blue-500/90 text-white"
                        : "bg-white/90 text-green-600 border border-green-200"
                    }`}>
                      {genState.generating
                        ? (genState.slides.length === 0 ? "构思中..." : "生成中...")
                        : "编辑中"}
                    </span>
                    {genState.generating && genState.progress && genState.progress.total > 0 && (
                      <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/5">
                        <div className="h-full bg-blue-500 transition-all duration-700" style={{ width: `${(genState.progress.current / genState.progress.total) * 100}%` }} />
                      </div>
                    )}
                  </div>
                  <div className="px-3 py-2.5">
                    <p className="text-[13px] font-semibold text-gray-800 truncate group-hover:text-blue-700 transition-colors">
                      {genState.title || "未命名演示文稿"}
                    </p>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {genState.slides.length > 0
                        ? `${genState.slides.length} 页`
                        : "正在构思"}
                      {genState.generating && genState.progress && genState.progress.total > 0
                        ? ` · ${genState.progress.current}/${genState.progress.total}`
                        : genState.generating ? "" : " · 点击继续编辑"}
                    </p>
                  </div>
                </button>
              )}
              {/* Saved history */}
              {recentHistory.map((entry) => {
                const preset = presets.find((p) => p.id === entry.style);
                const displayStyle = preset?.name || entry.style;
                const timeAgo = getTimeAgo(entry.created_at);
                return (
                  <div key={entry.id} className="group relative snap-start shrink-0 w-[260px]">
                    <button
                      onClick={() => handleHistoryClick(entry.id)}
                      className="w-full text-left rounded-xl border border-gray-200 bg-white overflow-hidden hover:border-blue-300 hover:shadow-lg transition-all"
                    >
                      <div className="relative aspect-[16/10] bg-gray-50 overflow-hidden">
                        {entry.first_slide_html ? (
                          <iframe
                            srcDoc={`<!DOCTYPE html><html><head><style>html,body{margin:0;padding:0;overflow:hidden;height:100%;pointer-events:none;}</style></head><body>${entry.first_slide_html}</body></html>`}
                            className="w-full h-full border-0 pointer-events-none"
                            sandbox=""
                            tabIndex={-1}
                            loading="lazy"
                          />
                        ) : (
                          <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
                            <div className="w-10 h-7 rounded bg-gray-200/80" />
                          </div>
                        )}
                        <span className={`absolute top-2 right-2 text-[10px] font-medium px-1.5 py-0.5 rounded-md backdrop-blur-sm ${
                          entry.status === "generating"
                            ? "bg-amber-500/90 text-white"
                            : entry.status === "failed"
                            ? "bg-red-500/90 text-white"
                            : "bg-white/90 text-gray-500 border border-gray-100"
                        }`}>
                          {entry.status === "generating"
                            ? "中断"
                            : entry.status === "failed"
                            ? "失败"
                            : `${entry.slide_count}页`}
                        </span>
                      </div>
                      <div className="px-3 py-2.5">
                        <p className="text-[13px] font-semibold text-gray-800 truncate group-hover:text-blue-700 transition-colors">
                          {entry.title || entry.content.slice(0, 30)}
                        </p>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-[10px] font-medium text-blue-600/80">{displayStyle}</span>
                          <span className="text-[10px] text-gray-300">·</span>
                          <span className="text-[10px] text-gray-400">{timeAgo}</span>
                        </div>
                      </div>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("确定删除这份演示文稿吗？")) {
                          deleteHistoryItem(entry.id);
                        }
                      }}
                      className="absolute top-1.5 left-1.5 w-6 h-6 rounded-full bg-black/60 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
                      title="删除"
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <GenerationFloat />
    </main>
  );
}
