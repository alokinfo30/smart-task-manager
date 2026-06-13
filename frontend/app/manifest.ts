import { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Smart Task Manager',
    short_name: 'STM',
    description: 'AI-powered offline-first task and expense manager.',
    start_url: '/',
    display: 'standalone',
    background_color: '#F9FAFB',
    theme_color: '#3B82F6',
    icons: [
      {
        src: 'https://cdn-icons-png.flaticon.com/512/2098/2098402.png',
        sizes: '192x192',
        type: 'image/png',
      },
      {
        src: 'https://cdn-icons-png.flaticon.com/512/2098/2098402.png',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
  };
}