import { api } from './client';
import { toProducts } from './products';
import { ApiCollection, ApiProduct, Product } from '../types';

export async function fetchCollections(): Promise<ApiCollection[]> {
  return api.get<ApiCollection[]>('/collections');
}

interface ApiCollectionProductsResponse {
  id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  image_url: string | null;
  items: ApiProduct[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export async function fetchCollectionProducts(collectionId: string, pageSize = 20): Promise<Product[]> {
  const response = await api.get<ApiCollectionProductsResponse>(
    `/collections/${collectionId}?page=1&page_size=${pageSize}`
  );
  return toProducts(response.items);
}
