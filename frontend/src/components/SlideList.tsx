"use client";

import { useState } from "react";
import { SlideDTO } from "@/lib/api";

interface Props {
  slides: SlideDTO[];
  activeIndex: number;
  onSelect: (index: number) => void;
  onReorder?: (fromIndex: number, toIndex: number) => void;
  generating?: boolean;
  regeneratingIndex?: number | null;
  generatingProgress?: { current: number; total: number; batchStart?: number; batchEnd?: number } | null;
  slideSteps?: Record<number, "expanding" | "rendering">;
}

export default function SlideList({ slides, activeIndex, onSelect, onReorder, generating, regeneratingIndex, generatingProgress, slideSteps }: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
        <span className="text-base font-semibold text-gray-800">PPT 大纲</span>
        <span className="text-sm text-gray-400">{slides.length} 页</span>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        {slides.map((slide, i) => {
          const isFailed = slide.html === "__FAILED__";
          const isCompleted = slide.html !== "" && !isFailed;
          const batchStart = generatingProgress?.batchStart;
          const batchEnd = generatingProgress?.batchEnd;
          const hasBatchInfo = batchStart != null && batchEnd != null;
          const isActivelyGenerating = generating && !isCompleted && !isFailed && hasBatchInfo && i >= batchStart && i < batchEnd;
          const isQueued = generating && !isCompleted && !isFailed && (hasBatchInfo ? i >= batchEnd : true);
          const isRegenerating = regeneratingIndex === i;
          const isActive = i === activeIndex;

          return (
            <div
              key={i}
              onClick={() => onSelect(i)}
              draggable={!generating && !!onReorder}
              onDragStart={(e) => {
                setDragIndex(i);
                e.dataTransfer.effectAllowed = "move";
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOverIndex(i);
              }}
              onDragEnd={() => {
                if (dragIndex !== null && dragOverIndex !== null && dragIndex !== dragOverIndex) {
                  onReorder?.(dragIndex, dragOverIndex);
                }
                setDragIndex(null);
                setDragOverIndex(null);
              }}
              className={`flex items-center gap-2 px-4 py-2.5 mx-2 mb-1 rounded-lg cursor-pointer select-none transition-all ${
                dragOverIndex === i && dragIndex !== i ? "border-t-2 border-t-blue-500" : ""
              } ${dragIndex === i ? "opacity-40" : ""} ${
                isFailed ? "bg-red-50"
                : isRegenerating ? "bg-purple-50"
                : isActive ? "bg-blue-50 ring-1 ring-blue-200"
                : "hover:bg-gray-100"
              }`}
            >
              {!generating && onReorder && (
                <span className="text-gray-300 cursor-grab active:cursor-grabbing text-sm flex-shrink-0">⠿</span>
              )}

              <span className={`font-mono text-sm w-6 text-center flex-shrink-0 ${
                isActive ? "text-blue-600 font-bold" : "text-gray-400"
              }`}>
                {i + 1}
              </span>

              {(isActivelyGenerating || isRegenerating) && (
                <span className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
              )}

              <span className={`text-sm truncate flex-1 ${
                isActive ? "text-gray-900 font-medium" : "text-gray-600"
              }`}>
                {slide.title || `第 ${i + 1} 页`}
              </span>

              {isRegenerating && (
                <span className="text-xs text-purple-600 bg-purple-100 px-1.5 py-0.5 rounded flex-shrink-0">生成中</span>
              )}
              {isActivelyGenerating && !isRegenerating && (
                <span className="text-xs text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded flex-shrink-0">
                  {slideSteps?.[i] === "expanding" ? "构思" : slideSteps?.[i] === "rendering" ? "渲染" : "生成"}
                </span>
              )}
              {isQueued && !isRegenerating && (
                <span className="text-xs text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded flex-shrink-0">排队</span>
              )}
              {isFailed && (
                <span className="text-xs text-red-600 bg-red-100 px-1.5 py-0.5 rounded flex-shrink-0">失败</span>
              )}
              {isCompleted && !isRegenerating && slide.quality_score > 0 && (
                <span className={`text-xs font-mono px-1.5 py-0.5 rounded flex-shrink-0 ${
                  slide.quality_score >= 80 ? "text-green-700 bg-green-50"
                  : slide.quality_score >= 60 ? "text-yellow-700 bg-yellow-50"
                  : "text-red-700 bg-red-50"
                }`}>
                  {slide.quality_score.toFixed(0)}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
