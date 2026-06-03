import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AlphaPulse — Stock Research & Analysis",
  description:
    "Institutional-grade ticker profiles, analyst research, and real-time watchlists. A Seeking Alpha-style platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Navbar />
        {children}
      </body>
    </html>
  );
}
