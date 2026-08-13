import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "#6c5ce7",
        brand2: "#a29bfe",
        accent: "#00b894",
        warn: "#ff7675",
        ink: "#1c1c28",
        muted: "#8a8a9a",
        line: "#ececf2",
      },
      maxWidth: { phone: "440px" },
    },
  },
  plugins: [],
};

export default config;
