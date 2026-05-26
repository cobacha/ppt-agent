"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";

interface Props {
  slideCount: number;
  activeIndex: number;
  onExport: () => void;
  onExportPdf: () => void;
  onExportPptx: () => void;
  onPreview: () => void;
  pdfExporting: boolean;
  onRegenerateAll: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
  onInsert: () => void;
  loading: boolean;
  generating?: boolean;
  onUndo?: () => void;
  canUndo?: boolean;
  title?: string;
  onTitleChange?: (title: string) => void;
  onPresent?: () => void;
  currentStyle?: string;
  onRemixStyle?: (styleId: string) => void;
  stylePresets?: { id: string; name: string }[];
}

export default function Toolbar({
  slideCount,
  activeIndex,
  onExport,
  onExportPdf,
  onExportPptx,
  onPreview,
  pdfExporting,
  onRegenerateAll,
  onMoveUp,
  onMoveDown,
  onDelete,
  onInsert,
  loading,
  generating = false,
  onUndo,
  canUndo = false,
  title = "",
  onTitleChange,
  onPresent,
  currentStyle,
  onRemixStyle,
  stylePresets = [],
}: Props) {
  const [exportOpen, setExportOpen] = useState(false);
  const [remixOpen, setRemixOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const remixRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    if (!exportOpen && !remixOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (exportOpen && dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
      if (remixOpen && remixRef.current && !remixRef.current.contains(e.target as Node)) {
        setRemixOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [exportOpen, remixOpen]);

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white">
      <div className="flex items-center gap-3">
        <Link
          href="/"
          className="text-sm text-gray-400 hover:text-blue-600 transition-colors flex items-center gap-1"
        >
          <span>←</span>
          PPT Agent
        </Link>
        <span className="text-gray-200">|</span>
        <input
          type="text"
          value={title}
          onChange={(e) => onTitleChange?.(e.target.value)}
          className="text-base font-semibold bg-transparent border-0 border-b border-transparent hover:border-gray-300 focus:border-blue-500 focus:outline-none px-1 py-0.5 min-w-[120px] max-w-[300px] truncate"
          placeholder="演示文稿标题"
        />
        <span className="text-sm text-gray-400">
          {activeIndex + 1} / {slideCount}
          <span className="text-[10px] text-gray-300 ml-2">← → 切换</span>
        </span>
      </div>

      <div className="flex items-center gap-1">
        {/* Undo button */}
        {onUndo && (
          <button
            onClick={onUndo}
            disabled={!canUndo || loading}
            className="px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed border border-gray-200 rounded-md mr-2"
            title="撤销 (Ctrl+Z)"
          >
            撤销 <span className="text-[10px] text-gray-400 font-mono ml-1">⌘Z</span>
          </button>
        )}

        {/* Slide manipulation group */}
        <div className="flex items-center border border-gray-200 rounded-md overflow-hidden mr-2">
          <button
            onClick={onMoveUp}
            disabled={loading || activeIndex === 0}
            className="px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed border-r border-gray-200"
            title="上移此页"
          >
            ↑ 上移
          </button>
          <button
            onClick={onMoveDown}
            disabled={loading || activeIndex >= slideCount - 1}
            className="px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed border-r border-gray-200"
            title="下移此页"
          >
            ↓ 下移
          </button>
          <button
            onClick={onInsert}
            disabled={loading}
            className="px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed border-r border-gray-200"
            title="在当前页后插入空白页"
          >
            插入空白页
          </button>
          <button
            onClick={onDelete}
            disabled={loading || slideCount <= 1}
            className="px-2.5 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed"
            title="删除此页"
          >
            删除此页
          </button>
        </div>

        {/* Action buttons */}
        <button
          onClick={onRegenerateAll}
          disabled={loading || generating || slideCount === 0}
          className="px-3 py-1.5 bg-amber-500 text-white rounded-md text-sm font-medium hover:bg-amber-600 disabled:opacity-50 transition-colors"
        >
          重新生成全部
        </button>

        {onRemixStyle && stylePresets.length > 0 && (
          <div className="relative" ref={remixRef}>
            <button
              onClick={() => setRemixOpen(!remixOpen)}
              disabled={loading || generating || slideCount === 0}
              className="px-3 py-1.5 bg-purple-500 text-white rounded-md text-sm font-medium hover:bg-purple-600 disabled:opacity-50 transition-colors"
            >
              🎨 换主题
            </button>
            {remixOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50 max-h-64 overflow-y-auto">
                {stylePresets.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => {
                      onRemixStyle(preset.id);
                      setRemixOpen(false);
                    }}
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 ${
                      preset.id === currentStyle ? "text-purple-600 font-medium bg-purple-50" : "text-gray-700"
                    }`}
                  >
                    {preset.name}
                    {preset.id === currentStyle && <span className="ml-2 text-xs">✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {onPresent && (
          <button
            onClick={onPresent}
            disabled={loading || generating || slideCount === 0}
            className="px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            ▶ 演示
          </button>
        )}

        {/* Unified export dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setExportOpen(!exportOpen)}
            disabled={loading || generating || pdfExporting || slideCount === 0}
            className="px-4 py-1.5 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            导出 ▾
          </button>
          {exportOpen && (
            <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50">
              <button
                onClick={() => { onPreview(); setExportOpen(false); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                预览完整演示
              </button>
              <button
                onClick={() => { onExport(); setExportOpen(false); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                导出 HTML <span className="text-[10px] text-gray-400 ml-1">.html</span>
              </button>
              <button
                onClick={() => { onExportPdf(); setExportOpen(false); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                导出 PDF <span className="text-[10px] text-gray-400 ml-1">.pdf</span>
              </button>
              <button
                onClick={() => { onExportPptx(); setExportOpen(false); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                导出 PPT <span className="text-[10px] text-gray-400 ml-1">.pptx</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
