<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { loadJSON } from '$lib/data.js';

  const PER_PAGE = 24;
  const STORAGE_KEY = 'sf_upzone_annotations_v1';
  const KEY_STORAGE = 'sf_gmaps_key_v1';

  let features = $state([]);
  let loadError = $state(null);
  let annotations = $state({}); // mapblklot -> { verdict, reason }
  let gmapsKey = $state('');

  // filters
  let useFilter = $state('all');
  let verdictFilter = $state('all');
  let search = $state('');
  let maxMinutes = $state(75);
  let page = $state(0);

  const USE_LABELS = {
    surface_parking: 'Surface parking lot',
    vacant: 'Vacant lot',
    single_story_commercial: 'Single-story commercial'
  };

  function centroid(geom) {
    // average of all coordinates (good enough to drop a Maps pin)
    let sx = 0, sy = 0, n = 0;
    const walk = (a) => {
      if (typeof a[0] === 'number') { sx += a[0]; sy += a[1]; n++; }
      else a.forEach(walk);
    };
    walk(geom.coordinates);
    return n ? [sy / n, sx / n] : [37.7749, -122.4194]; // [lat, lon]
  }

  onMount(async () => {
    try {
      const fc = await loadJSON('candidates.geojson');
      features = fc.features.map((f) => {
        const [lat, lon] = centroid(f.geometry);
        return { ...f.properties, lat, lon };
      });
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) annotations = JSON.parse(saved);
      gmapsKey = localStorage.getItem(KEY_STORAGE) || '';
    } catch (e) {
      loadError = String(e);
    }
  });

  function persist() {
    annotations = { ...annotations };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(annotations));
  }
  function setVerdict(id, verdict) {
    const cur = annotations[id]?.verdict;
    annotations[id] = { ...(annotations[id] || {}), verdict: cur === verdict ? null : verdict };
    persist();
  }
  function setReason(id, reason) {
    annotations[id] = { ...(annotations[id] || {}), reason };
    persist();
  }
  function saveKey() {
    localStorage.setItem(KEY_STORAGE, gmapsKey.trim());
    gmapsKey = gmapsKey.trim();
  }

  let filtered = $derived(
    features.filter((f) => {
      if (useFilter !== 'all' && f.use_type !== useFilter) return false;
      if (f.transit_min > maxMinutes) return false;
      const v = annotations[f.mapblklot]?.verdict || null;
      if (verdictFilter === 'unreviewed' && v) return false;
      if (verdictFilter !== 'all' && verdictFilter !== 'unreviewed' && v !== verdictFilter) return false;
      if (search) {
        const s = search.toLowerCase();
        if (!(`${f.address || ''} ${f.mapblklot}`.toLowerCase().includes(s))) return false;
      }
      return true;
    })
  );
  let pageCount = $derived(Math.max(1, Math.ceil(filtered.length / PER_PAGE)));
  let pageItems = $derived(filtered.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE));

  $effect(() => {
    // keep page in range when filters change
    filtered.length;
    if (page > pageCount - 1) page = 0;
  });

  let counts = $derived.by(() => {
    let feasible = 0, infeasible = 0, unsure = 0;
    for (const a of Object.values(annotations)) {
      if (a.verdict === 'feasible') feasible++;
      else if (a.verdict === 'infeasible') infeasible++;
      else if (a.verdict === 'unsure') unsure++;
    }
    return { feasible, infeasible, unsure, total: feasible + infeasible + unsure };
  });

  function cleanAddr(a) {
    return a ? String(a).replace(/\s+/g, ' ').replace(/0000/g, '').trim() : '';
  }
  function photoUrl(f) {
    if (gmapsKey) {
      return `https://maps.googleapis.com/maps/api/streetview?size=440x240` +
        `&location=${f.lat},${f.lon}&fov=85&pitch=8&key=${gmapsKey}`;
    }
    return null;
  }
  function embedUrl(f) {
    return `https://maps.google.com/maps?q=${f.lat},${f.lon}&z=19&t=k&output=embed`;
  }
  function streetViewLink(f) {
    return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${f.lat},${f.lon}`;
  }
  function mapsLink(f) {
    return `https://www.google.com/maps/search/?api=1&query=${f.lat},${f.lon}`;
  }

  function exportCSV() {
    const rows = [[
      'mapblklot', 'address', 'use_type', 'asr_class', 'asr_use', 'asr_stories',
      'asr_year', 'far', 'net_new_units', 'transit_min', 'lat', 'lon',
      'verdict', 'reason'
    ]];
    for (const f of features) {
      const a = annotations[f.mapblklot] || {};
      if (!a.verdict && !a.reason) continue;
      rows.push([
        f.mapblklot, cleanAddr(f.address), f.use_type, f.asr_class, f.asr_use,
        f.asr_stories, f.asr_year, f.far, f.net_new_units, f.transit_min,
        f.lat.toFixed(6), f.lon.toFixed(6), a.verdict || '', a.reason || ''
      ].map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','));
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `sf_upzone_annotations_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
</script>

<svelte:head><title>Site review · Make Room for San Francisco</title></svelte:head>

<div class="wrap sans">
  <header>
    <a class="back" href="{base}/">← Back to the analysis</a>
    <h1>Candidate site review</h1>
    <p class="lede">
      Every candidate parcel with a satellite photo and a Street View link. Mark each one
      <strong>feasible</strong>, <strong>infeasible</strong> or <strong>unsure</strong>, add a
      reason, and export your calls as CSV. Infeasible sites and their reasons feed back into the
      selection rules. Your annotations are saved in this browser automatically.
    </p>
  </header>

  {#if loadError}
    <p class="err">Could not load candidates: {loadError}</p>
  {/if}

  <div class="toolbar">
    <div class="filters">
      <label>Use
        <select bind:value={useFilter}>
          <option value="all">all</option>
          <option value="vacant">vacant lot</option>
          <option value="surface_parking">surface parking</option>
          <option value="single_story_commercial">single-story commercial</option>
        </select>
      </label>
      <label>Status
        <select bind:value={verdictFilter}>
          <option value="all">all</option>
          <option value="unreviewed">unreviewed</option>
          <option value="feasible">feasible</option>
          <option value="infeasible">infeasible</option>
          <option value="unsure">unsure</option>
        </select>
      </label>
      <label>≤ min to downtown
        <input type="range" min="15" max="75" step="1" bind:value={maxMinutes} />
        <span class="mono">{maxMinutes}</span>
      </label>
      <input class="search" type="search" placeholder="search address / block-lot" bind:value={search} />
    </div>
    <div class="actions">
      <span class="tally">{counts.total} reviewed
        <span class="g">· {counts.feasible} ✓</span>
        <span class="r">· {counts.infeasible} ✕</span>
        <span class="y">· {counts.unsure} ?</span>
      </span>
      <button class="export" onclick={exportCSV} disabled={counts.total === 0}>Export CSV</button>
    </div>
  </div>

  <details class="keybox">
    <summary>Show real Street View photos (optional Google Maps API key)</summary>
    <p>
      Without a key, each card shows a keyless Google <strong>satellite</strong> photo and a
      <strong>Street View link</strong>. Paste a Google Maps Static Street View API key to embed
      ground-level photos directly. The key is stored only in this browser.
    </p>
    <div class="keyrow">
      <input type="password" placeholder="Google Maps API key" bind:value={gmapsKey} />
      <button onclick={saveKey}>Save key</button>
    </div>
  </details>

  <p class="resultline">
    {filtered.length.toLocaleString()} sites match · page {page + 1} of {pageCount}
  </p>

  <div class="grid">
    {#each pageItems as f (f.mapblklot)}
      {@const a = annotations[f.mapblklot] || {}}
      <div class="card" class:feasible={a.verdict === 'feasible'}
           class:infeasible={a.verdict === 'infeasible'} class:unsure={a.verdict === 'unsure'}>
        <div class="photo">
          {#if photoUrl(f)}
            <img src={photoUrl(f)} alt="Street view of {cleanAddr(f.address)}" loading="lazy" />
          {:else}
            <iframe title="Map of {cleanAddr(f.address) || f.mapblklot}" src={embedUrl(f)}
                    loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
          {/if}
        </div>
        <div class="body">
          <div class="addr">{cleanAddr(f.address) || '(no address on file)'}</div>
          <div class="meta">
            <span class="pill use-{f.use_type}">{USE_LABELS[f.use_type] || f.use_type}</span>
            <span class="mono">{f.mapblklot}</span>
          </div>
          <div class="facts">
            class {f.asr_class || 'n/a'} ·
            {f.asr_stories != null ? Math.round(f.asr_stories) : 0} st ·
            {f.asr_year ? `built ${Math.round(f.asr_year)}` : 'no bldg'} ·
            FAR {f.far ?? 0}<br />
            ~{f.net_new_units} homes · {Math.round(f.transit_min)} min to downtown
          </div>
          <div class="links">
            <a href={streetViewLink(f)} target="_blank" rel="noreferrer">Street View ↗</a>
            <a href={mapsLink(f)} target="_blank" rel="noreferrer">Google Maps ↗</a>
          </div>
          <div class="verdicts">
            <button class="v feas" class:on={a.verdict === 'feasible'}
                    onclick={() => setVerdict(f.mapblklot, 'feasible')}>Feasible</button>
            <button class="v infeas" class:on={a.verdict === 'infeasible'}
                    onclick={() => setVerdict(f.mapblklot, 'infeasible')}>Infeasible</button>
            <button class="v uns" class:on={a.verdict === 'unsure'}
                    onclick={() => setVerdict(f.mapblklot, 'unsure')}>Unsure</button>
          </div>
          <input class="reason" type="text" placeholder="reason / note (optional)"
                 value={a.reason || ''} oninput={(e) => setReason(f.mapblklot, e.target.value)} />
        </div>
      </div>
    {/each}
  </div>

  {#if filtered.length === 0 && !loadError}
    <p class="empty">No sites match these filters.</p>
  {/if}

  <div class="pager">
    <button onclick={() => (page = Math.max(0, page - 1))} disabled={page === 0}>← Prev</button>
    <span>page {page + 1} / {pageCount}</span>
    <button onclick={() => (page = Math.min(pageCount - 1, page + 1))} disabled={page >= pageCount - 1}>Next →</button>
  </div>
</div>

<style>
  .wrap { max-width: 1180px; margin: 0 auto; padding: 1.6rem 1.1rem 4rem; color: #1a1a1a; }
  .back { color: var(--accent); text-decoration: none; font-size: 0.9rem; }
  h1 { font-family: Georgia, serif; font-size: 2rem; margin: 0.6rem 0 0.3rem; }
  .lede { color: #444; max-width: 760px; line-height: 1.55; font-size: 0.98rem; }
  .err { color: #b00; }
  .toolbar {
    position: sticky; top: 0; z-index: 5; background: #fff; display: flex; flex-wrap: wrap;
    gap: 0.8rem 1.4rem; justify-content: space-between; align-items: center;
    padding: 0.7rem 0; border-bottom: 1px solid #e6e6e6; margin: 1rem 0 0.4rem;
  }
  .filters { display: flex; flex-wrap: wrap; gap: 0.7rem 1rem; align-items: center; font-size: 0.85rem; }
  .filters label { display: flex; align-items: center; gap: 0.35rem; color: #444; }
  .filters select, .search, .keyrow input, .reason { font: inherit; padding: 0.3rem 0.45rem; border: 1px solid #ccc; border-radius: 6px; }
  .search { min-width: 200px; }
  .actions { display: flex; align-items: center; gap: 0.9rem; }
  .tally { font-size: 0.85rem; color: #555; }
  .tally .g { color: #1b7837; } .tally .r { color: #b2182b; } .tally .y { color: #b8860b; }
  .export { background: var(--accent); color: #fff; border: none; padding: 0.45rem 0.9rem; border-radius: 7px; font-weight: 600; cursor: pointer; }
  .export:disabled { opacity: 0.4; cursor: default; }
  .keybox { margin: 0.4rem 0; font-size: 0.85rem; color: #555; }
  .keybox summary { cursor: pointer; color: var(--accent); }
  .keyrow { display: flex; gap: 0.5rem; margin-top: 0.4rem; }
  .keyrow input { flex: 1 1 320px; max-width: 420px; }
  .keyrow button, .pager button { font: inherit; padding: 0.35rem 0.8rem; border: 1px solid #ccc; background: #f6f6f6; border-radius: 6px; cursor: pointer; }
  .resultline { font-size: 0.82rem; color: #888; margin: 0.4rem 0; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
  .card { border: 1px solid #e3e3e3; border-radius: 10px; overflow: hidden; background: #fff; display: flex; flex-direction: column; transition: box-shadow 0.15s, border-color 0.15s; }
  .card.feasible { border-color: #1b7837; box-shadow: 0 0 0 2px rgba(27,120,55,0.15); }
  .card.infeasible { border-color: #b2182b; box-shadow: 0 0 0 2px rgba(178,24,43,0.15); }
  .card.unsure { border-color: #d4a017; box-shadow: 0 0 0 2px rgba(212,160,23,0.18); }
  .photo, .photo img, .photo iframe { width: 100%; height: 190px; display: block; border: 0; object-fit: cover; background: #eee; }
  .body { padding: 0.7rem 0.8rem 0.85rem; display: flex; flex-direction: column; gap: 0.4rem; }
  .addr { font-weight: 700; font-size: 0.92rem; }
  .meta { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .mono { font-family: ui-monospace, Menlo, monospace; font-size: 0.74rem; color: #888; }
  .pill { font-size: 0.7rem; padding: 0.12rem 0.45rem; border-radius: 999px; color: #fff; }
  .use-vacant { background: #1b7837; } .use-surface_parking { background: #7b3294; } .use-single_story_commercial { background: #2166ac; }
  .facts { font-size: 0.78rem; color: #555; line-height: 1.5; }
  .links { display: flex; gap: 0.8rem; font-size: 0.78rem; }
  .verdicts { display: flex; gap: 0.35rem; margin-top: 0.15rem; }
  .v { flex: 1; font: inherit; font-size: 0.78rem; padding: 0.32rem 0; border: 1px solid #ccc; background: #fafafa; border-radius: 6px; cursor: pointer; }
  .v.feas.on { background: #1b7837; color: #fff; border-color: #1b7837; }
  .v.infeas.on { background: #b2182b; color: #fff; border-color: #b2182b; }
  .v.uns.on { background: #d4a017; color: #fff; border-color: #d4a017; }
  .reason { width: 100%; box-sizing: border-box; font-size: 0.8rem; }
  .empty { color: #888; padding: 2rem 0; text-align: center; }
  .pager { display: flex; justify-content: center; align-items: center; gap: 1rem; margin: 1.6rem 0 0; font-size: 0.85rem; color: #555; }
</style>
