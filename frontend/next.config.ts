import path from "path";
import { fileURLToPath } from "url";
import type { NextConfig } from "next";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  turbopack: {
    root: frontendRoot,
  },
  async rewrites() {
    const backend = process.env.RAG_API_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/rag/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
