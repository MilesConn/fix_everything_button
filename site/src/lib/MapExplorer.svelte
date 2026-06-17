<script>
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';

  let { model, cutoff = $bindable(45), onStats } = $props();

  let mapEl;
  let map;
  let maplibre;
  let candidates = $state(null); // raw GeoJSON
  let showGrid = $state(true);
  let colorBy = $state('use_type');
  let ready = $state(false);
  let error = $state(null);

  const USE_COLORS = {
    surface_parking: '#7b3294',
    vacant: '#1b7837',
    single_story_commercial: '#2166ac',
    low_intensity: '#d6604d'
  };
  const USE_LABELS = {
    surface_parking: 'Surface parking',
    vacant: 'Vacant lot',
    single_story_commercial: 'Single-story commercial',
    low_intensity: 'Low-intensity / underbuilt'
  };
  const TYPO_COLORS = { low: '#fdae61', mid: '#f46d43', high: '#a50026' };
  const TYPO_LABELS = { low: 'Low-rise (3–4 st.)', mid: 'Mid-rise (5–8 st.)', high: 'High-rise (9+ st.)' };

  const MINUTE_STOPS = [
    [0, '#1a9850'], [20, '#91cf60'], [30, '#d9ef8b'],
    [40, '#fee08b'], [50, '#fc8d59'], [70, '#d73027']
  ];

  function computeStats() {
    if (!candidates) return;
    let units = 0, count = 0, acres = 0;
    for (const f of candidates.features) {
      if (f.properties.transit_min <= cutoff) {
        units += f.properties.net_new_units || 0;
        acres += f.properties.lot_area_acres || 0;
        count += 1;
      }
    }
    onStats?.({ units, count, acres });
  }

  function applyCutoff() {
    if (!map || !map.getLayer('candidates-fill')) return;
    map.setFilter('candidates-fill', ['<=', ['get', 'transit_min'], cutoff]);
    map.setFilter('candidates-line', ['<=', ['get', 'transit_min'], cutoff]);
    if (map.getLayer('grid')) {
      map.setLayoutProperty('grid', 'visibility', showGrid ? 'visible' : 'none');
    }
    computeStats();
  }

  function colorExpr() {
    if (colorBy === 'typology') {
      return ['match', ['get', 'typology'],
        'low', TYPO_COLORS.low, 'mid', TYPO_COLORS.mid, 'high', TYPO_COLORS.high, '#888'];
    }
    return ['match', ['get', 'use_type'],
      'surface_parking', USE_COLORS.surface_parking,
      'vacant', USE_COLORS.vacant,
      'single_story_commercial', USE_COLORS.single_story_commercial,
      'low_intensity', USE_COLORS.low_intensity, '#888'];
  }

  $effect(() => {
    // re-run when these change
    cutoff; showGrid;
    if (ready) applyCutoff();
  });

  $effect(() => {
    if (ready && map && map.getLayer('candidates-fill')) {
      map.setPaintProperty('candidates-fill', 'fill-color', colorBy ? colorExpr() : colorExpr());
    }
  });

  onMount(async () => {
    try {
      maplibre = (await import('maplibre-gl')).default;
      await import('maplibre-gl/dist/maplibre-gl.css');

      const [grid, cand] = await Promise.all([
        fetch(`${base}/data/transit_grid.geojson`).then((r) => r.json()),
        fetch(`${base}/data/candidates.geojson`).then((r) => r.json())
      ]);
      candidates = cand;

      map = new maplibre.Map({
        container: mapEl,
        style: 'https://tiles.openfreemap.org/styles/positron',
        center: [-122.444, 37.765],
        zoom: 11.4,
        attributionControl: true
      });
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right');

      map.on('load', () => {
        // Transit isochrone grid
        map.addSource('grid', { type: 'geojson', data: grid });
        map.addLayer({
          id: 'grid',
          type: 'circle',
          source: 'grid',
          filter: ['has', 'minutes'],
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 3, 13, 7, 15, 14],
            'circle-color': ['interpolate', ['linear'], ['get', 'minutes'],
              ...MINUTE_STOPS.flat()],
            'circle-opacity': 0.55,
            'circle-blur': 0.5
          }
        });

        // Candidate parcels
        map.addSource('cand', { type: 'geojson', data: cand });
        map.addLayer({
          id: 'candidates-fill',
          type: 'fill',
          source: 'cand',
          paint: { 'fill-color': colorExpr(), 'fill-opacity': 0.85 }
        });
        map.addLayer({
          id: 'candidates-line',
          type: 'line',
          source: 'cand',
          paint: { 'line-color': '#222', 'line-width': 0.3, 'line-opacity': 0.4 }
        });

        // Downtown anchor
        new maplibre.Marker({ color: '#111' })
          .setLngLat([model.downtown.lon, model.downtown.lat])
          .setPopup(new maplibre.Popup({ offset: 18 }).setHTML(
            `<strong>Downtown anchor</strong><br/>${model.downtown.name}<br/>` +
            `travel times measured from here`))
          .addTo(map);

        const popup = new maplibre.Popup({ closeButton: false, closeOnClick: false });
        map.on('mousemove', 'candidates-fill', (e) => {
          map.getCanvas().style.cursor = 'pointer';
          const p = e.features[0].properties;
          popup.setLngLat(e.lngLat).setHTML(
            `<strong>${USE_LABELS[p.use_type] || p.use_type}</strong><br/>` +
            `~${p.net_new_units} homes · ${TYPO_LABELS[p.typology] || p.typology}<br/>` +
            `${(+p.lot_area_acres).toFixed(2)} acres · ${Math.round(p.transit_min)} min to downtown`
          ).addTo(map);
        });
        map.on('mouseleave', 'candidates-fill', () => {
          map.getCanvas().style.cursor = '';
          popup.remove();
        });

        ready = true;
        applyCutoff();
      });
    } catch (e) {
      error = String(e);
      console.error(e);
    }
  });

  onDestroy(() => map?.remove());
</script>

<div class="explorer">
  <div class="controls">
    <div class="knob">
      <label for="cut">Max transit time to downtown:
        <strong>{cutoff} min</strong></label>
      <input id="cut" type="range" min="15" max="75" step="5" bind:value={cutoff} />
      <div class="ticks"><span>15</span><span>45</span><span>75</span></div>
    </div>
    <div class="toggles">
      <label><input type="checkbox" bind:checked={showGrid} /> Travel-time heatmap</label>
      <label class="seg">Color sites by:
        <select bind:value={colorBy}>
          <option value="use_type">land use</option>
          <option value="typology">building typology</option>
        </select>
      </label>
    </div>
  </div>

  <div class="map" bind:this={mapEl}></div>

  <div class="legend">
    <div class="legend-block">
      <div class="legend-title">Transit time to downtown</div>
      <div class="ramp">
        <span style="background:#1a9850"></span>
        <span style="background:#91cf60"></span>
        <span style="background:#d9ef8b"></span>
        <span style="background:#fee08b"></span>
        <span style="background:#fc8d59"></span>
        <span style="background:#d73027"></span>
      </div>
      <div class="ramp-labels"><span>0</span><span>30</span><span>50</span><span>70+ min</span></div>
    </div>
    <div class="legend-block">
      <div class="legend-title">Candidate sites</div>
      {#if colorBy === 'use_type'}
        {#each Object.entries(USE_LABELS) as [k, v]}
          <div class="key"><span class="sw" style="background:{USE_COLORS[k]}"></span>{v}</div>
        {/each}
      {:else}
        {#each Object.entries(TYPO_LABELS) as [k, v]}
          <div class="key"><span class="sw" style="background:{TYPO_COLORS[k]}"></span>{v}</div>
        {/each}
      {/if}
    </div>
  </div>

  {#if error}<p class="err">Map failed to load: {error}</p>{/if}
</div>

<style>
  .explorer { border: 1px solid #e3e3e3; border-radius: 10px; overflow: hidden; background: #fff; }
  .controls {
    display: flex; flex-wrap: wrap; gap: 1.5rem 2rem; align-items: center;
    padding: 0.9rem 1.1rem; border-bottom: 1px solid #eee; background: #fafafa;
  }
  .knob { flex: 1 1 280px; }
  .knob label { font-size: 0.92rem; color: #333; }
  .knob input[type='range'] { width: 100%; margin-top: 0.4rem; accent-color: #d73027; }
  .ticks, .ramp-labels { display: flex; justify-content: space-between; font-size: 0.72rem; color: #999; }
  .toggles { display: flex; flex-direction: column; gap: 0.4rem; font-size: 0.9rem; }
  .toggles .seg select { margin-left: 0.3rem; }
  .map { height: 560px; width: 100%; }
  .legend {
    display: flex; gap: 2rem; flex-wrap: wrap; padding: 0.8rem 1.1rem;
    border-top: 1px solid #eee; background: #fff; font-size: 0.82rem;
  }
  .legend-title { font-weight: 600; margin-bottom: 0.35rem; }
  .ramp { display: flex; width: 220px; height: 12px; border-radius: 3px; overflow: hidden; }
  .ramp span { flex: 1; }
  .ramp-labels { width: 220px; margin-top: 2px; }
  .key { display: flex; align-items: center; gap: 0.4rem; margin: 0.15rem 0; }
  .sw { width: 13px; height: 13px; border-radius: 3px; display: inline-block; }
  .err { color: #b00; padding: 0.6rem 1.1rem; }
  @media (max-width: 640px) { .map { height: 440px; } }
</style>
