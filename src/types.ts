export interface Product {
  id: string;
  name: string;
  brand: string;
  price: number;
  image: string;
  secondaryImage?: string;
  description: string;
  category: string;
  tags: string[];
  colors: string[];
  sizes: string[];
  occasion: string;
  deliveryEstimate?: string;
  productUrl?: string;
}

/** Raw shape returned by the backend's /products* endpoints (schemas/product.py). */
export interface ApiProduct {
  id: string;
  name: string;
  description: string | null;
  price: number;
  colors: string[];
  sizes: string[];
  occasion: string | null;
  category: string | null;
  tags: string[];
  image: string;
  secondaryImage: string | null;
  product_url: string;
}

export interface ApiProductSearchResponse {
  items: ApiProduct[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SessionState {
  occasion: string | null;
  color_preference: string | null;
  budget_max: number | null;
  style_descriptors: string[];
  size: string | null;
  deadline_date: string | null;
  excluded: string[];
  brands: string[];
  department: string | null;
}

export interface ChatTurnResponse {
  session_id: string;
  reply: string;
  session_state: SessionState;
  filters: { style: string; occasion: string; budget: string; color?: string; size?: string };
  products: ApiProductSearchResponse;
  turn_type: 'fast_path' | 'llm_extraction';
}

export interface ApiBrand {
  id: string;
  name: string;
  slug: string;
  domain: string;
  logo_url: string | null;
  is_active: boolean;
  department: string;
}

export interface ApiCollection {
  id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  image_url: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface Collection {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  image: string;
}

export interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
}

export interface FilterChips {
  style: string;
  occasion: string;
  budget: string;
  color?: string;
  size?: string;
}

export type Platform = 'desktop' | 'mobile';

export type CurrentScreen = 'onboarding' | 'discovery' | 'chat' | 'detail';
