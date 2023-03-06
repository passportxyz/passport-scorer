/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: false,
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
