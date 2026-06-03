/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "ui-avatars.com" },
      { protocol: "https", hostname: "**" },
    ],
  },
  async rewrites() {
    const api = process.env.BACKEND_URL ?? "http://localhost:8000";
    return [{ source: "/api/backend/:path*", destination: `${api}/api/v1/:path*` }];
  },
};

export default nextConfig;
