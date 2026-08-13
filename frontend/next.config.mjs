/** @type {import('next').NextConfig} */

// 프론트(:3000)의 /api 요청을 백엔드 FastAPI(:8000)로 프록시 → CORS 걱정 없음.
const backend = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
