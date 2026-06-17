import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: undefined,
      precompress: false,
      strict: true
    }),
    paths: {
      // Set BASE_PATH at build time for GitHub Pages project sites, e.g.
      // BASE_PATH=/fix_everything_button npm run build
      base: process.env.BASE_PATH ?? ''
    }
  }
};

export default config;
