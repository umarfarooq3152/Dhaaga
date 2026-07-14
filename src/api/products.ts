import { api } from './client';
import { getBrandNameMap } from './brands';
import { ApiProduct, ApiProductSearchResponse, Product } from '../types';

function brandSlugFromId(productId: string): string {
  return productId.split(':')[0] ?? productId;
}

export async function toProduct(apiProduct: ApiProduct): Promise<Product> {
  const brandNames = await getBrandNameMap();
  const slug = brandSlugFromId(apiProduct.id);
  return {
    id: apiProduct.id,
    name: apiProduct.name,
    brand: brandNames[slug] ?? slug,
    price: apiProduct.price,
    image: apiProduct.image,
    secondaryImage: apiProduct.secondaryImage ?? undefined,
    description: apiProduct.description ?? '',
    category: apiProduct.category ?? 'Apparel',
    tags: apiProduct.tags,
    colors: apiProduct.colors,
    sizes: apiProduct.sizes,
    occasion: apiProduct.occasion ?? 'Versatile',
    // Not yet populated by the backend (Feature 8, deferred) — left undefined
    // so the frontend's existing "Standard Delivery" fallback UI applies.
    deliveryEstimate: undefined,
    productUrl: apiProduct.product_url,
  };
}

export async function toProducts(apiProducts: ApiProduct[]): Promise<Product[]> {
  // Brand map is fetched once and cached, so this is cheap despite the map.
  return Promise.all(apiProducts.map(toProduct));
}

export interface ProductSearchParams {
  q?: string;
  occasion?: string;
  color?: string;
  size?: string;
  tags?: string[];
  minPrice?: number;
  maxPrice?: number;
  page?: number;
  pageSize?: number;
}

export interface ProductSearchResult {
  items: Product[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

function buildSearchQuery(params: ProductSearchParams): string {
  const search = new URLSearchParams();
  if (params.q) search.set('q', params.q);
  if (params.occasion) search.set('occasion', params.occasion);
  if (params.color) search.set('color', params.color);
  if (params.size) search.set('size', params.size);
  if (params.tags) params.tags.forEach((t) => search.append('tags', t));
  if (params.minPrice !== undefined) search.set('min_price', String(params.minPrice));
  if (params.maxPrice !== undefined) search.set('max_price', String(params.maxPrice));
  search.set('page', String(params.page ?? 1));
  search.set('page_size', String(params.pageSize ?? 20));
  return search.toString();
}

async function toSearchResult(response: ApiProductSearchResponse): Promise<ProductSearchResult> {
  return {
    items: await toProducts(response.items),
    total: response.total,
    page: response.page,
    pageSize: response.page_size,
    hasMore: response.has_more,
  };
}

export async function searchProducts(params: ProductSearchParams = {}): Promise<ProductSearchResult> {
  const response = await api.get<ApiProductSearchResponse>(`/products/search?${buildSearchQuery(params)}`);
  return toSearchResult(response);
}

export async function fetchProduct(productId: string): Promise<Product> {
  const response = await api.get<ApiProduct>(`/products/${encodeURIComponent(productId)}`);
  return toProduct(response);
}

export async function fetchAlternatives(productId: string, limit = 4): Promise<Product[]> {
  const response = await api.get<ApiProductSearchResponse>(
    `/products/${encodeURIComponent(productId)}/alternatives?limit=${limit}&page_size=${limit}`
  );
  return toProducts(response.items);
}
