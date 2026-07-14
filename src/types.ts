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
}

export type Platform = 'desktop' | 'mobile';

export type CurrentScreen = 'onboarding' | 'discovery' | 'chat' | 'detail';
