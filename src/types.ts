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
  isKids: boolean;
  ageRangesMonths: Array<[number, number]>;
  liveVerified: boolean;
  liveVerifiedAt?: string;
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
  department?: 'men' | 'women' | 'unisex' | null;
  is_kids?: boolean;
  age_ranges_months?: Array<[number, number]>;
  tags: string[];
  image: string;
  secondaryImage: string | null;
  product_url: string;
  live_verified?: boolean;
  live_verified_at?: string | null;
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
  category: string | null;
  color_preference: string | null;
  budget_max: number | null;
  style_descriptors: string[];
  size: string | null;
  deadline_date: string | null;
  excluded: string[];
  brands: string[];
  department: string | null;
  wants_kids: boolean;
  child_age_months: number | null;
  semantic_query: string | null;
  excluded_styles: string[];
  fallback_categories: string[];
  fallback_styles: string[];
  hard_constraints: string[];
  soft_preferences: string[];
}

export interface ChatTurnResponse {
  session_id: string;
  reply: string;
  session_state: SessionState;
  filters: { category?: string; style: string; styles?: string[]; occasion: string; budget: string; color?: string; size?: string; age?: string };
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
  category?: string;
  style: string;
  styles?: string[];
  occasion: string;
  budget: string;
  color?: string;
  size?: string;
  age?: string;
}

export type Platform = 'desktop' | 'mobile';

export type CurrentScreen = 'onboarding' | 'discovery' | 'chat' | 'detail';
