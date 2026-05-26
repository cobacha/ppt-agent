"use client";

import { useEffect, useRef, useState, useMemo } from "react";

interface Props {
  thinking: string;
  onCancel?: () => void;
}

const STAGES = [
  { label: "正在努力思考中", sub: "理解你的内容，寻找最佳表达方式" },
  { label: "深度分析中", sub: "识别核心主题与信息层次" },
  { label: "构思演示结构", sub: "设计叙事节奏与页面编排" },
  { label: "构思大纲中", sub: "打磨每页的标题和内容要点" },
];

function extractTitles(text: string): string[] {
  const matches = text.match(/"title"\s*:\s*"([^"]+)"/g);
  if (!matches) return [];
  return matches
    .map((m) => {
      const val = m.match(/"title"\s*:\s*"([^"]+)"/);
      return val ? val[1] : "";
    })
    .filter((t) => t && t.length > 1 && t.length < 60);
}

export default function GeneratingView({ thinking, onCancel }: Props) {
  const listEndRef = useRef<HTMLDivElement>(null);
  const [stage, setStage] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  const titles = useMemo(() => extractTitles(thinking), [thinking]);

  useEffect(() => {
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (titles.length > 0 && listEndRef.current) {
      listEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [titles.length]);

  useEffect(() => {
    if (!thinking) { setStage(0); return; }
    if (titles.length > 0) setStage(3);
    else if (thinking.length > 200) setStage(2);
    else setStage(1);
  }, [thinking, titles.length]);

  const currentStage = STAGES[stage];
  const formatTime = (s: number) =>
    `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="flex-1 flex items-center justify-center relative overflow-hidden bg-gradient-to-b from-gray-50 to-white">
      <div className="absolute top-20 -left-20 w-72 h-72 bg-blue-100/40 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-20 -right-20 w-60 h-60 bg-indigo-100/30 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 w-full max-w-sm px-6">
        {/* Animated ring */}
        <div className="flex justify-center mb-8">
          <div className="relative w-16 h-16 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-2 border-blue-200 animate-[ping_3s_cubic-bezier(0,0,0.2,1)_infinite] opacity-40" />
            <div className="absolute inset-0 rounded-full border-2 border-blue-300/60" />
            <div className="w-3 h-3 rounded-full bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,0.5)]" />
          </div>
        </div>

        {/* Stage label */}
        <div className="text-center mb-5">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">
            {currentStage.label}
          </h2>
          <p className="text-sm text-gray-400">
            {currentStage.sub}
          </p>
        </div>

        {/* Progress dots + timer */}
        <div className="flex items-center justify-center gap-4 mb-8">
          <div className="flex gap-1.5">
            {STAGES.map((_, i) => (
              <div
                key={i}
                className={`h-1 rounded-full transition-all duration-700 ${
                  i <= stage
                    ? "w-7 bg-blue-500"
                    : "w-4 bg-gray-200"
                }`}
              />
            ))}
          </div>
          <span className="text-[11px] font-mono text-gray-300 tabular-nums">
            {formatTime(elapsed)}
          </span>
        </div>

        {/* Outline list */}
        {titles.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <p className="text-xs text-gray-400 mb-3 text-center">
              大纲预览 · {titles.length} 页
            </p>
            <div className="max-h-[260px] overflow-y-auto space-y-1.5 scroll-smooth" style={{ scrollbarWidth: "none" }}>
              {titles.map((title, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 animate-[fadeIn_0.4s_ease-out_both]"
                  style={{ animationDelay: `${i * 0.06}s` }}
                >
                  <span className="flex-shrink-0 text-[11px] font-mono text-blue-400 w-5 text-right">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="text-sm text-gray-700 truncate">
                    {title}
                  </span>
                </div>
              ))}
              <div ref={listEndRef} />
            </div>
          </div>
        )}

        {/* Loading dots */}
        {titles.length === 0 && (
          <div className="flex justify-center">
            <div className="flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-[pulse_1.5s_ease-in-out_infinite]"
                  style={{ animationDelay: `${i * 0.3}s` }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Cancel */}
        {onCancel && (
          <div className="flex justify-center mt-10">
            <button
              onClick={onCancel}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
            >
              取消生成
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
