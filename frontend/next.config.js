/** @type {import('next').NextConfig} */
const nextConfig = {
  // Optional: Change the output directory if needed (default is 'out')
  // distDir: 'dist',
  images: { unoptimized: true } // Required for static exports if using Next.js <Image />
};

module.exports = nextConfig;