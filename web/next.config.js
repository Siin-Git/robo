/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep parallel local previews from sharing generated build files.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Backend address stays server-side (thin proxy route); browsers only
  // ever see same-origin /api. No rewrites needed.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
