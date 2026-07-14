import { api } from './client';
import { ApiBrand } from '../types';

let brandNameCache: Record<string, string> | null = null;
let inFlight: Promise<Record<string, string>> | null = null;

/** Slug -> display name lookup, fetched once and cached for the session.
 * Products only carry a brand slug (embedded in their composite id); the
 * display name shown on cards/details comes from this lookup. */
export async function getBrandNameMap(): Promise<Record<string, string>> {
  if (brandNameCache) return brandNameCache;
  if (inFlight) return inFlight;

  inFlight = api.get<ApiBrand[]>('/brands').then((brands) => {
    brandNameCache = Object.fromEntries(brands.map((b) => [b.slug, b.name]));
    return brandNameCache;
  });

  return inFlight;
}

export async function fetchBrands(): Promise<ApiBrand[]> {
  return api.get<ApiBrand[]>('/brands');
}
