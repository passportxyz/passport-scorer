/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  async redirects() {
    return [
      {
        source: "/dashboard",
        destination: "/dashboard/scorer",
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
