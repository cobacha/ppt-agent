"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { fetchHistory, saveHistory, deleteHistory, HistoryItem, SlideDTO } from "@/lib/api";

export type { HistoryItem };

export function useHistory() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const lastFetchRef = useRef(0);

  const reload = useCallback(() => {
    setLoading(true);
    lastFetchRef.current = Date.now();
    fetchHistory(20)
      .then((data) => setHistory(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  // Re-fetch when page becomes visible (user navigates back via SPA or tab switch)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible" && Date.now() - lastFetchRef.current > 3000) {
        reload();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    // Also re-fetch on focus (covers SPA back-navigation within same tab)
    const handleFocus = () => {
      if (Date.now() - lastFetchRef.current > 3000) {
        reload();
      }
    };
    window.addEventListener("focus", handleFocus);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", handleFocus);
    };
  }, [reload]);

  const saveToHistory = useCallback(
    async (entry: {
      style: string;
      content: string;
      slides: SlideDTO[];
      gen_id?: string;
      title?: string;
    }): Promise<string | null> => {
      try {
        const result = await saveHistory(entry.content, entry.style, entry.slides, entry.gen_id, entry.title);
        reload();
        return result.id;
      } catch {
        return null;
      }
    },
    [reload]
  );

  const deleteItem = useCallback(
    async (id: string): Promise<boolean> => {
      try {
        await deleteHistory(id);
        reload();
        return true;
      } catch {
        return false;
      }
    },
    [reload]
  );

  return { history, loading, saveToHistory, deleteItem, reload };
}
