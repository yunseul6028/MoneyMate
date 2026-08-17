import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MoneyMate 💸",
  description: "대학생을 위한 Proactive 금융 친구 AI",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  // 노치/상태바 영역까지 화면을 꽉 채우고(env safe-area 활성화),
  // 상단 브라우저 UI를 헤더 보라색으로 톤 맞춤.
  viewportFit: "cover",
  themeColor: "#6c5ce7",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
