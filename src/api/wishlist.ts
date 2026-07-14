import { api } from './client';
import { toProducts } from './products';
import { ApiProduct, Product } from '../types';

interface ApiWishlistItem {
  product: ApiProduct;
  added_at: string;
}

interface ApiWishlistResponse {
  items: ApiWishlistItem[];
}

export async function fetchWishlist(): Promise<Product[]> {
  const response = await api.get<ApiWishlistResponse>('/wishlist');
  return toProducts(response.items.map((item) => item.product));
}

export async function addToWishlist(productId: string): Promise<void> {
  await api.post(`/wishlist/${encodeURIComponent(productId)}`);
}

export async function removeFromWishlist(productId: string): Promise<void> {
  await api.delete(`/wishlist/${encodeURIComponent(productId)}`);
}
