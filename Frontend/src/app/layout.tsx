import type { Metadata } from "next";
import { Be_Vietnam_Pro, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "katex/dist/katex.min.css";
const body = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});
const mono = JetBrains_Mono({ subsets:["latin"], variable:"--font-mono", display:"swap" });
export const metadata: Metadata = {
  title: "StudyBot TLU — Trợ lý học vụ Trường Đại học Thủy lợi",
  description: "Hỏi đáp quy chế đào tạo, học bổng, học phí, chuẩn đầu ra của Trường Đại học Thủy lợi — kèm văn bản gốc để đối chiếu.",
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className={`${body.variable} ${mono.variable} font-sans bg-tlu-ground text-tlu-ink antialiased`}>
        {children}
      </body>
    </html>
  );
}
