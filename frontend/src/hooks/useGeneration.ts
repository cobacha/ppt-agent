"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  SlideDTO,
  regenerateSlide,
  exportPresentation,
  exportPdf,
  fetchLayouts,
  fetchOutline,
  generateSlidesBatch,
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
  title: string;
}

export function useGeneration() {
  const [state, setState] = useState<EditorState>({
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
    title: "",
  });

  const abortRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Undo stack
  const undoStackRef = useRef<SlideDTO[][]>([]);
  const MAX_UNDO = 10;

  const pushUndo = useCallback((slides: SlideDTO[]) => {
    undoStackRef.current = [...undoStackRef.current.slice(-(MAX_UNDO - 1)), slides];
  }, []);

  const undo = useCallback(() => {
    const stack = undoStackRef.current;
    if (stack.length === 0) return;
    const prev = stack[stack.length - 1];
    undoStackRef.current = stack.slice(0, -1);
    setState((s) => ({ ...s, slides: prev }));
  }, []);

  const canUndo = undoStackRef.current.length > 0;

  const generateStreaming = useCallback((content: string, style: string) => {
    // Cancel any previous stream
    abortControllerRef.current?.abort();

    setState((s) => ({
      ...s,
      loading: true,
      generating: true,
      error: null,
      style,
      slides: [],
      progress: { current: 0, total: 0 },
      thinking: "",
    }));

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
        setState((s) => ({
          ...s,
          slides: placeholders,
          title: outline.title || s.title || "Untitled",
          loading: false,
          thinking: "",
          progress: { current: 0, total },
          expanding: { current: 0, total },
        }));
      },
      onExpanded: (expanded) => {
        setState((s) => {
          const newSlides = [...s.slides];
          if (newSlides[expanded.index]) {
            newSlides[expanded.index] = {
              ...newSlides[expanded.index],
              detailed_content: expanded.detailed_content,
            };
          }
          return {
            ...s,
            slides: newSlides,
            expanding: {
              current: (s.expanding?.current || 0) + 1,
              total: s.expanding?.total || s.slides.length,
            },
          };
        });
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
          return {
            ...s,
            slides: newSlides,
            activeIndex: slide.index,
            expanding: null,
            progress: { current: completed, total: s.progress?.total || newSlides.length },
          };
        });
      },
      onError: (error) => {
        if (error.index != null) {
          // Slide-level error — mark that slide as failed but continue
          setState((s) => {
            const newSlides = [...s.slides];
            if (newSlides[error.index!]) {
              newSlides[error.index!] = {
                ...newSlides[error.index!],
                html: "__FAILED__",
              };
            }
            return { ...s, slides: newSlides, error: `第 ${error.index! + 1} 页生成失败: ${error.message}` };
          });
        } else {
          setState((s) => ({ ...s, error: error.message }));
        }
      },
      onDone: () => {
        setState((s) => ({ ...s, generating: false, progress: null }));
        abortControllerRef.current = null;
      },
    });

    abortControllerRef.current = controller;
  }, []);

  const generateBatch = useCallback(async (content: string, style: string) => {
    abortRef.current = false;
    setState((s) => ({
      ...s,
      loading: true,
      generating: true,
      error: null,
      style,
      slides: [],
      progress: { current: 0, total: 0 },
    }));

    try {
      // Stage 1: Get outline
      const outline = await fetchOutline(content, style);
      const total = outline.slides.length;

      // Initialize placeholder slides
      const placeholders: SlideDTO[] = outline.slides.map((s, i) => ({
        index: i,
        title: s.title,
        html: "",
        quality_score: 0,
      }));

      setState((s) => ({
        ...s,
        slides: placeholders,
        loading: false,
        progress: { current: 0, total },
      }));

      // Stage 2: Generate slides in batches of 3
      const BATCH_SIZE = 3;
      const contextSlides: Record<string, unknown>[] = [];

      for (let batchStart = 0; batchStart < outline.slides.length; batchStart += BATCH_SIZE) {
        if (abortRef.current) break;

        const batchEnd = Math.min(batchStart + BATCH_SIZE, outline.slides.length);
        const batchSpecs = outline.slides.slice(batchStart, batchEnd).map((spec) => ({
          title: spec.title,
          bullets: spec.bullets,
          content_type: spec.content_type,
          suggested_layout: spec.suggested_layout,
        }));

        setState((s) => ({
          ...s,
          progress: { current: batchStart, total, batchStart, batchEnd },
        }));

        let batchResult: { results: { html: string; quality_score: number }[] };

        try {
          batchResult = await generateSlidesBatch({
            slide_specs: batchSpecs,
            style,
            start_index: batchStart,
            context_slides: contextSlides.slice(-3),
          });
        } catch (err: unknown) {
          // Retry once after 2 seconds
          await new Promise((resolve) => setTimeout(resolve, 2000));
          try {
            batchResult = await generateSlidesBatch({
              slide_specs: batchSpecs,
              style,
              start_index: batchStart,
              context_slides: contextSlides.slice(-3),
            });
          } catch (retryErr: unknown) {
            // Keep already-generated slides, show error
            const message = retryErr instanceof Error ? retryErr.message : "批量生成失败";
            setState((s) => ({
              ...s,
              generating: false,
              progress: null,
              error: `第 ${batchStart + 1}-${batchEnd} 页生成失败: ${message}`,
            }));
            return;
          }
        }

        // Update all slides in this batch
        for (let j = 0; j < batchResult.results.length; j++) {
          const globalIdx = batchStart + j;
          const result = batchResult.results[j];
          const spec = outline.slides[globalIdx];

          setState((s) => {
            const newSlides = [...s.slides];
            newSlides[globalIdx] = {
              index: globalIdx,
              title: spec.title,
              html: result.html,
              quality_score: result.quality_score,
            };
            return { ...s, slides: newSlides, activeIndex: globalIdx, progress: { current: globalIdx + 1, total } };
          });

          contextSlides.push({
            index: globalIdx,
            title: spec.title,
            layout_used: spec.suggested_layout,
            html: result.html,
          });
        }
      }

      setState((s) => ({ ...s, generating: false, progress: null }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "生成失败";
      setState((s) => ({
        ...s,
        loading: false,
        generating: false,
        progress: null,
        error: message,
      }));
    }
  }, []);

  // Default to streaming; fall back to batch via generateBatch
  const generate = generateStreaming;

  const regenSlide = useCallback(
    async (index: number, content: string, layout: string, prompt?: string) => {
      setState((s) => {
        pushUndo(s.slides);
        return { ...s, loading: true, error: null };
      });
      try {
        const contextSlides: Record<string, unknown>[] = [];
        if (index > 0 && state.slides[index - 1]?.html) {
          contextSlides.push({
            index: index - 1,
            title: state.slides[index - 1].title,
            html: state.slides[index - 1].html,
          });
        }
        if (index < state.slides.length - 1 && state.slides[index + 1]?.html) {
          contextSlides.push({
            index: index + 1,
            title: state.slides[index + 1].title,
            html: state.slides[index + 1].html,
          });
        }

        const fullContent = prompt
          ? `${content}\n\n[生成指令]: ${prompt}`
          : content;

        const result = await regenerateSlide({
          slide_index: index,
          content: fullContent,
          layout,
          style: state.style,
          context_slides: contextSlides,
        });

        setState((s) => {
          const newSlides = [...s.slides];
          newSlides[index] = {
            ...newSlides[index],
            html: result.html,
            quality_score: result.quality_score,
          };
          return { ...s, slides: newSlides, loading: false };
        });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "重新生成失败";
        setState((s) => ({ ...s, loading: false, error: message }));
      }
    },
    [state.style, state.slides, pushUndo]
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
      // Reindex
      const reindexed = newSlides.map((slide, i) => ({ ...slide, index: i }));
      // Adjust activeIndex to follow the moved slide
      let newActiveIndex = s.activeIndex;
      if (s.activeIndex === fromIndex) {
        newActiveIndex = toIndex;
      } else if (fromIndex < s.activeIndex && toIndex >= s.activeIndex) {
        newActiveIndex = s.activeIndex - 1;
      } else if (fromIndex > s.activeIndex && toIndex <= s.activeIndex) {
        newActiveIndex = s.activeIndex + 1;
      }
      return { ...s, slides: reindexed, activeIndex: newActiveIndex };
    });
  }, [pushUndo]);

  const deleteSlide = useCallback((index: number) => {
    setState((s) => {
      if (s.slides.length <= 1) return s; // Don't delete last slide
      pushUndo(s.slides);
      const newSlides = s.slides.filter((_, i) => i !== index).map((slide, i) => ({ ...slide, index: i }));
      let newActiveIndex = s.activeIndex;
      if (s.activeIndex >= newSlides.length) {
        newActiveIndex = newSlides.length - 1;
      } else if (s.activeIndex > index) {
        newActiveIndex = s.activeIndex - 1;
      }
      return { ...s, slides: newSlides, activeIndex: newActiveIndex };
    });
  }, [pushUndo]);

  const insertSlide = useCallback((afterIndex: number) => {
    setState((s) => {
      pushUndo(s.slides);
      const insertAt = afterIndex + 1;
      const placeholder: SlideDTO = {
        index: insertAt,
        title: "空白页",
        html: "",
        quality_score: 0,
      };
      const newSlides = [...s.slides];
      newSlides.splice(insertAt, 0, placeholder);
      const reindexed = newSlides.map((slide, i) => ({ ...slide, index: i }));
      return { ...s, slides: reindexed, activeIndex: insertAt };
    });
  }, [pushUndo]);

  const previewFull = useCallback(async () => {
    const slides = state.slides.map((s) => ({ html: s.html }));
    const result = await exportPresentation(slides, state.style, state.title);
    const blob = new Blob([result.html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }, [state.slides, state.style, state.title]);

  const doExport = useCallback(async () => {
    const slides = state.slides.map((s) => ({ html: s.html }));
    const result = await exportPresentation(slides, state.style, state.title);
    const blob = new Blob([result.html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename || `${state.title || "presentation"}.html`;
    a.click();
    URL.revokeObjectURL(url);
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

  const [layouts, setLayouts] = useState<string[]>([]);

  const loadSlides = useCallback((slides: SlideDTO[], style: string) => {
    setState((s) => ({
      ...s,
      slides,
      style,
      activeIndex: 0,
      loading: false,
      generating: false,
      error: null,
    }));
  }, []);

  useEffect(() => {
    fetchLayouts().then((data) => setLayouts(Object.keys(data.layouts)));
  }, []);

  const setTitle = useCallback((title: string) => {
    setState((s) => ({ ...s, title }));
  }, []);

  const cancel = useCallback(() => {
    abortRef.current = true;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setState((s) => ({ ...s, loading: false, generating: false, progress: null, thinking: "" }));
  }, []);

  return {
    state,
    generate,
    generateStreaming,
    generateBatch,
    regenSlide,
    setActiveSlide,
    updateSlideHtml,
    moveSlide,
    deleteSlide,
    insertSlide,
    previewFull,
    doExport,
    doExportPdf,
    pdfExporting,
    layouts,
    undo,
    canUndo,
    loadSlides,
    cancel,
    setTitle,
  };
}
