import { base } from '$app/paths';

export async function loadJSON(path) {
  const res = await fetch(`${base}/data/${path}`);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

export async function loadModel() {
  return loadJSON('model.json');
}
