"use client";

import { useState, useEffect, useCallback } from "react";
import { SlideDTO } from "@/lib/api";

interface Props {
  slides: SlideDTO[];
  startIndex: number;
  onExit: () => void;
}

export default function PresenterMode({ slides, startIndex, onExit }: Props) {
  const [current, setCurrent] = useState(startIndex);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const go = useCallback(
    (dir: 1 | -1) => {
      setCurrent((c) => Math.max(0, Math.min(slides.length - 1, c + dir)));
    },
    [slides.length]
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === " ") {
        e.preventDefault();
        go(1);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        go(-1);
      } else if (e.key === "Escape") {
        onExit();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [go, onExit]);

  const srcdoc = `<!DOCTYPE html><html><head><style>html,body{margin:0;padding:0;overflow:hidden;height:100%;}</style></head><body>${slides[current]?.html || ""}</body></html>`;

  const formatTime = (s: number) =>
    `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;

  return (
    <div className="fixed inset-0 z-[9999] bg-black flex flex-col">
      <div className="flex-1 flex items-center justify-center">
        <div className="w-full h-full" style={{ aspectRatio: "16/9", maxHeight: "100vh" }}>
          <iframe
            className="w-full h-full border-0"
            sandbox=""
            srcDoc={srcdoc}
          />
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 p-3 flex items-center justify-between bg-gradient-to-t from-black/80 to-transparent opacity-0 hover:opacity-100 transition-opacity duration-300">
        <div className="flex items-center gap-4">
          <button onClick={() => go(-1)} disabled={current === 0} className="text-white/70 hover:text-white disabled:text-white/20 text-lg">
            ←
          </button>
          <span className="text-white/80 text-sm font-mono">
            {current + 1} / {slides.length}
          </span>
          <button onClick={() => go(1)} disabled={current === slides.length - 1} className="text-white/70 hover:text-white disabled:text-white/20 text-lg">
            →
          </button>
        </div>
        <span className="text-white/40 text-xs font-mono">{formatTime(elapsed)}</span>
        <button onClick={onExit} className="text-white/60 hover:text-white text-sm px-3 py-1 border border-white/20 rounded hover:border-white/40 transition-colors">
          退出 (Esc)
        </button>
      </div>
    </div>
  );
}
