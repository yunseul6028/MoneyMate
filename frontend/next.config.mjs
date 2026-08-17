/** @type {import('next').NextConfig} */

// /api/* 는 같은 프로젝트의 FastAPI(Python 서버리스 함수)가 처리한다.
//  - Vercel(배포): api/index.py 함수로 rewrite (같은 도메인, CORS 없음)
//  - 로컬 개발: 따로 띄운 uvicorn(:8000)으로 프록시
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: process.env.VERCEL
          ? "/api/"
          : "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
