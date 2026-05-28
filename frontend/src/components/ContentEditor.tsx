"use client";

import { useState, useEffect, useRef } from "react";
import { SlideDTO, LayoutInfo } from "@/lib/api";

function buildContent(s: SlideDTO): string {
  const parts = [s.title];
  if (s.detailed_content) {
    parts.push("", s.detailed_content);
  } else if (s.bullets && s.bullets.length > 0) {
    parts.push("", ...s.bullets.map((b) => `- ${b}`));
  }
  return parts.join("\n");
}

interface Props {
  slide: SlideDTO;
  slideIndex: number;
  totalSlides: number;
  layouts: string[];
  layoutMap?: Record<string, LayoutInfo>;
  onRegenerate: (content: string, layout: string, prompt: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
  loading: boolean;
  generating?: boolean;
}

export default function ContentEditor({
  slide,
  slideIndex,
  totalSlides,
  layouts,
  layoutMap = {},
  onRegenerate,
  onDirtyChange,
  loading,
  generating = false,
}: Props) {

  const [content, setContent] = useState(buildContent(slide));
  const [prompt, setPrompt] = useState("");
  const [layout, setLayout] = useState("auto");
  const [userEdited, setUserEdited] = useState(false);
  const prevDirty = useRef(false);

  useEffect(() => {
    if (prevDirty.current !== userEdited) {
      prevDirty.current = userEdited;
      onDirtyChange?.(userEdited);
    }
  }, [userEdited, onDirtyChange]);

  useEffect(() => {
    setContent(buildContent(slide));
    setLayout("auto");
    setPrompt("");
    setUserEdited(false);
  }, [slide.index]);

  // Update content when detailed_content arrives, but only if user hasn't edited
  useEffect(() => {
    if (!userEdited && slide.detailed_content) {
      setContent(buildContent(slide));
    }
  }, [slide.detailed_content]);

  const roleLabel = slideIndex === 0 ? "封面" : slideIndex === totalSlides - 1 ? "结尾" : "内容";

  return (
    <div className="flex flex-col border-t border-gray-200 flex-shrink-0 bg-white">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100">
        <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
          {slideIndex + 1}/{totalSlides}
        </span>
        <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{roleLabel}</span>
        <span className="text-sm font-medium text-gray-700 truncate flex-1">
          {slide.title || "无标题"}
        </span>
        {slide.quality_score > 0 && (
          <span className={`text-xs font-mono px-2 py-0.5 rounded ${
            slide.quality_score >= 80 ? "text-green-700 bg-green-50"
            : slide.quality_score >= 60 ? "text-yellow-700 bg-yellow-50"
            : "text-red-700 bg-red-50"
          }`}>
            {slide.quality_score.toFixed(0)}分
          </span>
        )}
      </div>

      {/* Editable content */}
      <div className="p-4 flex flex-col gap-4">
        <div>
          <label className="text-xs font-semibold text-gray-600 mb-1.5 block">页面内容</label>
          <textarea
            value={content}
            onChange={(e) => { setContent(e.target.value); setUserEdited(true); }}
            className="w-full h-[160px] p-3 border border-gray-200 rounded-md text-sm font-mono resize-y focus:ring-1 focus:ring-blue-400 bg-gray-50 leading-relaxed"
            placeholder="第一行为标题，后续行为要点内容（每行一个要点，可用 - 开头）"
          />
        </div>

        <div>
          <label className="text-xs font-semibold text-gray-600 mb-1.5 block">
            生成指令 <span className="font-normal text-gray-400">（可选）</span>
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="w-full h-[64px] px-3 py-2 border border-gray-200 rounded-md text-sm resize-y focus:ring-1 focus:ring-purple-400 leading-relaxed"
            placeholder="对生成结果的额外要求，如：用深色背景、突出数据对比、加图标装饰..."
          />
        </div>

        <div className="flex gap-2">
          <select
            value={layout}
            onChange={(e) => setLayout(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-200 rounded-md text-sm"
          >
            <option value="auto">布局: 自动</option>
            {layouts.map((l) => (
              <option key={l} value={l}>{layoutMap[l]?.description || l}</option>
            ))}
          </select>
          <button
            onClick={() => onRegenerate(content, layout, prompt)}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2 flex-shrink-0"
          >
            {loading && (
              <span className="animate-spin w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full" />
            )}
            {loading ? "生成中..." : "重新生成此页"}
          </button>
        </div>
      </div>
    </div>
  );
}
