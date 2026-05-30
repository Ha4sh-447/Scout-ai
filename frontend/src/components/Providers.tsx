"use client";

import { SessionProvider } from "next-auth/react";
import { ToastProvider } from "@/lib/toast";
import { ToastContainer } from "@/components/ToastContainer";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <SessionProvider refetchOnWindowFocus={false}>
        {children}
      </SessionProvider>
      <ToastContainer />
    </ToastProvider>
  );
}
