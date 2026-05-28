const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface SlideDTO {
  index: number;
  title: string;
  html: string;
  quality_score: number;
  bullets?: string[];
  detailed_content?: string;
}

export interface GenerateResponse {
  slides: SlideDTO[];
  full_html: string;
  iterations: number;
  score: number;
  issues: string[];
}

export interface StylePreset {
  id: string;
  name: string;
  vibe: string;
  colors: Record<string, string>;
  fonts: Record<string, string>;
}

export interface LayoutInfo {
  description: string;
  best_for: string[];
  css_class: string;
}

export async function fetchStyles(): Promise<{ presets: StylePreset[] }> {
  const res = await fetch(`${API_BASE}/api/styles`);
  if (!res.ok) throw new Error(`Failed to fetch styles: ${res.statusText}`);
  return res.json();
}

export async function fetchLayouts(): Promise<{ layouts: Record<string, LayoutInfo> }> {
  const res = await fetch(`${API_BASE}/api/layouts`);
  if (!res.ok) throw new Error(`Failed to fetch layouts: ${res.statusText}`);
  return res.json();
}

export async function generatePresentation(
  content: string,
  style: string
): Promise<GenerateResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);
  try {
    const res = await fetch(`${API_BASE}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, style, max_iterations: 2 }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Generation failed: ${res.statusText}`);
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

export async function regenerateSlide(params: {
  slide_index: number;
  content: string;
  layout: string;
  style: string;
  context?: string;
  context_slides?: Record<string, unknown>[];
}): Promise<{ html: string; quality_score: number }> {
  const res = await fetch(`${API_BASE}/api/regen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Regeneration failed: ${res.statusText}`);
  return res.json();
}

export interface OutlineSlide {
  index: number;
  title: string;
  bullets: string[];
  content_type: string;
  suggested_layout: string;
}

export interface OutlineResponse {
  title: string;
  subtitle: string;
  slides: OutlineSlide[];
  gen_id?: string;
}

export async function fetchOutline(
  content: string,
  style: string
): Promise<OutlineResponse> {
  const res = await fetch(`${API_BASE}/api/outline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, style }),
  });
  if (!res.ok) throw new Error(`Outline failed: ${res.statusText}`);
  return res.json();
}

export async function generateSlide(params: {
  slide_spec: Record<string, unknown>;
  style: string;
  slide_index: number;
  context_slides: Record<string, unknown>[];
}): Promise<{ html: string; quality_score: number }> {
  const res = await fetch(`${API_BASE}/api/generate-slide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Slide generation failed: ${res.statusText}`);
  return res.json();
}

export async function generateSlidesBatch(params: {
  slide_specs: Record<string, unknown>[];
  style: string;
  start_index: number;
  context_slides: Record<string, unknown>[];
}): Promise<{ results: { html: string; quality_score: number }[] }> {
  const res = await fetch(`${API_BASE}/api/generate-slides-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Batch generation failed: ${res.statusText}`);
  return res.json();
}

export async function exportPresentation(
  slides: { html: string }[],
  style: string,
  title?: string
): Promise<{ html: string; filename: string }> {
  const res = await fetch(`${API_BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slides, style, title }),
  });
  if (!res.ok) throw new Error(`Export failed: ${res.statusText}`);
  return res.json();
}

export async function exportPdf(
  slides: { html: string }[],
  style: string
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/export-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slides, style }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `PDF export failed: ${res.statusText}`);
  }
  return res.blob();
}

export async function exportPptx(
  slides: { html: string }[],
  style: string,
  title?: string
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/export-pptx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slides, style, title }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `PPTX export failed: ${res.statusText}`);
  }
  return res.blob();
}

// --- Prompt Management ---

export interface PromptInfo {
  name: string;
  filename: string;
  content: string;
  description: string;
}

export async function fetchPrompts(): Promise<{ prompts: PromptInfo[] }> {
  const res = await fetch(`${API_BASE}/api/prompts`);
  if (!res.ok) throw new Error(`Failed to fetch prompts: ${res.statusText}`);
  return res.json();
}

export async function fetchPrompt(filename: string): Promise<PromptInfo> {
  const res = await fetch(`${API_BASE}/api/prompts/${filename}`);
  if (!res.ok) throw new Error(`Failed to fetch prompt: ${res.statusText}`);
  return res.json();
}

export async function updatePrompt(
  filename: string,
  content: string
): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/prompts/${filename}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Failed to update prompt: ${res.statusText}`);
  return res.json();
}

// --- History ---

export interface HistoryItem {
  id: string;
  created_at: string;
  content: string;
  style: string;
  slide_count: number;
  title?: string;
  first_slide_html?: string;
  status?: string;
}

export interface HistoryDetail extends HistoryItem {
  slides: SlideDTO[];
}

export async function fetchHistory(limit = 20): Promise<{ items: HistoryItem[] }> {
  const res = await fetch(`${API_BASE}/api/history?limit=${limit}`);
  if (!res.ok) throw new Error("加载历史失败");
  return res.json();
}

export async function fetchHistoryDetail(id: string): Promise<HistoryDetail> {
  const res = await fetch(`${API_BASE}/api/history/${id}`);
  if (!res.ok) throw new Error("加载历史详情失败");
  return res.json();
}

export async function saveHistory(
  content: string,
  style: string,
  slides: { index: number; title: string; html: string; quality_score: number }[],
  gen_id?: string,
  title?: string
): Promise<{ id: string }> {
  const res = await fetch(`${API_BASE}/api/history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, style, slides, gen_id, title }),
  });
  if (!res.ok) throw new Error("保存历史失败");
  return res.json();
}

export interface ActiveGeneration {
  id: string;
  created_at: string;
  content: string;
  style: string;
  slide_count: number;
  slides: SlideDTO[];
  status: string;
  title: string;
}

export async function fetchActiveGeneration(): Promise<ActiveGeneration | null> {
  const res = await fetch(`${API_BASE}/api/active-generation`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.active || null;
}

export async function deleteHistory(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/history/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("删除失败");
}

export async function importUrl(url: string): Promise<{ content: string; title: string; word_count: number }> {
  const res = await fetch(`${API_BASE}/api/import-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "导入失败" }));
    throw new Error(err.detail || "导入失败");
  }
  return res.json();
}

// --- Settings ---

export interface ProviderConfig {
  has_key: boolean;
  key_preview: string;
  base_url: string;
  model: string;
}

export interface LLMSettings {
  provider: string;
  anthropic: ProviderConfig;
  openai: ProviderConfig;
}

export interface SettingsUpdatePayload {
  provider?: string;
  anthropic_key?: string;
  anthropic_base_url?: string;
  anthropic_model?: string;
  openai_key?: string;
  openai_base_url?: string;
  openai_model?: string;
}

export async function fetchSettings(): Promise<LLMSettings> {
  const res = await fetch(`${API_BASE}/api/settings`);
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}

export async function updateSettings(settings: SettingsUpdatePayload): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "保存失败" }));
    throw new Error(err.detail || "保存失败");
  }
  return res.json();
}

export async function testConnection(settings: SettingsUpdatePayload): Promise<{ success: boolean; message?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/api/settings/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  return res.json();
}
