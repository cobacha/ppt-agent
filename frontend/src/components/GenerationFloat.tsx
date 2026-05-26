"use client";

import { useRouter, usePathname } from "next/navigation";
import { useGenerationContext } from "@/context/GenerationContext";

export default function GenerationFloat() {
  const router = useRouter();
  const pathname = usePathname();
  const { state } = useGenerationContext();

  if (!state.generating || pathname === "/editor") return null;

  const { progress, title, thinking } = state;
  const current = progress?.current || 0;
  const total = progress?.total || 0;
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  const isThinking = !!thinking || (total === 0 && current === 0);

  return (
    <button
      onClick={() => router.push("/editor")}
      className="fixed bottom-6 right-6 z-50 bg-white border border-gray-200 rounded-2xl shadow-lg px-4 py-3 flex items-center gap-3 hover:shadow-xl hover:border-blue-300 transition-all animate-[slideUp_0.3s_ease-out]"
      style={{ minWidth: 200 }}
    >
      <span className="relative flex h-3 w-3">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500" />
      </span>

      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-700 truncate">
          {title || "正在生成中..."}
        </p>
        {isThinking ? (
          <p className="text-[10px] text-gray-400 mt-1">正在构思大纲...</p>
        ) : (
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-[10px] text-gray-400 font-mono whitespace-nowrap">
              {current}/{total}
            </span>
          </div>
        )}
      </div>

      <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}
