// Client-side mirror of scripts/economic_model.py so the headline numbers update
// live as the user changes the transit cutoff. Same formula, same elasticities.

export function computeImpact(units, model) {
  const stockPct = (units / model.sf_housing_units) * 100;
  const rent = model.sf_average_rent;
  const renters = model.sf_renter_households;

  const scenario = (e) => {
    const rentPct = stockPct * e; // negative
    const newRent = rent * (1 + rentPct / 100);
    const monthly = rent - newRent;
    return {
      elasticity: e,
      rentChangePct: rentPct,
      newRent,
      monthlySavings: monthly,
      annualSavings: monthly * 12,
      citywideAnnual: monthly * 12 * renters
    };
  };

  const el = model.rent_elasticity;
  return {
    units,
    stockPct,
    conservative: scenario(el.conservative),
    central: scenario(el.central),
    optimistic: scenario(el.optimistic),
    perYear: Math.round(units / model.buildout_phase_years)
  };
}

export function fmtInt(n) {
  return Math.round(n).toLocaleString('en-US');
}

export function fmtMoney(n) {
  const v = Math.abs(Math.round(n));
  return `$${v.toLocaleString('en-US')}`;
}

export function fmtPct(n, digits = 1) {
  return `${Math.abs(n).toFixed(digits)}%`;
}
