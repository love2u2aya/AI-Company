import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "パパママ社",
  description: "動画配信の広告収益で稼ぐ擬似会社 — エージェント組織ダッシュボード",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <header className="border-b border-gray-800 bg-gray-900">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-8">
            <Link href="/" className="text-xl font-bold text-amber-400 tracking-tight">
              📺 パパママ社
            </Link>
            <nav className="flex gap-6 text-sm text-gray-400">
              <Link href="/" className="hover:text-white transition-colors">ダッシュボード</Link>
              <Link href="/org" className="hover:text-white transition-colors">組織図</Link>
              <Link href="/members" className="hover:text-white transition-colors">メンバー</Link>
              <Link href="/tickets" className="hover:text-white transition-colors">チケット</Link>
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
