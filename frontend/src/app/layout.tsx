import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Conversion Engine",
  description: "Automated Lead Generation for Tenacious Consulting",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">
        <div className="flex">
          <aside className="w-64 bg-slate-900 min-h-screen p-6 fixed">
            <h1 className="text-white text-xl font-bold mb-1">Conversion Engine</h1>
            <p className="text-slate-400 text-xs mb-8">Tenacious Consulting</p>
            <nav className="space-y-2">
              <a href="/" className="block px-3 py-2 rounded text-sm text-white bg-slate-700 hover:bg-slate-600">
                Dashboard
              </a>
              <a href="/prospects" className="block px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-700">
                Prospects
              </a>
              <a href="/enrich" className="block px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-700">
                Enrich
              </a>
              <a href="/inbox" className="block px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-700">
                Inbox
              </a>
              <a href="/analytics" className="block px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-700">
                Analytics
              </a>
              <a href="/settings" className="block px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-700">
                Settings
              </a>
            </nav>
            <div className="absolute bottom-6 left-6 right-6">
              <div className="px-3 py-2 rounded bg-slate-800 text-xs text-slate-400">
                <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-2"></span>
                Kill Switch: SAFE
              </div>
            </div>
          </aside>
          <main className="ml-64 flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
