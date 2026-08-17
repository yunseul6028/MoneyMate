/** @type {import('next').NextConfig} */

// 프론트의 /api 요청을 백엔드 FastAPI 로 프록시 → CORS 걱정 없음.
//  - Vercel(배포): 배포된 백엔드로. BACKEND_URL 환경변수로 언제든 덮어쓸 수 있음.
//  - 로컬 개발: localhost:8000
const backend =
  process.env.BACKEND_URL ||
  (process.env.VERCEL
    ? "https://backend-ten-delta-94.vercel.app"
    : "http://localhost:8000");

const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
