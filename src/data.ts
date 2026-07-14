import { Product, Collection } from './types';

export const INITIAL_PRODUCTS: Product[] = [
  {
    id: '1',
    name: 'Emerald Silk Tilla Peshwas',
    brand: 'Dhaaga Lahore',
    price: 34500,
    image: 'https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?q=80&w=800&auto=format&fit=crop',
    secondaryImage: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?q=80&w=800&auto=format&fit=crop',
    description: 'A traditional heavy-flared Peshwas crafted in premium pure silk, featuring stunning hand-embroidered Lahore tilla work on the bodice and sleeves. Finished with a block-printed rust organza dupatta and raw silk churidar.',
    category: 'Peshwas',
    tags: ['mehndi', 'emerald', 'silk', 'embroidery', 'tilla', 'under 50k'],
    colors: ['Emerald Green', 'Rust Orange', 'Maroon'],
    sizes: ['XS', 'S', 'M', 'L', 'XL'],
    occasion: 'Mehndi & Sangeet',
    deliveryEstimate: 'Ships from Lahore (3 days delivery)'
  },
  {
    id: '2',
    name: 'Shehnai Crimson Zardozi Lehenga',
    brand: 'Karachi Couture Circle',
    price: 185000,
    image: 'https://images.unsplash.com/photo-1610030469668-93535c17b6b3?q=80&w=800&auto=format&fit=crop',
    secondaryImage: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?q=80&w=800&auto=format&fit=crop',
    description: 'An elite bridal lehenga in rich crimson silk velvet, hand-embroidered with classic zardozi, dabka, and heavy kora embellishments. Accompanied by a pure chiffon trailing veil and a second custom-dyed net dupatta.',
    category: 'Lehenga',
    tags: ['wedding', 'bridal', 'velvet', 'luxury', 'barat'],
    colors: ['Crimson Red', 'Royal Maroon', 'Plum'],
    sizes: ['Custom', 'S', 'M', 'L'],
    occasion: 'Barat & Walima',
    deliveryEstimate: 'Made to order (6 weeks creation + Express Courier)'
  },
  {
    id: '3',
    name: 'Multan Gota-Patti Angrakha',
    brand: 'Sahar of Multan',
    price: 24000,
    image: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?q=80&w=800&auto=format&fit=crop',
    secondaryImage: 'https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?q=80&w=800&auto=format&fit=crop',
    description: 'A beautifully balanced mustard georgette Angrakha, adorned with hand-placed Multani gota-patti work, scalloped dori-ties, and a traditional crinkled block dupatta. Ideal for vibrant dholkis or intimate Mayuns.',
    category: 'Angrakha',
    tags: ['mayun', 'mustard', 'gota', 'under 50k'],
    colors: ['Mustard Yellow', 'Marigold Orange', 'Blush Pink'],
    sizes: ['S', 'M', 'L', 'XL'],
    occasion: 'Mayun & Haldi',
    deliveryEstimate: 'Ships from Multan (4 days delivery)'
  },
  {
    id: '4',
    name: 'Ivory Raw-Silk Sherwani',
    brand: 'Dhaaga Lahore',
    price: 68000,
    image: 'https://images.unsplash.com/photo-1607990283143-e81e7a2c93ab?q=80&w=800&auto=format&fit=crop',
    secondaryImage: 'https://images.unsplash.com/photo-1597983073493-88cd35cf93b0?q=80&w=800&auto=format&fit=crop',
    description: 'Command presence in a hand-loomed raw silk sherwani featuring understated self-thread geometric embroidery, custom copper buttons, and a matching cotton silk inner kurta and straight pajama.',
    category: 'Sherwani',
    tags: ['groom', 'ivory', 'silk', 'luxury', 'barat'],
    colors: ['Ivory White', 'Champagne Gold', 'Jet Black'],
    sizes: ['S', 'M', 'L', 'XL', 'XXL'],
    occasion: 'Barat & Walima',
    deliveryEstimate: 'Ships from Lahore (4 days delivery)'
  },
  {
    id: '5',
    name: 'Teal Block-Print Gharara Set',
    brand: 'Karachi Couture Circle',
    price: 29500,
    image: 'https://images.unsplash.com/photo-1597983073493-88cd35cf93b0?q=80&w=800&auto=format&fit=crop',
    secondaryImage: 'https://images.unsplash.com/photo-1605721911519-3dfeb3be25e7?q=80&w=800&auto=format&fit=crop',
    description: 'A classic 1970s silhouette reborn. Deep teal jamawar gharara trousers paired with a short raw silk tunic and a heavily-laden gold tilla block dupatta.',
    category: 'Gharara',
    tags: ['mehndi', 'teal', 'jamawar', 'under 50k'],
    colors: ['Teal Blue', 'Emerald', 'Peacock Blue'],
    sizes: ['S', 'M', 'L', 'XL'],
    occasion: 'Mehndi & Sangeet',
    deliveryEstimate: 'Ships from Karachi (3 days delivery)'
  },
  {
    id: '6',
    name: 'Peshawar Lapis-Lazuli Peshwas',
    brand: 'Heritage of Peshawar',
    price: 45000,
    image: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?q=80&w=800&auto=format&fit=crop',
    secondaryImage: 'https://images.unsplash.com/photo-1610030469668-93535c17b6b3?q=80&w=800&auto=format&fit=crop',
    description: 'Deep lapis blue silk-crêpe Peshwas detailed with traditional Peshawar thread embroidery and tiny mirror embellishments. Includes an elegant crushed silk palazzo.',
    category: 'Peshwas',
    tags: ['mehndi', 'blue', 'embroidery', 'under 50k'],
    colors: ['Lapis Blue', 'Royal Blue'],
    sizes: ['S', 'M', 'L'],
    occasion: 'Mehndi & Sangeet',
    deliveryEstimate: 'Ships from Peshawar (4 days delivery)'
  }
];

export const INITIAL_COLLECTIONS: Collection[] = [
  {
    id: 'col-1',
    title: 'The Walled City Autumn Drop',
    subtitle: 'Limited Lahore Heirlooms',
    description: 'A curated selection of deep lapis, warm terracotta, and emerald-toned handspun raw silks celebrating the legacy of slow, sustainable Pakistani couture.',
    image: 'https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?q=80&w=1200&auto=format&fit=crop'
  },
  {
    id: 'col-2',
    title: 'Modern Shehnai Baraat Curations',
    subtitle: 'Grand Pre-Wedding and Main Days',
    description: 'Fluid, dancing silhouettes in luxurious silk fabrics adorned with delicate gold zardozi motifs, made for motion, heritage, and grand entrances.',
    image: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?q=80&w=1200&auto=format&fit=crop'
  }
];
