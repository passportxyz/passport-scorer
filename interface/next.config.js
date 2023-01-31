/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  async redirects() {
    return [
      {
        source: "/dashboard",
        destination: "/dashboard/community",
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
