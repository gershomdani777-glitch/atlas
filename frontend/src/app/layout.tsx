import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";
import { AtlasProvider } from "@/context/AtlasProvider";
import { TopNav } from "@/components/TopNav";
import { PageTransition } from "@/components/PageTransition";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  weight: "400",
  subsets: ["latin"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ATLAS — Decision Control",
  description: "Autonomous paper-trading agent: propose with AI, dispose with deterministic risk.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <AtlasProvider>
          <TopNav />
          <main style={{ flex: 1, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
            <PageTransition>{children}</PageTransition>
          </main>
        </AtlasProvider>
      </body>
    </html>
  );
}
