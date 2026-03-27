import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: "Scout AI | Your Personal Job Agent",
  description: "Automate your job search with agentic discovery and resume matching.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-outfit">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
