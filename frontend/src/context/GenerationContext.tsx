"use client";

import { createContext, useContext, useState, useCallback, useEffect, useRef, useMemo, type ReactNode } from "react";
import {
  SlideDTO,
  LayoutInfo,
  regenerateSlide,
  exportPresentation,
  exportPdf,
  exportPptx,
  fetchLayouts,
  fetchActiveGeneration,
} from "@/lib/api";
import { streamGeneration } from "@/lib/sse";

export interface EditorState {
  slides: SlideDTO[];
  activeIndex: number;
  style: string;
  fullHtml: string;
  loading: boolean;
  generating: boolean;
  progress: { current: number; total: number; batchStart?: number; batchEnd?: number } | null;
  error: string | null;
  thinking: string;
  expanding: { current: number; total: number } | null;
  slideSteps: Record<number, "expanding" | "rendering">;
  title: string;
}

interface GenerationContextValue {
  state: EditorState;
  genId: string | null;
  generate: (content: string, style: string, language?: string, aspectRatio?: string) => void;
  cancel: () => void;
  regenSlide: (index: number, content: string, layout: string, prompt?: string) => Promise<void>;
  setActiveSlide: (index: number) => void;
  updateSlideHtml: (index: number, html: string) => void;
  moveSlide: (fromIndex: number, toIndex: number) => void;
  deleteSlide: (index: number) => void;
  insertSlide: (afterIndex: number) => void;
  duplicateSlide: (index: number) => void;
  previewFull: () => Promise<void>;
  doExport: () => Promise<void>;
  doExportPdf: () => Promise<void>;
  doExportPptx: () => Promise<void>;
  pdfExporting: boolean;
  layouts: string[];
  layoutMap: Record<string, LayoutInfo>;
  undo: () => void;
  canUndo: boolean;
  loadSlides: (slides: SlideDTO[], style: string, title?: string) => void;
  setTitle: (title: string) => void;
  onDone: (listener: DoneListener) => () => void;
  recoverActiveGeneration: () => Promise<boolean>;
  continueGeneration: (indices: number[]) => Promise<void>;
}

const GenerationContext = createContext<GenerationContextValue | null>(null);

export function useGenerationContext() {
  const ctx = useContext(GenerationContext);
  if (!ctx) throw new Error("useGenerationContext must be used within GenerationProvider");
  return ctx;
}

const INITIAL_STATE: EditorState = {
  slides: [],
  activeIndex: 0,
  style: "corporate-navy",
  fullHtml: "",
  loading: false,
  generating: false,
  progress: null,
  error: null,
  thinking: "",
  expanding: null,
  slideSteps: {},
  title: "",
};

export interface GenerationDoneEvent {
  content: string;
  style: string;
  slides: SlideDTO[];
  title: string;
  gen_id?: string;
}

type DoneListener = (event: GenerationDoneEvent) => void;

export function GenerationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<EditorState>(INITIAL_STATE);
  const [genId, setGenId] = useState<string | null>(null);
  const genIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const doneListenersRef = useRef<Set<DoneListener>>(new Set());
  const genContentRef = useRef<string>("");
  const genStyleRef = useRef<string>("");
  const slidesRef = useRef<SlideDTO[]>([]);

  const onDone = useCallback((listener: DoneListener) => {
    doneListenersRef.current.add(listener);
    return () => { doneListenersRef.current.delete(listener); };
  }, []);

  useEffect(() => { slidesRef.current = state.slides; }, [state.slides]);
  useEffect(() => { genIdRef.current = genId; }, [genId]);

  // Undo stack
  const undoStackRef = useRef<SlideDTO[][]>([]);
  const [undoCount, setUndoCount] = useState(0);
  const MAX_UNDO = 10;

  const pushUndo = useCallback((slides: SlideDTO[]) => {
    undoStackRef.current = [...undoStackRef.current.slice(-(MAX_UNDO - 1)), slides];
    setUndoCount(undoStackRef.current.length);
  }, []);

  const undo = useCallback(() => {
    const stack = undoStackRef.current;
    if (stack.length === 0) return;
    const prev = stack[stack.length - 1];
    undoStackRef.current = stack.slice(0, -1);
    setUndoCount(undoStackRef.current.length);
    setState((s) => ({ ...s, slides: prev }));
  }, []);

  const canUndo = undoCount > 0;

  const generate = useCallback((content: string, style: string, language: string = "zh", aspectRatio: string = "16:9") => {
    abortControllerRef.current?.abort();
    genContentRef.current = content;
    genStyleRef.current = style;

    setState({
      ...INITIAL_STATE,
      loading: true,
      generating: true,
      style,
      progress: { current: 0, total: 0 },
    });
    undoStackRef.current = [];
    setUndoCount(0);

    const controller = streamGeneration(content, style, {
      onThinking: (text) => {
        setState((s) => ({ ...s, thinking: s.thinking + text }));
      },
      onOutline: (outline) => {
        const total = outline.slides.length;
        const placeholders: SlideDTO[] = outline.slides.map((s, i) => ({
          index: i,
          title: s.title,
          html: "",
          quality_score: 0,
          bullets: s.bullets,
        }));
        const derivedTitle = outline.title || outline.slides?.[0]?.title || "";
        if (outline.gen_id) {
          setGenId(outline.gen_id);
        }
        setState((s) => ({
          ...s,
          slides: placeholders,
          title: derivedTitle || s.title || "",
          loading: false,
          thinking: "",
          progress: { current: 0, total },
          expanding: { current: 0, total },
        }));
      },
      onSlideStep: (event) => {
        setState((s) => ({
          ...s,
          slideSteps: { ...s.slideSteps, [event.index]: event.step },
        }));
      },
      onBatchStart: (batch) => {
        setState((s) => ({
          ...s,
          expanding: null,
          progress: {
            current: s.progress?.current || 0,
            total: s.progress?.total || 0,
            batchStart: batch.start,
            batchEnd: batch.end,
          },
        }));
      },
      onSlide: (slide) => {
        setState((s) => {
          const newSlides = [...s.slides];
          newSlides[slide.index] = {
            ...newSlides[slide.index],
            index: slide.index,
            title: slide.title,
            html: slide.html,
            quality_score: slide.quality_score,
          };
          const completed = newSlides.filter((sl) => sl.html).length;
          const newSteps = { ...s.slideSteps };
          delete newSteps[slide.index];
          return {
            ...s,
            slides: newSlides,
            activeIndex: slide.index,
            expanding: null,
            slideSteps: newSteps,
            progress: {
              current: completed,
              total: s.progress?.total || newSlides.length,
              batchStart: s.progress?.batchStart,
              batchEnd: s.progress?.batchEnd,
            },
          };
        });
      },
      onError: (error) => {
        if (error.index != null) {
          setState((s) => {
            const newSlides = [...s.slides];
            if (newSlides[error.index!]) {
              newSlides[error.index!] = { ...newSlides[error.index!], html: "__FAILED__" };
            }
            return { ...s, slides: newSlides, error: `第 ${error.index! + 1} 页生成失败: ${error.message}` };
          });
        } else {
          setState((s) => ({ ...s, error: error.message }));
        }
      },
      onDone: (data) => {
        const doneGenId = data?.gen_id || null;
        if (doneGenId) setGenId(doneGenId);
        setState((s) => {
          if (s.slides.length > 0 && !s.error) {
            const event: GenerationDoneEvent = {
              content: genContentRef.current,
              style: genStyleRef.current,
              slides: s.slides,
              title: s.title,
              gen_id: doneGenId || undefined,
            };
            setTimeout(() => {
              doneListenersRef.current.forEach((fn) => fn(event));
            }, 0);
          }
          return { ...s, generating: false, progress: null };
        });
        abortControllerRef.current = null;
      },
    }, language, aspectRatio);

    abortControllerRef.current = controller;
  }, []);

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setState((s) => ({ ...s, loading: false, generating: false, progress: null, thinking: "" }));
  }, []);

  const regenSlide = useCallback(
    async (index: number, content: string, layout: string, prompt?: string) => {
      setState((s) => {
        pushUndo(s.slides);
        return { ...s, loading: true, error: null };
      });
      try {
        const currentSlides = slidesRef.current;
        const contextSlides: Record<string, unknown>[] = [];
        if (index > 0 && currentSlides[index - 1]?.html) {
          contextSlides.push({ index: index - 1, title: currentSlides[index - 1].title, html: currentSlides[index - 1].html });
        }
        if (index < currentSlides.length - 1 && currentSlides[index + 1]?.html) {
          contextSlides.push({ index: index + 1, title: currentSlides[index + 1].title, html: currentSlides[index + 1].html });
        }

        const fullContent = prompt ? `${content}\n\n[生成指令]: ${prompt}` : content;

        // Build presentation context so LLM knows slide position and role
        const outlineContext = currentSlides.map((s, i) => `${i + 1}. ${s.title}`).join("\n");
        const contextStr = `演示文稿标题: ${state.title || "未命名"}\n总页数: ${currentSlides.length}\n当前编辑: 第 ${index + 1} 页（共 ${currentSlides.length} 页）\n${index === 0 ? "角色: 封面页" : index === currentSlides.length - 1 ? "角色: 结尾页" : `角色: 内容页`}\n\n大纲:\n${outlineContext}`;

        const result = await regenerateSlide({
          slide_index: index,
          content: fullContent,
          layout,
          style: state.style,
          context_slides: contextSlides,
          context: contextStr,
        });

        setState((s) => {
          const newSlides = [...s.slides];
          newSlides[index] = { ...newSlides[index], html: result.html, quality_score: result.quality_score };
          return { ...s, slides: newSlides, loading: false };
        });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "重新生成失败";
        setState((s) => ({ ...s, loading: false, error: message }));
      }
    },
    [state.style, state.title, pushUndo]
  );

  const setActiveSlide = useCallback((index: number) => {
    setState((s) => ({ ...s, activeIndex: index }));
  }, []);

  const updateSlideHtml = useCallback((index: number, html: string) => {
    setState((s) => {
      pushUndo(s.slides);
      const newSlides = [...s.slides];
      newSlides[index] = { ...newSlides[index], html };
      return { ...s, slides: newSlides };
    });
  }, [pushUndo]);

  const moveSlide = useCallback((fromIndex: number, toIndex: number) => {
    setState((s) => {
      if (fromIndex < 0 || fromIndex >= s.slides.length) return s;
      if (toIndex < 0 || toIndex >= s.slides.length) return s;
      pushUndo(s.slides);
      const newSlides = [...s.slides];
      const [moved] = newSlides.splice(fromIndex, 1);
      newSlides.splice(toIndex, 0, moved);
      const reindexed = newSlides.map((slide, i) => ({ ...slide, index: i }));
      let newActiveIndex = s.activeIndex;
      if (s.activeIndex === fromIndex) newActiveIndex = toIndex;
      else if (fromIndex < s.activeIndex && toIndex >= s.activeIndex) newActiveIndex = s.activeIndex - 1;
      else if (fromIndex > s.activeIndex && toIndex <= s.activeIndex) newActiveIndex = s.activeIndex + 1;
      return { ...s, slides: reindexed, activeIndex: newActiveIndex };
    });
  }, [pushUndo]);

  const deleteSlide = useCallback((index: number) => {
    setState((s) => {
      if (s.slides.length <= 1) return s;
      pushUndo(s.slides);
      const newSlides = s.slides.filter((_, i) => i !== index).map((slide, i) => ({ ...slide, index: i }));
      let newActiveIndex = s.activeIndex;
      if (s.activeIndex >= newSlides.length) newActiveIndex = newSlides.length - 1;
      else if (s.activeIndex > index) newActiveIndex = s.activeIndex - 1;
      return { ...s, slides: newSlides, activeIndex: newActiveIndex };
    });
  }, [pushUndo]);

  const insertSlide = useCallback((afterIndex: number) => {
    setState((s) => {
      pushUndo(s.slides);
      const insertAt = afterIndex + 1;
      const placeholder: SlideDTO = { index: insertAt, title: "空白页", html: "", quality_score: 0 };
      const newSlides = [...s.slides];
      newSlides.splice(insertAt, 0, placeholder);
      const reindexed = newSlides.map((slide, i) => ({ ...slide, index: i }));
      return { ...s, slides: reindexed, activeIndex: insertAt };
    });
  }, [pushUndo]);

  const duplicateSlide = useCallback((index: number) => {
    setState((s) => {
      if (index < 0 || index >= s.slides.length) return s;
      pushUndo(s.slides);
      const source = s.slides[index];
      const copy: SlideDTO = { ...source, title: `${source.title} (副本)` };
      const newSlides = [...s.slides];
      newSlides.splice(index + 1, 0, copy);
      const reindexed = newSlides.map((slide, i) => ({ ...slide, index: i }));
      return { ...s, slides: reindexed, activeIndex: index + 1 };
    });
  }, [pushUndo]);

  const previewFull = useCallback(async () => {
    try {
      const slides = state.slides.map((s) => ({ html: s.html }));
      const result = await exportPresentation(slides, state.style, state.title);
      // Use sandbox iframe with Blob src to isolate LLM-generated HTML from parent origin
      const contentBlob = new Blob([result.html], { type: "text/html" });
      const contentUrl = URL.createObjectURL(contentBlob);
      const wrapper = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Preview</title><style>*{margin:0;padding:0}iframe{width:100vw;height:100vh;border:none}</style></head><body><iframe sandbox="allow-scripts" src="${contentUrl}"></iframe></body></html>`;
      const blob = new Blob([wrapper], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => { URL.revokeObjectURL(url); URL.revokeObjectURL(contentUrl); }, 60000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "预览失败";
      setState((s) => ({ ...s, error: message }));
    }
  }, [state.slides, state.style, state.title]);

  const doExport = useCallback(async () => {
    try {
      const slides = state.slides.map((s) => ({ html: s.html }));
      const result = await exportPresentation(slides, state.style, state.title);
      const blob = new Blob([result.html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = result.filename || `${state.title || "presentation"}.html`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "导出失败";
      setState((s) => ({ ...s, error: message }));
    }
  }, [state.slides, state.style, state.title]);

  const [pdfExporting, setPdfExporting] = useState(false);

  const doExportPdf = useCallback(async () => {
    setPdfExporting(true);
    setState((s) => ({ ...s, error: null }));
    try {
      const slides = state.slides.map((s) => ({ html: s.html }));
      const blob = await exportPdf(slides, state.style);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "presentation.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "PDF 导出失败";
      setState((s) => ({ ...s, error: message }));
    } finally {
      setPdfExporting(false);
    }
  }, [state.slides, state.style]);

  const doExportPptx = useCallback(async () => {
    setPdfExporting(true);
    setState((s) => ({ ...s, error: null }));
    try {
      const slides = state.slides.map((s) => ({ html: s.html }));
      const blob = await exportPptx(slides, state.style, state.title);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${state.title || "presentation"}.pptx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "PPTX 导出失败";
      setState((s) => ({ ...s, error: message }));
    } finally {
      setPdfExporting(false);
    }
  }, [state.slides, state.style, state.title]);

  const [layoutMap, setLayoutMap] = useState<Record<string, LayoutInfo>>({});
  const layouts = useMemo(() => Object.keys(layoutMap), [layoutMap]);

  useEffect(() => {
    fetchLayouts().then((data) => setLayoutMap(data.layouts)).catch(() => {});
  }, []);

  const recoverActiveGeneration = useCallback(async (): Promise<boolean> => {
    const active = await fetchActiveGeneration();
    if (!active) return false;
    setGenId(active.id);
    genContentRef.current = active.content;
    genStyleRef.current = active.style;
    setState((s) => ({
      ...s,
      slides: active.slides,
      style: active.style,
      title: active.title || active.slides[0]?.title || "",
      activeIndex: 0,
      loading: false,
      generating: false,
      error: null,
    }));
    return true;
  }, []);

  const loadSlides = useCallback((slides: SlideDTO[], style: string, title?: string) => {
    // Store content/style for "regenerate all" to work on history-loaded sessions
    genStyleRef.current = style;
    setState((s) => ({
      ...s,
      slides,
      style,
      title: title || slides[0]?.title || s.title,
      activeIndex: 0,
      loading: false,
      generating: false,
      error: null,
    }));
  }, []);

  const setTitle = useCallback((title: string) => {
    setState((s) => ({ ...s, title }));
  }, []);

  const continueGeneration = useCallback(async (indices: number[]) => {
    if (indices.length === 0) return;
    const currentSlides = slidesRef.current;
    const total = currentSlides.length;
    const completedBefore = currentSlides.filter(s => s.html && s.html !== "__FAILED__").length;

    setState((s) => ({
      ...s,
      generating: true,
      loading: true,
      error: null,
      progress: { current: completedBefore, total },
    }));

    const BATCH = 3;
    let completed = completedBefore;

    try {
      for (let i = 0; i < indices.length; i += BATCH) {
        const batch = indices.slice(i, i + BATCH);
        setState((s) => ({
          ...s,
          progress: {
            current: completed,
            total,
            batchStart: batch[0],
            batchEnd: batch[batch.length - 1] + 1,
          },
        }));

        const currentSlides = slidesRef.current;
        const results = await Promise.allSettled(
          batch.map(async (idx) => {
            const slide = currentSlides[idx];
            const content = slide.detailed_content || slide.bullets?.join("\n") || slide.title;

            const contextSlides: Record<string, unknown>[] = [];
            if (idx > 0 && currentSlides[idx - 1]?.html && currentSlides[idx - 1].html !== "__FAILED__") {
              contextSlides.push({ index: idx - 1, title: currentSlides[idx - 1].title, html: currentSlides[idx - 1].html });
            }
            if (idx < currentSlides.length - 1 && currentSlides[idx + 1]?.html && currentSlides[idx + 1].html !== "__FAILED__") {
              contextSlides.push({ index: idx + 1, title: currentSlides[idx + 1].title, html: currentSlides[idx + 1].html });
            }

            const result = await regenerateSlide({
              slide_index: idx,
              content,
              layout: "auto",
              style: genStyleRef.current || state.style,
              context_slides: contextSlides,
            });

            completed++;
            setState((s) => {
              const newSlides = [...s.slides];
              newSlides[idx] = { ...newSlides[idx], html: result.html, quality_score: result.quality_score };
              return {
                ...s,
                slides: newSlides,
                progress: { current: completed, total, batchStart: s.progress?.batchStart, batchEnd: s.progress?.batchEnd },
              };
            });
            return idx;
          })
        );

        // Mark failed slides so user can retry them individually
        for (let j = 0; j < results.length; j++) {
          if (results[j].status === "rejected") {
            const failedIdx = batch[j];
            setState((s) => {
              const newSlides = [...s.slides];
              newSlides[failedIdx] = { ...newSlides[failedIdx], html: "__FAILED__" };
              return { ...s, slides: newSlides };
            });
            completed++;
          }
        }
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "继续生成失败";
      setState((s) => ({ ...s, error: message }));
    } finally {
      setState((s) => {
        // Fire done listeners so history gets saved/updated
        const event: GenerationDoneEvent = {
          content: genContentRef.current,
          style: genStyleRef.current,
          slides: s.slides,
          title: s.title,
          gen_id: genIdRef.current || undefined,
        };
        setTimeout(() => {
          doneListenersRef.current.forEach((fn) => fn(event));
        }, 0);
        return { ...s, generating: false, loading: false, progress: null };
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const contextValue = useMemo(() => ({
    state,
    genId,
    generate,
    cancel,
    regenSlide,
    setActiveSlide,
    updateSlideHtml,
    moveSlide,
    deleteSlide,
    insertSlide,
    duplicateSlide,
    previewFull,
    doExport,
    doExportPdf,
    doExportPptx,
    pdfExporting,
    layouts,
    layoutMap,
    undo,
    canUndo,
    loadSlides,
    setTitle,
    onDone,
    recoverActiveGeneration,
    continueGeneration,
  }), [state, genId, generate, cancel, regenSlide, setActiveSlide, updateSlideHtml, moveSlide, deleteSlide, insertSlide, duplicateSlide, previewFull, doExport, doExportPdf, doExportPptx, pdfExporting, layouts, layoutMap, undo, canUndo, loadSlides, setTitle, onDone, recoverActiveGeneration, continueGeneration]);

  return (
    <GenerationContext.Provider value={contextValue}>
      {children}
    </GenerationContext.Provider>
  );
}
