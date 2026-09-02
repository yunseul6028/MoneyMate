import type { MetadataRoute } from "next";

// PWA — '홈 화면에 추가' 시 M 아이콘 앱으로 설치(standalone). 웹앱·위젯이 한 배포.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MoneyMate",
    short_name: "MoneyMate",
    description: "가계부를 안 써도 챙겨주는 대학생 금융 친구 AI",
    start_url: "/",
    display: "standalone",
    background_color: "#6c5ce7",
    theme_color: "#6c5ce7",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
