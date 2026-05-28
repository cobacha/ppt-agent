"use client";

import { useRef, useEffect, useCallback, useState, memo } from "react";

interface Props {
  html: string;
  onContentEdit?: (updatedHtml: string) => void;
  loading?: boolean;
}

function SlidePreview({ html, onContentEdit, loading = false }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [transitioning, setTransitioning] = useState(false);
  const prevHtmlRef = useRef<string>("");
  const observerRef = useRef<MutationObserver | null>(null);
  const injectVersionRef = useRef(0);
  const onContentEditRef = useRef(onContentEdit);
  onContentEditRef.current = onContentEdit;

  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    if (!document.fullscreenElement) {
      container.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }, []);

  // Listen for fullscreen change
  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  // Keyboard shortcut: F to toggle fullscreen when container is focused
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "f" || e.key === "F") {
        // Don't trigger if typing in an input
        const target = e.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) return;
        toggleFullscreen();
      }
    };
    container.addEventListener("keydown", handler);
    return () => container.removeEventListener("keydown", handler);
  }, [toggleFullscreen]);

  const handleSaveEdit = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe || !onContentEditRef.current) return;
    const doc = iframe.contentDocument;
    if (!doc) return;
    const updated = doc.body.innerHTML;
    onContentEditRef.current(updated);
    setIsDirty(false);
  }, []);

  const injectHtml = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    // Disconnect previous observer
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    setIsDirty(false);

    const version = ++injectVersionRef.current;
    const content = `<!DOCTYPE html><html><head><style>html, body { margin: 0; padding: 0; overflow: hidden; height: 100%; } [contenteditable="true"]:hover { outline: 2px dashed rgba(59,130,246,0.5); cursor: text; } [contenteditable="true"]:focus { outline: 2px solid #3b82f6; background: rgba(59,130,246,0.03); }</style></head><body>${html}</body></html>`;
    iframe.srcdoc = content;

    if (onContentEditRef.current) {
      const setupEditable = () => {
        if (injectVersionRef.current !== version) return;
        const iframeDoc = iframe.contentDocument;
        if (!iframeDoc || !iframeDoc.body) return;
        iframeDoc.querySelectorAll("h1, h2, h3, h4, h5, h6, p, li, span, td, th").forEach((el) => {
          const htmlEl = el as HTMLElement;
          if (htmlEl.children.length === 0 || htmlEl.textContent?.trim()) {
            htmlEl.setAttribute("contenteditable", "true");
          }
        });

        const observer = new MutationObserver(() => {
          setIsDirty(true);
        });
        observer.observe(iframeDoc.body, {
          childList: true,
          subtree: true,
          characterData: true,
        });
        observerRef.current = observer;
      };

      iframe.addEventListener("load", setupEditable, { once: true });
    }
  }, [html]);

  useEffect(() => {
    if (prevHtmlRef.current && prevHtmlRef.current !== html) {
      setTransitioning(true);
      const t = setTimeout(() => {
        injectHtml();
        setTimeout(() => setTransitioning(false), 50);
      }, 150);
      prevHtmlRef.current = html;
      return () => clearTimeout(t);
    }
    prevHtmlRef.current = html;
    injectHtml();
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [injectHtml, html]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full bg-[#1a1a1a] rounded-lg overflow-hidden flex items-center justify-center"
      tabIndex={0}
    >
      {/* Fullscreen toggle button */}
      <button
        onClick={toggleFullscreen}
        className="absolute top-2 right-2 z-10 px-2 py-1 bg-black/50 text-white text-xs rounded hover:bg-black/70 transition-colors"
        title="全屏预览 (F)"
      >
        {isFullscreen ? "退出全屏" : "全屏"}
      </button>

      {/* Dirty indicator: blue top border */}
      {isDirty && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-blue-500 z-10" />
      )}

      {/* Aspect-ratio-locked slide container */}
      <div
        className="relative bg-white shadow-2xl rounded-sm transition-all duration-200"
        style={{
          width: `${zoom}%`,
          maxWidth: "100%",
          aspectRatio: "16 / 9",
        }}
      >
        <iframe
          ref={iframeRef}
          className={`absolute inset-0 w-full h-full border-0 transition-opacity duration-150 ${transitioning ? "opacity-0" : "opacity-100"}`}
          sandbox="allow-same-origin"
          title="Slide Preview"
        />
      </div>

      {/* Zoom controls */}
      <div className="absolute bottom-3 right-3 z-10 flex items-center gap-1 bg-black/60 rounded-full px-2 py-1">
        <button
          onClick={() => setZoom((z) => Math.max(50, z - 10))}
          className="text-white/80 hover:text-white text-xs px-1"
        >
          −
        </button>
        <span className="text-[10px] text-white/60 font-mono w-8 text-center">{zoom}%</span>
        <button
          onClick={() => setZoom((z) => Math.min(100, z + 10))}
          className="text-white/80 hover:text-white text-xs px-1"
        >
          +
        </button>
        <button
          onClick={() => setZoom(100)}
          className="text-[10px] text-white/50 hover:text-white/80 ml-1"
        >
          Fit
        </button>
      </div>

      {/* Save edit button */}
      {isDirty && onContentEdit && (
        <button
          onClick={handleSaveEdit}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 px-4 py-1.5 bg-blue-600 text-white text-sm rounded-md shadow-lg hover:bg-blue-700 transition-colors"
        >
          保存编辑
        </button>
      )}

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <div className="animate-spin w-8 h-8 border-3 border-white border-t-transparent rounded-full" />
            <span className="text-white text-sm font-medium">生成中...</span>
          </div>
        </div>
      )}

      {/* Empty state when no html */}
      {!html && !loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center">
          <div className="text-center text-gray-400">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full border-2 border-dashed border-gray-300 flex items-center justify-center">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
              </svg>
            </div>
            <p className="text-sm">等待生成</p>
          </div>
        </div>
      )}

      {/* Fullscreen close overlay button */}
      {isFullscreen && (
        <button
          onClick={toggleFullscreen}
          className="absolute top-4 right-4 z-20 px-3 py-2 bg-black/70 text-white rounded-md hover:bg-black/90 transition-colors"
        >
          退出全屏
        </button>
      )}
    </div>
  );
}

export default memo(SlidePreview, (prev, next) => prev.html === next.html && prev.loading === next.loading);
