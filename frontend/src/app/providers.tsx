"use client";

import { GenerationProvider } from "@/context/GenerationContext";

export default function Providers({ children }: { children: React.ReactNode }) {
  return <GenerationProvider>{children}</GenerationProvider>;
}
