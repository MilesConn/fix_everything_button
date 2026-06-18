<script>
  let { children } = $props();
</script>

{@render children()}

<style>
  :global(:root) {
    --ink: #1a1a1a;
    --muted: #5a5a5a;
    --rule: #e6e6e6;
    --accent: #d73027;
    --max: 680px;
  }
  :global(html) { scroll-behavior: smooth; }
  :global(body) {
    margin: 0;
    color: var(--ink);
    background: #fff;
    font-family: Georgia, 'Times New Roman', serif;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }
  :global(h1, h2, h3) {
    font-family: Georgia, 'Times New Roman', serif;
    line-height: 1.15;
    letter-spacing: -0.01em;
  }
  :global(.sans) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }
  :global(a) { color: var(--accent); }
</style>
