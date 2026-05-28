import { OutlineResponse } from "./api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface SSESlideEvent {
  index: number;
  html: string;
  quality_score: number;
  title: string;
}

export interface SSEErrorEvent {
  message: string;
  index?: number;
}

export interface SSEExpandedEvent {
  index: number;
  title: string;
  detailed_content: string;
  key_visual: string;
}

export interface SSEBatchStartEvent {
  start: number;
  end: number;
}

export interface SSESlideStepEvent {
  index: number;
  step: "expanding" | "rendering";
  title: string;
}

export interface SSECallbacks {
  onOutline: (outline: OutlineResponse) => void;
  onExpanded?: (expanded: SSEExpandedEvent) => void;
  onBatchStart?: (batch: SSEBatchStartEvent) => void;
  onSlideStep?: (event: SSESlideStepEvent) => void;
  onSlide: (slide: SSESlideEvent) => void;
  onError: (error: SSEErrorEvent) => void;
  onDone: (data?: { gen_id?: string }) => void;
  onThinking?: (text: string) => void;
  onReconnect?: (attempt: number) => void;
}

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;

/**
 * Connect to the SSE streaming endpoint using fetch + ReadableStream.
 * Returns an AbortController to cancel the stream.
 * Automatically retries up to 3 times on non-abort failures.
 */
export function streamGeneration(
  content: string,
  style: string,
  callbacks: SSECallbacks,
  language: string = "zh",
  aspectRatio: string = "16:9"
): AbortController {
  const controller = new AbortController();
  const requestId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  (async () => {
    let retryCount = 0;
    let outlineReceived = false;

    while (retryCount <= MAX_RETRIES) {
      try {
        const res = await fetch(`${API_BASE}/api/generate-stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content, style, language, aspect_ratio: aspectRatio, request_id: requestId }),
          signal: controller.signal,
        });

        if (!res.ok) {
          let errorMsg = `请求失败: ${res.status} ${res.statusText}`;
          try {
            const errBody = await res.json();
            if (errBody.detail) errorMsg = errBody.detail;
          } catch {}
          callbacks.onError({ message: errorMsg });
          callbacks.onDone();
          return;
        }

        const reader = res.body?.getReader();
        if (!reader) {
          callbacks.onError({ message: "无法读取响应流" });
          callbacks.onDone();
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent = "";
        let currentData = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete lines from buffer
          let newlineIdx: number;
          while ((newlineIdx = buffer.indexOf("\n")) !== -1) {
            const line = buffer.slice(0, newlineIdx);
            buffer = buffer.slice(newlineIdx + 1);

            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              // SSE spec: multi-line data fields are concatenated with newlines
              currentData = currentData ? currentData + "\n" + line.slice(6) : line.slice(6);
            } else if (line === "" && currentEvent) {
              const eventType = currentEvent;
              const eventData = currentData;
              currentEvent = "";
              currentData = "";
              try {
                const data = JSON.parse(eventData);
                switch (eventType) {
                  case "thinking":
                    callbacks.onThinking?.(data.text);
                    break;
                  case "outline":
                    if (!outlineReceived) {
                      callbacks.onOutline(data as OutlineResponse);
                      outlineReceived = true;
                    }
                    break;
                  case "expanded":
                    callbacks.onExpanded?.(data as SSEExpandedEvent);
                    break;
                  case "batch_start":
                    callbacks.onBatchStart?.(data as SSEBatchStartEvent);
                    break;
                  case "slide_step":
                    callbacks.onSlideStep?.(data as SSESlideStepEvent);
                    break;
                  case "slide":
                    callbacks.onSlide(data as SSESlideEvent);
                    break;
                  case "error":
                    callbacks.onError(data as SSEErrorEvent);
                    break;
                  case "resume":
                    callbacks.onDone(data as { gen_id?: string });
                    return;
                  case "done":
                    callbacks.onDone(data as { gen_id?: string });
                    return;
                }
              } catch {
                // Ignore JSON parse errors for partial data
              }
            }
          }
        }

        // Stream ended normally without a done event — treat as complete
        callbacks.onDone();
        return;
      } catch (err: unknown) {
        if ((err as Error).name === "AbortError") return;

        retryCount++;
        if (retryCount > MAX_RETRIES) {
          callbacks.onError({
            message: err instanceof Error ? err.message : "流式生成连接失败",
          });
          callbacks.onDone();
          return;
        }

        // Notify about reconnection attempt
        callbacks.onReconnect?.(retryCount);

        // Wait before retrying
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      }
    }
  })();

  return controller;
}
