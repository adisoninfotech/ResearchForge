import type { NextConfig } from 'next';

const apiProxyTarget = process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000';

const nextConfig: NextConfig = {
  output: 'standalone',
  transpilePackages: ['@researchforge/ui', '@researchforge/shared-types'],
  reactStrictMode: true,
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiProxyTarget}/api/:path*`,
      },
      {
        source: '/health/:path*',
        destination: `${apiProxyTarget}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;
