import { ImageResponse } from "next/og";

// iOS 홈화면 아이콘(apple-touch-icon). iOS 가 모서리를 알아서 둥글게 처리하므로
// 정사각형 그라데이션으로 꽉 채운다. next/og(resvg)로 SVG → PNG 렌더.
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

const SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180" viewBox="0 0 512 512"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6c5ce7"/><stop offset="1" stop-color="#a29bfe"/></linearGradient></defs><rect width="512" height="512" fill="url(#g)"/><path d="M168 366 L168 156 L256 298 L344 156 L344 366" fill="none" stroke="#ffffff" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/><circle cx="384" cy="140" r="34" fill="#ffd76a"/></svg>`;

export default function AppleIcon() {
  const uri = `data:image/svg+xml;base64,${btoa(SVG)}`;
  return new ImageResponse(
    (
      // eslint-disable-next-line @next/next/no-img-element
      <img width={180} height={180} src={uri} alt="MoneyMate" />
    ),
    { ...size }
  );
}
