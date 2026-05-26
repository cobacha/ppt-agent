"use client";

import { Suspense, useEffect, useRef, useCallback, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useGenerationContext } from "@/context/GenerationContext";
import { useHistory } from "@/hooks/useHistory";
import { fetchHistoryDetail, fetchStyles, StylePreset } from "@/lib/api";
import Toolbar from "@/components/Toolbar";
import SlideList from "@/components/SlideList";
import ContentEditor from "@/components/ContentEditor";
import SlidePreview from "@/components/SlidePreview";
import GeneratingView from "@/components/GeneratingView";
import PresenterMode from "@/components/PresenterMode";

export default function EditorPageWrapper() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center"><p className="text-gray-400">加载中...</p></div>}>
      <EditorPage />
    </Suspense>
  );
}

function EditorPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    state,
    genId,
    generate,
    regenSlide,
    setActiveSlide,
    updateSlideHtml,
    moveSlide,
    deleteSlide,
    insertSlide,
    previewFull,
    doExport,
    doExportPdf,
    doExportPptx,
    pdfExporting,
    layouts,
    undo,
    canUndo,
    loadSlides,
    cancel,
    setTitle,
    onDone,
    recoverActiveGeneration,
    continueGeneration,
  } = useGenerationContext();
  const { saveToHistory } = useHistory();
  const [toast, setToast] = useState<string | null>(null);
  const [presenting, setPresenting] = useState(false);
  const [stylePresets, setStylePresets] = useState<StylePreset[]>([]);

  useEffect(() => {
    fetchStyles().then((data) => setStylePresets(data.presets));
  }, []);
  const genStartRef = useRef<number>(0);

  const hasStarted = useRef(false);

  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;

    const historyId = searchParams.get("history");
    if (historyId) {
      fetchHistoryDetail(historyId).then((detail) => {
        loadSlides(detail.slides, detail.style, detail.title);
        // Store in sessionStorage for "regenerate all" to work
        sessionStorage.setItem("ppt-agent-content", detail.content);
        sessionStorage.setItem("ppt-agent-style", detail.style);
      }).catch(() => {
        router.push("/");
      });
      return;
    }

    // If context already has generation active (started from home page), just watch it
    if (state.generating || state.slides.length > 0) {
      genStartRef.current = Date.now();
      return;
    }

    // Try recovering from DB (handles page refresh during generation)
    recoverActiveGeneration().then((recovered) => {
      if (recovered) return;
      // Fallback: page refresh or direct URL access — use sessionStorage
      const content = sessionStorage.getItem("ppt-agent-content");
      const style = sessionStorage.getItem("ppt-agent-style");
      if (!content || !style) {
        router.push("/");
        return;
      }
      genStartRef.current = Date.now();
      generate(content, style);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save to history when generation completes (via context onDone event)
  useEffect(() => {
    return onDone(async (event) => {
      const historyId = await saveToHistory({
        style: event.style,
        content: event.content,
        slides: event.slides,
        gen_id: event.gen_id,
        title: event.title,
      });
      if (historyId) {
        window.history.replaceState(null, "", `/editor?history=${historyId}`);
      }
      if (genStartRef.current) {
        const elapsed = Math.round((Date.now() - genStartRef.current) / 1000);
        const avgScore = event.slides.reduce((sum, s) => sum + s.quality_score, 0) / event.slides.length;
        setToast(`${event.slides.length} 页生成完成 · ${elapsed}秒 · 平均质量 ${avgScore.toFixed(0)}/100`);
        setTimeout(() => setToast(null), 5000);
      }
    });
  }, [onDone, saveToHistory]);

  const handleRegenerateAll = () => {
    const content = sessionStorage.getItem("ppt-agent-content");
    const style = sessionStorage.getItem("ppt-agent-style");
    if (!content || !style) return;
    if (!confirm(`确定重新生成全部 ${state.slides.length} 页吗？当前编辑将丢失。`)) return;
    generate(content, style);
  };

  const handleRemixStyle = (styleId: string) => {
    const content = sessionStorage.getItem("ppt-agent-content");
    if (!content) return;
    if (!confirm(`切换主题将重新生成全部 ${state.slides.length} 页，确定吗？`)) return;
    sessionStorage.setItem("ppt-agent-style", styleId);
    genStartRef.current = Date.now();
    generate(content, styleId);
  };

  const handleRetryFailed = async () => {
    const failedIndices = state.slides
      .map((s, i) => (s.html === "__FAILED__" ? i : -1))
      .filter((i) => i >= 0);
    for (const idx of failedIndices) {
      const slide = state.slides[idx];
      const content = slide.detailed_content || slide.bullets?.join("\n") || slide.title;
      await regenSlide(idx, content, "auto");
    }
  };

  const incompleteSlides = state.slides.filter(s => !s.html || s.html === "__FAILED__");
  const hasIncomplete = !state.generating && incompleteSlides.length > 0;

  const handleContinueGeneration = () => {
    const emptyIndices = state.slides
      .map((s, i) => (!s.html || s.html === "__FAILED__" ? i : -1))
      .filter((i) => i >= 0);
    if (emptyIndices.length === 0) return;
    continueGeneration(emptyIndices);
  };

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable;

      // Ctrl+Z / Cmd+Z for undo (works even in inputs)
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        undo();
        return;
      }

      // Skip other shortcuts if focused on input
      if (isInput) return;

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (state.activeIndex > 0) {
          setActiveSlide(state.activeIndex - 1);
        }
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        if (state.activeIndex < state.slides.length - 1) {
          setActiveSlide(state.activeIndex + 1);
        }
      }
    },
    [state.activeIndex, state.slides.length, setActiveSlide, undo]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const activeSlide = state.slides[state.activeIndex];


  if (state.error && state.slides.length === 0) {
    const errorMap: Record<string, { title: string; tip: string }> = {
      "rate limit": { title: "请求过于频繁", tip: "请等待 30 秒后重试" },
      "429": { title: "请求过于频繁", tip: "请等待 30 秒后重试" },
      "timeout": { title: "生成超时", tip: "内容较长时可能需要更多时间，可尝试减少内容量" },
      "fetch": { title: "网络连接失败", tip: "请检查网络连接和后端服务是否正常运行" },
      "500": { title: "服务器内部错误", tip: "这通常是暂时性的，请稍后重试" },
    };
    const matched = Object.entries(errorMap).find(([key]) =>
      state.error!.toLowerCase().includes(key.toLowerCase())
    );
    const errorInfo = matched?.[1] || { title: "生成失败", tip: "请检查输入内容格式是否正确" };

    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-sm">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-red-100 flex items-center justify-center">
            <svg className="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-900 mb-1">{errorInfo.title}</h2>
          <p className="text-sm text-gray-500 mb-1">{state.error}</p>
          <p className="text-xs text-gray-400 mb-6">{errorInfo.tip}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={handleRegenerateAll}
              className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              重试
            </button>
            <button
              onClick={() => router.push("/")}
              className="px-5 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50 transition-colors"
            >
              返回首页
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (state.slides.length === 0 && !state.error) {
    return <GeneratingView thinking={state.thinking} onCancel={() => { cancel(); router.push("/"); }} />;
  }

  return (
    <div className="flex-1 flex flex-col h-screen">
      <Toolbar
        slideCount={state.slides.length}
        activeIndex={state.activeIndex}
        onExport={doExport}
        onExportPdf={doExportPdf}
        onExportPptx={doExportPptx}
        onPreview={previewFull}
        pdfExporting={pdfExporting}
        onRegenerateAll={handleRegenerateAll}
        onMoveUp={() => moveSlide(state.activeIndex, state.activeIndex - 1)}
        onMoveDown={() => moveSlide(state.activeIndex, state.activeIndex + 1)}
        onDelete={() => {
          if (window.confirm("确定要删除此页吗？")) {
            deleteSlide(state.activeIndex);
          }
        }}
        onInsert={() => insertSlide(state.activeIndex)}
        loading={state.loading}
        generating={state.generating}
        onUndo={undo}
        canUndo={canUndo}
        title={state.title}
        onTitleChange={setTitle}
        onPresent={() => setPresenting(true)}
        currentStyle={state.style}
        onRemixStyle={handleRemixStyle}
        stylePresets={stylePresets}
      />

      {state.generating && state.progress && state.progress.total > 0 && (
        <div className="px-4 py-2 bg-blue-50 border-b border-blue-100 flex items-center gap-3">
          <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full" />
          <span className="text-sm text-blue-700">
            {state.progress.batchStart != null && state.progress.batchEnd != null
              ? `正在生成第 ${state.progress.batchStart + 1}-${state.progress.batchEnd} 页...`
              : `正在生成第 ${state.progress.current}/${state.progress.total} 页...`}
          </span>
          <div className="flex-1 h-1.5 bg-blue-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-500"
              style={{ width: `${(state.progress.current / state.progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {hasIncomplete && (
        <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 flex items-center gap-3">
          <span className="text-sm text-amber-700">
            {incompleteSlides.length} 页未完成
          </span>
          <button
            onClick={handleContinueGeneration}
            disabled={state.loading}
            className="px-3 py-1 bg-amber-600 text-white rounded text-sm font-medium hover:bg-amber-700 disabled:opacity-50"
          >
            继续生成
          </button>
          <span className="text-xs text-amber-500">将逐页补全缺失内容</span>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel — Outline + Editor */}
        <div className="w-80 border-r border-gray-200 flex flex-col bg-gray-50">
          <SlideList
            slides={state.slides}
            activeIndex={state.activeIndex}
            onSelect={setActiveSlide}
            onReorder={moveSlide}
            generating={state.generating}
            regeneratingIndex={state.loading && !state.generating ? state.activeIndex : null}
            generatingProgress={state.progress}
            slideSteps={state.slideSteps}
          />
          {activeSlide && (
            <ContentEditor
              slide={activeSlide}
              slideIndex={state.activeIndex}
              totalSlides={state.slides.length}
              layouts={layouts}
              onRegenerate={(content, layout, prompt) =>
                regenSlide(state.activeIndex, content, layout, prompt)
              }
              loading={state.loading}
              generating={state.generating}
            />
          )}
        </div>

        {/* Right Panel — Preview */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 p-4 overflow-hidden">
            {activeSlide && activeSlide.html && activeSlide.html !== "__FAILED__" ? (
              <SlidePreview
                html={activeSlide.html}
                onContentEdit={(updated) =>
                  updateSlideHtml(state.activeIndex, updated)
                }
                loading={state.loading}
              />
            ) : activeSlide ? (
              <div className="w-full h-full flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200">
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full border-2 border-dashed border-gray-300 flex items-center justify-center">
                    {state.generating ? (
                      <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <svg className="w-6 h-6 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                      </svg>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 font-medium">
                    {state.generating ? "等待生成" : "空白页"}
                  </p>
                  {activeSlide.title && (
                    <p className="text-xs text-gray-400 mt-1">{activeSlide.title}</p>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* PDF export progress modal */}
      {pdfExporting && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-8 text-center shadow-2xl">
            <div className="animate-spin w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full mx-auto mb-4" />
            <p className="font-medium">正在渲染 PDF...</p>
            <p className="text-sm text-gray-400 mt-1">通常需要 5-10 秒</p>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 bg-gray-900 text-white text-sm rounded-full shadow-xl animate-[fadeIn_0.3s]">
          {toast}
        </div>
      )}

      {presenting && (
        <PresenterMode
          slides={state.slides}
          startIndex={state.activeIndex}
          onExit={() => setPresenting(false)}
        />
      )}
    </div>
  );
}
