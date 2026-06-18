<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import MapExplorer from '$lib/MapExplorer.svelte';
  import { loadModel } from '$lib/data.js';
  import { computeImpact, fmtInt, fmtMoney, fmtPct } from '$lib/economics.js';

  let model = $state(null);
  let cutoff = $state(45);
  let stats = $state(null);
  let loadError = $state(null);

  let impact = $derived(model && stats ? computeImpact(stats.units, model) : null);

  onMount(async () => {
    try {
      model = await loadModel();
      cutoff = model.default_cutoff_min;
    } catch (e) {
      loadError = String(e);
    }
  });
</script>

<svelte:head>
  <title>Make Room for San Francisco</title>
</svelte:head>

<article>
  <header class="hero">
    <p class="kicker sans">An Opinion analysis · Housing</p>
    <h1>Make Room for San Francisco</h1>
    <p class="dek">
      San Francisco keeps saying it has no room left to grow. It does. By counting only
      parking lots, vacant land and single-story buildings near transit — and demolishing
      nothing — the city can make space for roughly
      <strong>{model ? fmtInt(model.summary.total_net_new_units) : '16,000'} new homes.</strong>
      Here is where they go, and what they would do to the rent.
    </p>
    <p class="byline sans">
      A San Francisco replication of the New York Times / PAU study
      <em>“How to Make Room for One Million New Yorkers.”</em>
    </p>
  </header>

  <section class="prose">
    <p>
      In December 2023, the architect Vishaan Chakrabarti and his firm
      <a href="https://pau.studio/what/affordable-new-york/" target="_blank" rel="noreferrer">PAU</a>
      asked a deceptively simple question for The New York Times: how much housing could
      New York add without knocking anything down? Their answer — more than half a million
      homes, found almost entirely on vacant lots, parking lots and single-story shops near
      transit — reframed a crisis that everyone treats as a matter of <em>space</em> into
      what it really is: a matter of <em>rules</em>.
    </p>
    <p>
      San Francisco is the country's most extreme version of that crisis. So we ran the same
      conservative playbook here, with one upgrade. Instead of drawing a half-mile circle
      around train stations, we measured the <strong>actual public-transit travel time</strong>
      from every parcel to downtown using Muni and BART schedules. You can move that dial
      below.
    </p>
  </section>

  <section class="full">
    <h2 class="sans section-h">Where the homes could go</h2>
    <p class="prose note">
      Each colored shape is a candidate site — a parking lot, vacant parcel or single-story
      building with no housing on it today. The background heatmap is transit time to
      downtown. Drag the slider to change how close to downtown a site must be.
    </p>

    {#if loadError}
      <p class="prose err">Could not load model data: {loadError}</p>
    {/if}

    {#if model}
      <MapExplorer {model} bind:cutoff onStats={(s) => (stats = s)} />

      <div class="statbar sans">
        <div class="stat">
          <div class="num">{stats ? fmtInt(stats.count) : '—'}</div>
          <div class="lbl">candidate sites within {cutoff} min</div>
        </div>
        <div class="stat">
          <div class="num">{stats ? fmtInt(stats.units) : '—'}</div>
          <div class="lbl">net-new homes (no demolition)</div>
        </div>
        <div class="stat">
          <div class="num">{stats ? fmtInt(stats.acres) : '—'}</div>
          <div class="lbl">acres of underused land</div>
        </div>
        <div class="stat">
          <div class="num">{stats ? fmtPct(impact.stockPct, 0) : '—'}</div>
          <div class="lbl">increase in SF housing stock</div>
        </div>
      </div>
    {:else if !loadError}
      <p class="prose">Loading map…</p>
    {/if}
  </section>

  <section class="prose">
    <h2 class="sans section-h">What it would do to the rent</h2>
    <p>
      More homes mean lower rents — the only real debate is by how much. We do not invent a
      number. We use the <strong>metro “stock elasticity of rent”</strong>: the percentage
      change in rents for each one-percent change in the housing stock, drawn from the
      causal research literature. Our central value is <strong>−0.5</strong>, meaning a
      10% larger housing stock is associated with rents about 5% lower (Pew, 2025); we show
      a conservative-to-optimistic band of −0.25 to −1.0 around it.
    </p>

    {#if model && impact}
      <div class="headline-impact">
        <p class="big">
          Building these <strong>{fmtInt(impact.units)}</strong> homes is projected to lower
          the typical SF rent by
          <span class="range">{fmtPct(impact.conservative.rentChangePct, 0)}–{fmtPct(
            impact.optimistic.rentChangePct,
            0
          )}</span>
          <span class="mid">(central ≈ {fmtPct(impact.central.rentChangePct, 0)})</span>
        </p>
        <p class="big sub">
          ≈ <strong>{fmtMoney(impact.central.monthlySavings)}/month</strong> off the typical
          {fmtMoney(model.sf_average_rent)} rent — about
          <strong>{fmtMoney(impact.central.citywideAnnual)}</strong> a year kept in renters'
          pockets across the city.
        </p>
      </div>

      <div class="cards sans">
        {#each [['Conservative', impact.conservative, '−0.25'], ['Central', impact.central, '−0.50'], ['Optimistic', impact.optimistic, '−1.00']] as [name, s, e]}
          <div class="card" class:center={name === 'Central'}>
            <div class="card-name">{name}</div>
            <div class="card-el">elasticity {e}</div>
            <div class="card-pct">{fmtPct(s.rentChangePct, 1)}</div>
            <div class="card-meta">lower rents</div>
            <div class="card-row">{fmtMoney(s.monthlySavings)}/mo saved</div>
            <div class="card-row">new avg rent {fmtMoney(s.newRent)}</div>
          </div>
        {/each}
      </div>

      <p class="caveat">
        <strong>Read this honestly.</strong> A {fmtPct(impact.stockPct, 0)} jump in the housing
        stock is larger than the year-to-year changes these elasticities were measured on,
        so the full-buildout percentages above are a linear extrapolation — an order of
        magnitude, not a forecast. The defensible, conservative way to state it: phased over
        {model.buildout_phase_years} years, that's about <strong>{fmtInt(impact.perYear)} homes a
        year</strong>, each 10,000 of which lowers rents by roughly
        {fmtPct((10000 / model.sf_housing_units) * 100 * Math.abs(model.rent_elasticity.central), 2)}
        at the central elasticity. Real-world cross-check: Austin added ~13% to its apartment
        stock in two years and saw asking rents fall ~15%.
      </p>
    {/if}
  </section>

  <section class="prose">
    <h2 class="sans section-h">How we did it</h2>
    <p>
      The whole pipeline is open and reproducible from raw public data. A parcel becomes a
      candidate only if it clears every one of these tests:
    </p>
    <ol class="crit">
      <li><strong>No home is demolished</strong> — zero existing residential units in both the
        land-use file <em>and</em> the current Assessor roll, and not a residential property class.</li>
      <li><strong>It isn't civic or institutional</strong> — libraries, schools, churches,
        hospitals, fire/police, and all government or public land are excluded by property class
        (this is what kept a branch library out of an earlier draft).</li>
      <li><strong>It isn't an office or industrial building</strong>, a hotel, or a parking garage.</li>
      <li><strong>It's genuinely low and underbuilt</strong> — at most one story in the Assessor
        roll <em>and</em> a roof at/below ~9 m in LiDAR <em>and</em> a floor-area ratio under 1.2.
        The ratio test rejects any dense or mis-mapped tower (this is what kept Salesforce Tower out).</li>
      <li><strong>It's not brand-new</strong> — anything the Assessor records as built since 2015
        is excluded, so recent buildings the older layers miss (e.g. a 2020 apartment block) don't
        slip through as “vacant.”</li>
      <li><strong>It carries a real soft-site signal</strong> — a surface parking lot, a vacant
        developable lot, or single-story retail/commercial.</li>
      <li><strong>It survives the sea</strong> — outside the 2100 sea-level-rise + 100-year-storm
        inundation zone.</li>
      <li><strong>It's transit-served</strong> — public-transit travel time to downtown is at or
        below your chosen cutoff.</li>
    </ol>
    <p>
      Each surviving site is then matched to its neighborhood's building heights and given a
      conservative low-, mid- or high-rise unit count, so nothing towers over its block. We hand-review
      sites for feasibility in a companion <a href="{base}/review">annotation tool</a>, and feed what
      we learn back into these rules.
    </p>

    {#if model}
      <div class="sources sans">
        <h3>Data</h3>
        <ul>
          <li>Parcels, land use, zoning, building footprints (LiDAR heights), the 2100
            sea-level-rise zone, and the current <strong>Assessor secured roll</strong>
            (stories, units, year built, property class) — <a href="https://data.sfgov.org" target="_blank" rel="noreferrer">DataSF</a> open data.</li>
          <li>Transit schedules — SFMTA (Muni) and BART GTFS feeds; routing on the OpenStreetMap
            street network via R5/r5py.</li>
        </ul>
        <h3>Rent-impact evidence</h3>
        <ul>
          {#each model.elasticity_sources as src}<li>{src}</li>{/each}
        </ul>
        <h3>Assumptions worth knowing</h3>
        <ul>
          {#each model.caveats as c}<li>{c}</li>{/each}
        </ul>
        <p class="method">{model.method_note}</p>
      </div>
    {/if}
  </section>

  <footer class="sans">
    <p>
      Built as a reproducible, open replication of the NYT/PAU “Make Room” analysis for
      San Francisco. Every figure regenerates from <code>uv run main.py</code>. Code and
      methodology are in the repository.
    </p>
  </footer>
</article>

<style>
  article { padding: 0 1.1rem 5rem; }
  .hero { max-width: var(--max); margin: 3.4rem auto 1.6rem; }
  .kicker { color: var(--accent); font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; font-size: 0.78rem; margin: 0 0 0.6rem; }
  h1 { font-size: clamp(2.3rem, 6vw, 3.6rem); margin: 0 0 1rem; font-weight: 700; }
  .dek { font-size: 1.28rem; line-height: 1.5; color: #2a2a2a; margin: 0 0 1.2rem; }
  .byline { font-size: 0.9rem; color: var(--muted); border-top: 1px solid var(--rule); padding-top: 0.9rem; }
  .prose { max-width: var(--max); margin: 0 auto; }
  .prose p, .crit li, .prose li { font-size: 1.12rem; line-height: 1.72; color: #232323; }
  .section-h { font-size: 1.7rem; margin: 2.6rem 0 0.4rem; }
  .note { color: var(--muted); font-size: 1.02rem; }
  .full { max-width: 1040px; margin: 1.4rem auto 0; }
  .full .section-h, .full .note { max-width: var(--max); margin-left: auto; margin-right: auto; }
  .statbar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--rule); border: 1px solid var(--rule); border-radius: 10px; overflow: hidden; margin: 1rem 0 0; }
  .stat { background: #fff; padding: 1.1rem 1rem; text-align: center; }
  .stat .num { font-size: 1.9rem; font-weight: 800; color: var(--ink); font-family: -apple-system, Helvetica, Arial, sans-serif; }
  .stat .lbl { font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }
  .headline-impact { border-left: 4px solid var(--accent); padding: 0.4rem 0 0.4rem 1.2rem; margin: 1.6rem 0; }
  .big { font-size: 1.45rem; line-height: 1.45; margin: 0.3rem 0; }
  .big .range { color: var(--accent); font-weight: 800; white-space: nowrap; }
  .big .mid { color: var(--muted); font-size: 1.05rem; }
  .big.sub { font-size: 1.15rem; color: #333; }
  .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem; margin: 1.6rem 0; }
  .card { border: 1px solid var(--rule); border-radius: 10px; padding: 1.1rem; text-align: center; background: #fcfcfc; }
  .card.center { border-color: var(--accent); box-shadow: 0 2px 12px rgba(215,48,39,0.12); }
  .card-name { font-weight: 700; font-size: 0.95rem; }
  .card-el { font-size: 0.74rem; color: var(--muted); margin-bottom: 0.5rem; }
  .card-pct { font-size: 2.1rem; font-weight: 800; color: var(--accent); }
  .card-meta { font-size: 0.78rem; color: var(--muted); margin-bottom: 0.6rem; }
  .card-row { font-size: 0.88rem; color: #333; margin: 0.15rem 0; }
  .caveat { background: #fbf7e9; border: 1px solid #efe3b8; border-radius: 10px; padding: 1rem 1.2rem; font-size: 1.02rem !important; line-height: 1.65 !important; color: #4a4327 !important; }
  .crit { padding-left: 1.2rem; }
  .crit li { margin: 0.5rem 0; }
  .sources { max-width: var(--max); margin: 1.4rem auto 0; background: #f7f7f7; border-radius: 10px; padding: 1.2rem 1.4rem; }
  .sources h3 { font-size: 1rem; margin: 1rem 0 0.3rem; }
  .sources h3:first-child { margin-top: 0; }
  .sources ul { margin: 0; padding-left: 1.1rem; }
  .sources li { font-size: 0.92rem; line-height: 1.55; color: #333; margin: 0.3rem 0; }
  .sources .method { font-size: 0.85rem; color: var(--muted); margin-top: 0.8rem; font-style: italic; }
  footer { max-width: var(--max); margin: 3rem auto 0; border-top: 1px solid var(--rule); padding-top: 1.2rem; color: var(--muted); font-size: 0.86rem; }
  .err { color: #b00; }
  @media (max-width: 640px) {
    .statbar { grid-template-columns: repeat(2, 1fr); }
    .cards { grid-template-columns: 1fr; }
  }
</style>
