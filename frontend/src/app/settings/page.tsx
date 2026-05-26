"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import {
  fetchSettings,
  updateSettings,
  testConnection,
  LLMSettings,
  SettingsUpdatePayload,
  fetchPrompts,
  updatePrompt,
  PromptInfo,
} from "@/lib/api";

// --- Version history helpers (from prompts page) ---

interface VersionEntry {
  content: string;
  timestamp: number;
}

function getHistoryKey(filename: string) {
  return `ppt-prompt-history-${filename}`;
}

function getVersions(filename: string): VersionEntry[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(getHistoryKey(filename));
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function saveVersion(filename: string, content: string) {
  const versions = getVersions(filename);
  const newEntry: VersionEntry = { content, timestamp: Date.now() };
  const nonDefault = versions.slice(0, versions.length > 0 ? versions.length - 1 : 0);
  const defaultEntry = versions.length > 0 ? versions[versions.length - 1] : null;
  const updated = [newEntry, ...nonDefault].slice(0, 3);
  if (defaultEntry) {
    updated.push(defaultEntry);
  }
  localStorage.setItem(getHistoryKey(filename), JSON.stringify(updated));
}

function initDefaultVersion(filename: string, content: string) {
  const existing = getVersions(filename);
  if (existing.length === 0) {
    const entry: VersionEntry = { content, timestamp: Date.now() };
    localStorage.setItem(getHistoryKey(filename), JSON.stringify([entry]));
  }
}

function getDefaultContent(filename: string): string | null {
  const versions = getVersions(filename);
  if (versions.length === 0) return null;
  return versions[versions.length - 1]?.content || null;
}

function getNonDefaultVersions(filename: string): VersionEntry[] {
  const versions = getVersions(filename);
  if (versions.length <= 1) return [];
  return versions.slice(0, versions.length - 1);
}

// --- Model Configuration Tab ---

function ModelConfigTab() {
  const [provider, setProvider] = useState("anthropic");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [anthropicBaseUrl, setAnthropicBaseUrl] = useState("");
  const [anthropicModel, setAnthropicModel] = useState("");
  const [anthropicKeyPreview, setAnthropicKeyPreview] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState("");
  const [openaiModel, setOpenaiModel] = useState("");
  const [openaiKeyPreview, setOpenaiKeyPreview] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    fetchSettings()
      .then((s: LLMSettings) => {
        setProvider(s.provider);
        setAnthropicModel(s.anthropic.model);
        setAnthropicBaseUrl(s.anthropic.base_url || "");
        setAnthropicKeyPreview(s.anthropic.key_preview || "");
        setOpenaiModel(s.openai.model);
        setOpenaiBaseUrl(s.openai.base_url || "");
        setOpenaiKeyPreview(s.openai.key_preview || "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const payload: SettingsUpdatePayload = { provider };
      if (provider === "anthropic") {
        if (anthropicKey) payload.anthropic_key = anthropicKey;
        if (anthropicBaseUrl) payload.anthropic_base_url = anthropicBaseUrl;
        payload.anthropic_model = anthropicModel;
      } else {
        if (openaiKey) payload.openai_key = openaiKey;
        if (openaiBaseUrl) payload.openai_base_url = openaiBaseUrl;
        payload.openai_model = openaiModel;
      }
      const res = await testConnection(payload);
      setTestResult({
        success: res.success,
        message: res.success ? res.message || "连接成功" : res.error || "连接失败",
      });
    } catch {
      setTestResult({ success: false, message: "请求失败，请检查后端服务" });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: SettingsUpdatePayload = { provider };
      // Always send both providers' config
      if (anthropicKey) payload.anthropic_key = anthropicKey;
      payload.anthropic_base_url = anthropicBaseUrl;
      payload.anthropic_model = anthropicModel;
      if (openaiKey) payload.openai_key = openaiKey;
      payload.openai_base_url = openaiBaseUrl;
      payload.openai_model = openaiModel;

      await updateSettings(payload);
      showToast("success", "保存成功");
      // Refresh key previews
      const s = await fetchSettings();
      setAnthropicKeyPreview(s.anthropic.key_preview || "");
      setOpenaiKeyPreview(s.openai.key_preview || "");
      setAnthropicKey("");
      setOpenaiKey("");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "保存失败";
      showToast("error", msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-gray-400 text-center py-12">加载中...</div>;
  }

  const activeModel = provider === "anthropic" ? anthropicModel : openaiModel;

  return (
    <div className="space-y-6">
      {/* Provider Switcher Tabs */}
      <div className="flex rounded-lg bg-gray-100 p-1">
        <button
          onClick={() => setProvider("anthropic")}
          className={`flex-1 px-4 py-2.5 text-sm font-medium rounded-md transition-all ${
            provider === "anthropic"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Anthropic Claude
        </button>
        <button
          onClick={() => setProvider("openai")}
          className={`flex-1 px-4 py-2.5 text-sm font-medium rounded-md transition-all ${
            provider === "openai"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          OpenAI 兼容
        </button>
      </div>

      {/* Provider Config — only show active */}
      {provider === "anthropic" ? (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">API Key</label>
            <input
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder={anthropicKeyPreview || "输入 Anthropic API Key"}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-400 mt-1">留空则保持当前密钥不变</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Base URL</label>
            <input
              type="text"
              value={anthropicBaseUrl}
              onChange={(e) => setAnthropicBaseUrl(e.target.value)}
              placeholder="https://api.anthropic.com（留空使用默认）"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Model ID</label>
            <input
              type="text"
              value={anthropicModel}
              onChange={(e) => setAnthropicModel(e.target.value)}
              list="anthropic-models"
              placeholder="claude-sonnet-4-6"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <datalist id="anthropic-models">
              <option value="claude-sonnet-4-6" />
              <option value="claude-opus-4-7" />
              <option value="claude-haiku-4-5" />
            </datalist>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">API Key</label>
            <input
              type="password"
              value={openaiKey}
              onChange={(e) => setOpenaiKey(e.target.value)}
              placeholder={openaiKeyPreview || "输入 API Key"}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-400 mt-1">留空则保持当前密钥不变</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Base URL</label>
            <input
              type="text"
              value={openaiBaseUrl}
              onChange={(e) => setOpenaiBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-400 mt-1">支持 DeepSeek、Ollama、vLLM 等兼容接口</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Model ID</label>
            <input
              type="text"
              value={openaiModel}
              onChange={(e) => setOpenaiModel(e.target.value)}
              list="openai-models"
              placeholder="gpt-4o"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <datalist id="openai-models">
              <option value="gpt-4o" />
              <option value="gpt-4o-mini" />
              <option value="deepseek-chat" />
              <option value="qwen-max" />
            </datalist>
          </div>
        </div>
      )}

      {/* Test result */}
      {testResult && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
            testResult.success
              ? "bg-green-50 text-green-700 border border-green-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          <span className="text-base">{testResult.success ? "✓" : "✗"}</span>
          <span>{testResult.message}</span>
        </div>
      )}

      {/* Actions — prominent buttons */}
      <div className="flex gap-3 pt-3">
        <button
          onClick={handleTest}
          disabled={testing || !activeModel}
          className={`flex-1 px-4 py-3 text-sm font-medium rounded-xl border-2 transition-colors ${
            testing || !activeModel
              ? "border-gray-200 text-gray-400 cursor-not-allowed"
              : "border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50"
          }`}
        >
          {testing ? "测试中..." : "测试连接"}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !activeModel}
          className={`flex-1 px-4 py-3 text-sm font-medium rounded-xl transition-colors ${
            saving || !activeModel
              ? "bg-gray-100 text-gray-400 cursor-not-allowed"
              : "bg-blue-600 text-white hover:bg-blue-700 shadow-md"
          }`}
        >
          {saving ? "保存中..." : "保存配置"}
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 px-4 py-2 rounded-lg text-sm font-medium shadow-lg ${
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}

// --- Prompt Editor Tab ---

function PromptEditorTab() {
  const [prompts, setPrompts] = useState<PromptInfo[]>([]);
  const [selected, setSelected] = useState<PromptInfo | null>(null);
  const [editContent, setEditContent] = useState("");
  const [isDirty, setIsDirty] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lineNumbersRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchPrompts()
      .then((data) => {
        setPrompts(data.prompts);
        if (data.prompts.length > 0) {
          setSelected(data.prompts[0]);
          setEditContent(data.prompts[0].content);
          data.prompts.forEach((p) => initDefaultVersion(p.filename, p.content));
        }
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!historyOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (historyRef.current && !historyRef.current.contains(e.target as Node)) {
        setHistoryOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [historyOpen]);

  const handleSelect = (prompt: PromptInfo) => {
    setSelected(prompt);
    setEditContent(prompt.content);
    setIsDirty(false);
    setHistoryOpen(false);
  };

  const handleContentChange = (value: string) => {
    setEditContent(value);
    setIsDirty(value !== selected?.content);
  };

  const handleSave = async () => {
    if (!selected || !isDirty) return;
    try {
      saveVersion(selected.filename, selected.content);
      await updatePrompt(selected.filename, editContent);
      const updated = prompts.map((p) =>
        p.filename === selected.filename ? { ...p, content: editContent } : p
      );
      setPrompts(updated);
      setSelected({ ...selected, content: editContent });
      setIsDirty(false);
      showToast("success", "保存成功");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "保存失败";
      showToast("error", msg);
    }
  };

  const handleRestoreDefault = () => {
    if (!selected) return;
    const defaultContent = getDefaultContent(selected.filename);
    if (defaultContent == null) return;
    setEditContent(defaultContent);
    setIsDirty(defaultContent !== selected.content);
  };

  const handleRestoreVersion = (version: VersionEntry) => {
    setEditContent(version.content);
    setIsDirty(version.content !== selected?.content);
    setHistoryOpen(false);
  };

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const canRestoreDefault = selected
    ? editContent !== getDefaultContent(selected.filename)
    : false;

  const historyVersions = selected ? getNonDefaultVersions(selected.filename) : [];
  const lines = editContent.split("\n");
  const lineNumbers = lines.map((_, i) => i + 1);

  if (loading) {
    return <div className="text-gray-400 text-center py-12">加载中...</div>;
  }

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)]">
      {/* Toolbar */}
      <div className="flex items-center justify-end gap-3 mb-3">
        <button
          onClick={handleRestoreDefault}
          disabled={!canRestoreDefault}
          className={`px-3 py-1.5 text-sm rounded border transition-colors ${
            canRestoreDefault
              ? "border-gray-300 text-gray-700 hover:bg-gray-50"
              : "border-gray-200 text-gray-400 cursor-not-allowed"
          }`}
        >
          恢复默认
        </button>

        <div className="relative" ref={historyRef}>
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            disabled={historyVersions.length === 0}
            className={`px-3 py-1.5 text-sm rounded border transition-colors ${
              historyVersions.length > 0
                ? "border-gray-300 text-gray-700 hover:bg-gray-50"
                : "border-gray-200 text-gray-400 cursor-not-allowed"
            }`}
          >
            历史版本
          </button>
          {historyOpen && historyVersions.length > 0 && (
            <div className="absolute right-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50">
              {historyVersions.map((v, i) => (
                <button
                  key={i}
                  onClick={() => handleRestoreVersion(v)}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  {new Date(v.timestamp).toLocaleString("zh-CN", {
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={handleSave}
          disabled={!isDirty}
          className={`px-4 py-1.5 text-sm rounded font-medium transition-colors ${
            isDirty
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "bg-gray-100 text-gray-400 cursor-not-allowed"
          }`}
        >
          保存
        </button>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden rounded-lg border border-gray-200">
        {/* Sidebar */}
        <aside className="w-56 border-r border-gray-200 bg-gray-50 overflow-y-auto shrink-0">
          <div className="p-3">
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-2 px-2">
              提示词文件
            </p>
            {prompts.map((prompt) => (
              <button
                key={prompt.filename}
                onClick={() => handleSelect(prompt)}
                className={`w-full text-left px-3 py-2.5 rounded-md mb-1 transition-colors ${
                  selected?.filename === prompt.filename
                    ? "bg-blue-100 text-blue-700 font-medium"
                    : "hover:bg-gray-100 text-gray-700"
                }`}
              >
                <div className="text-sm">{prompt.description}</div>
                <div className="text-xs text-gray-400 mt-0.5 font-mono">
                  {prompt.filename}
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Editor */}
        <section className="flex-1 flex flex-col overflow-hidden">
          {selected && (
            <>
              <div className="px-4 py-2 border-b border-gray-100 bg-white shrink-0">
                <h2 className="text-sm font-medium text-gray-700">
                  {selected.description}
                </h2>
                <p className="text-xs text-gray-400 font-mono mt-0.5">
                  {selected.filename}
                </p>
              </div>
              <div className="flex-1 flex relative overflow-hidden">
                <div
                  ref={lineNumbersRef}
                  className="w-10 bg-gray-50 border-r border-gray-100 overflow-hidden text-right pr-2 pt-4 font-mono text-xs text-gray-300 leading-relaxed select-none"
                  style={{ height: "100%" }}
                >
                  {lineNumbers.map((n) => (
                    <div key={n}>{n}</div>
                  ))}
                </div>
                <textarea
                  ref={textareaRef}
                  value={editContent}
                  onChange={(e) => handleContentChange(e.target.value)}
                  onScroll={(e) => {
                    if (lineNumbersRef.current) {
                      lineNumbersRef.current.scrollTop = e.currentTarget.scrollTop;
                    }
                  }}
                  spellCheck={false}
                  className="flex-1 h-full p-4 pl-3 font-mono text-sm leading-relaxed resize-none focus:outline-none bg-white text-gray-800"
                  style={{ tabSize: 2 }}
                />
              </div>
            </>
          )}
        </section>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 px-4 py-2 rounded-lg text-sm font-medium shadow-lg ${
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}

// --- Main Settings Page ---

type TabId = "model" | "prompts";

export default function SettingsPageWrapper() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center"><p className="text-gray-400">加载中...</p></div>}>
      <SettingsPage />
    </Suspense>
  );
}

function SettingsPage() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") === "prompts" ? "prompts" : "model";
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);

  const tabs: { id: TabId; label: string }[] = [
    { id: "model", label: "模型配置" },
    { id: "prompts", label: "Prompt 编辑" },
  ];

  return (
    <main className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Back link */}
        <a
          href="/"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors mb-6"
        >
          ← 返回首页
        </a>

        {/* Page title */}
        <h1 className="text-2xl font-bold text-gray-900 mb-6">设置</h1>

        {/* Tab switcher */}
        <div className="flex border-b border-gray-200 mb-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
                activeTab === tab.id
                  ? "text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
              {activeTab === tab.id && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          {activeTab === "model" && <ModelConfigTab />}
          {activeTab === "prompts" && <PromptEditorTab />}
        </div>
      </div>
    </main>
  );
}
