import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowLeft, Heart, ShoppingBag, Truck, CheckCircle, ExternalLink, RefreshCw } from 'lucide-react';
import { Product } from '../types';
import { fetchAlternatives } from '../api/products';

interface ProductDetailScreenProps {
  product: Product;
  onBack: () => void;
  onSelectProduct: (product: Product) => void;
  wishlist: string[];
  onToggleWishlist: (productId: string) => void;
  onOpenWishlist: () => void;
}

export default function ProductDetailScreen({
  product,
  onBack,
  onSelectProduct,
  wishlist,
  onToggleWishlist,
  onOpenWishlist
}: ProductDetailScreenProps) {
  const [selectedColor, setSelectedColor] = useState(product.colors[0]);
  const [selectedSize, setSelectedSize] = useState(product.sizes[0] || 'M');
  const isLiked = wishlist.includes(product.id);
  const [showRedirectNotice, setShowRedirectNotice] = useState(false);

  // Check responsive size dynamically
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    handleResize(); // run once initially
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Auto scroll to top on product change
  useEffect(() => {
    setSelectedColor(product.colors[0]);
    setSelectedSize(product.sizes[0] || 'M');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [product]);

  // Curated alternatives — tag/category overlap scoring, fetched live per product.
  const [curatedAlternatives, setCuratedAlternatives] = useState<Product[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetchAlternatives(product.id, 4)
      .then((alternatives) => {
        if (!cancelled) setCuratedAlternatives(alternatives);
      })
      .catch((error) => {
        console.error('Failed to load alternatives:', error);
      });
    return () => {
      cancelled = true;
    };
  }, [product.id]);

  const brandName = product.brand || 'Dhaaga Luxury';

  const badgeAndEstimate = product.deliveryEstimate ? (
    <div className="bg-[#004B37]/5 border border-[#004B37]/10 p-3.5 rounded-[4px] flex items-start gap-2.5 my-4">
      <Truck className="w-5 h-5 text-[#003224] mt-0.5" />
      <div>
        <span className="text-xs font-semibold text-[#003224] uppercase tracking-wider block font-sans">Active Chat Delivery Priority</span>
        <p className="text-xs text-[#004B37] font-sans font-medium mt-0.5">{product.deliveryEstimate} — pre-approved artisan route.</p>
      </div>
    </div>
  ) : (
    <div className="bg-amber-50 border border-amber-200/50 p-3.5 rounded-[4px] flex items-start gap-2.5 my-4">
      <Truck className="w-5 h-5 text-amber-700 mt-0.5" />
      <div>
        <span className="text-xs font-semibold text-amber-800 uppercase tracking-wider block font-sans">Standard Delivery Route</span>
        <p className="text-xs text-gray-600 font-sans mt-0.5">Arrives in 6-8 business days (Handcrafted to order in Multan/Lahore workshops).</p>
      </div>
    </div>
  );

  const colorsAndSwatches = (
    <div className="space-y-2">
      <span className="text-xs uppercase tracking-wider text-gray-500 font-bold font-sans">Color Palette</span>
      <div className="flex gap-2">
        {product.colors.map((color) => (
          <button
            key={color}
            onClick={() => setSelectedColor(color)}
            className={`px-4 py-2 rounded-full text-xs font-sans font-medium transition-all border ${
              selectedColor === color
                ? 'bg-[#003224] text-white border-[#003224]'
                : 'bg-white text-gray-700 border-gray-200 hover:border-gray-400'
            }`}
          >
            {color}
          </button>
        ))}
      </div>
    </div>
  );

  const sizeSelector = (
    <div className="space-y-2">
      <div className="flex justify-between items-center max-w-sm">
        <span className="text-xs uppercase tracking-wider text-gray-500 font-bold font-sans">Select Size</span>
        <button className="text-[11px] text-[#003224] underline font-sans font-medium">Sizing Chart</button>
      </div>
      <div className="flex gap-2">
        {product.sizes.map((s) => (
          <button
            key={s}
            onClick={() => setSelectedSize(s)}
            className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-sans font-semibold transition-all border ${
              selectedSize === s
                ? 'bg-[#003224] border-[#003224] text-white'
                : 'bg-white border-gray-200 text-gray-700 hover:border-gray-400'
            }`}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );

  const handleRedirectAction = (e: React.MouseEvent) => {
    e.preventDefault();
    if (product.productUrl) {
      // Opens in a new tab so the shopper doesn't lose their Dhaaga session.
      window.open(product.productUrl, '_blank', 'noopener,noreferrer');
    }
    setShowRedirectNotice(true);
    setTimeout(() => {
      setShowRedirectNotice(false);
    }, 3000);
  };

  const actionButtons = (
    <div className="space-y-3 pt-4">
      <button
        onClick={handleRedirectAction}
        disabled={!product.productUrl}
        className="w-full bg-[#003224] text-[#FCF9F8] hover:bg-[#004B37] disabled:opacity-50 disabled:cursor-not-allowed rounded-full py-4 px-6 font-sans font-semibold text-sm transition-all flex items-center justify-center gap-2 tracking-wide shadow-[0_4px_12px_rgba(0,50,36,0.15)] cursor-pointer"
      >
        <ShoppingBag className="w-4 h-4" />
        <span>View on {brandName}</span>
        <ExternalLink className="w-3.5 h-3.5" />
      </button>
      <div className="flex gap-2">
        <button
          onClick={() => onToggleWishlist(product.id)}
          className={`flex-1 border rounded-full py-2.5 px-4 text-xs font-sans font-semibold transition-all flex items-center justify-center gap-2 cursor-pointer ${
            isLiked ? 'bg-red-50 border-red-200 text-red-600' : 'bg-white border-gray-200 text-gray-700 hover:border-gray-400'
          }`}
        >
          <Heart className={`w-4 h-4 ${isLiked ? 'fill-red-600 text-red-600' : ''}`} />
          <span>{isLiked ? 'Saved to Wishlist' : 'Save to Board'}</span>
        </button>
      </div>
    </div>
  );

  // Curated Alternatives Grid Segment
  const alternativesSection = (
    <div className="space-y-6 pt-12 border-t border-gray-100">
      <div className="flex justify-between items-baseline">
        <div>
          <h3 className="font-serif text-2xl italic font-bold text-[#1C1B1B]">Curated Alternatives</h3>
          <p className="text-xs text-gray-500 font-sans mt-1">Heritage alternatives matching your visual search profile.</p>
        </div>
        <span className="text-xs text-gray-400 font-sans uppercase tracking-widest font-bold">Similarity Clustering</span>
      </div>

      {isMobile ? (
        <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-none -mx-4 px-4">
          {curatedAlternatives.map((p) => (
            <div
              key={p.id}
              onClick={() => onSelectProduct(p)}
              className="bg-white border border-gray-100 rounded-[4px] p-2.5 w-44 flex-shrink-0 cursor-pointer hover:border-gray-300 transition-all shadow-sm flex flex-col justify-between"
            >
              <div className="relative aspect-[3/4] w-full bg-gray-50 overflow-hidden mb-2 rounded-[4px]">
                <img src={p.image} alt={p.name} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
              </div>
              <div className="space-y-1">
                <h4 className="font-sans text-xs font-semibold text-gray-900 line-clamp-1">{p.name}</h4>
                <p className="text-xs font-bold text-[#003224]">Rs. {p.price.toLocaleString('en-PK')}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-6">
          {curatedAlternatives.map((p) => (
            <div
              key={p.id}
              onClick={() => onSelectProduct(p)}
              className="bg-white border border-gray-100 rounded-[4px] p-3 overflow-hidden group cursor-pointer hover:border-gray-300 transition-all shadow-sm flex flex-col justify-between"
            >
              <div className="relative aspect-[3/4] w-full bg-gray-50 overflow-hidden mb-3" style={{ borderRadius: '4px' }}>
                <img
                  src={p.image}
                  alt={p.name}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-102"
                  referrerPolicy="no-referrer"
                />
              </div>
              <div className="space-y-1.5">
                <h4 className="font-sans text-xs font-semibold text-gray-900 line-clamp-1 group-hover:text-[#003224]">
                  {p.name}
                </h4>
                <p className="text-xs font-bold text-[#003224] font-sans">
                  Rs. {p.price.toLocaleString('en-PK')}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-[#FCF9F8] flex flex-col justify-start relative">
      {/* Dynamic Toast instead of annoying window.alert */}
      <AnimatePresence>
        {showRedirectNotice && (
          <motion.div
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -50 }}
            className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-[#003224] text-white text-xs sm:text-sm font-sans font-semibold py-3 px-6 rounded-md shadow-2xl border border-[#004B37] flex items-center gap-2"
          >
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span>Connecting to {brandName}'s design studio...</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header Nav */}
      <header className="px-4 sm:px-8 py-4 bg-white/85 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between border-b border-gray-100">
        <button onClick={onBack} className="p-1.5 text-gray-600 hover:text-black flex items-center gap-1.5 cursor-pointer">
          <ArrowLeft className="w-5 h-5 lg:w-4 lg:h-4" />
          <span className="text-xs font-sans font-semibold">Back to Search</span>
        </button>
        <span className="font-serif text-lg sm:text-xl tracking-[0.25em] text-[#003224] uppercase font-bold">DHAAGA</span>
        <div className="flex items-center gap-3">
          <div className="hidden lg:block text-xs bg-[#FCF9F8] text-[#003224] px-3.5 py-1 rounded-full border border-gray-100 font-sans font-bold">
            Heritage Collection
          </div>
          <button
            onClick={onOpenWishlist}
            className="p-1.5 hover:bg-gray-100 rounded-full transition-colors cursor-pointer text-gray-500 hover:text-[#003224] relative flex items-center justify-center"
            title="Saved Collection"
          >
            <Heart className={`w-4.5 h-4.5 ${wishlist.length > 0 ? 'fill-[#003224] text-[#003224]' : ''}`} />
            {wishlist.length > 0 && (
              <span className="absolute -top-0.5 -right-0.5 bg-[#003224] text-white text-[8px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center">
                {wishlist.length}
              </span>
            )}
          </button>
        </div>
      </header>

      {isMobile ? (
        /* Mobile Detail Layout */
        <div className="flex-1 overflow-y-auto">
          {/* Main Full-Width Image */}
          <div className="relative aspect-[3/4] w-full bg-gray-100">
            <img
              src={product.image}
              alt={product.name}
              className="w-full h-full object-cover"
              referrerPolicy="no-referrer"
            />
            <div className="absolute top-4 left-4 bg-white/95 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider text-[#003224] font-sans">
              {brandName}
            </div>
          </div>

          {/* Info Details Content */}
          <div className="p-5 space-y-6 bg-[#FCF9F8]">
            <div className="space-y-2">
              <span className="text-xs font-bold uppercase tracking-widest text-[#003224] font-sans">{product.category}</span>
              <h1 className="font-sans text-xl font-bold text-[#1C1B1B] leading-tight">{product.name}</h1>
              <p className="text-lg font-bold text-[#003224] font-sans">Rs. {product.price.toLocaleString('en-PK')}</p>
            </div>

            {/* Delivery Estimate */}
            {badgeAndEstimate}

            {/* Colors */}
            {colorsAndSwatches}

            {/* Sizes */}
            {sizeSelector}

            {/* Product Narrative */}
            <div className="space-y-2 border-t border-gray-100 pt-4">
              <span className="text-xs uppercase tracking-wider text-gray-500 font-bold font-sans">Artisanship & Fabric</span>
              <p className="text-xs text-gray-600 leading-relaxed font-sans whitespace-pre-line">{product.description}</p>
              <div className="flex flex-wrap gap-1.5 pt-2">
                {product.tags.map(t => (
                  <span key={t} className="bg-white border border-gray-200 text-gray-500 text-[9px] font-sans py-0.5 px-2 rounded-full">
                    #{t}
                  </span>
                ))}
              </div>
            </div>

            {/* Action buttons */}
            {actionButtons}

            {/* Curated Alternatives scroll row */}
            {alternativesSection}
          </div>
        </div>
      ) : (
        /* Desktop Rendering */
        <main className="max-w-5xl mx-auto w-full px-6 sm:px-8 py-10 space-y-12 flex-1">
          {/* Two-column Detail section */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-10 bg-white border border-gray-100 rounded-[4px] p-6 lg:p-8 shadow-sm">
            {/* Left Column: Image setup */}
            <div className="space-y-4">
              <div className="relative aspect-[3/4] w-full bg-gray-50 overflow-hidden" style={{ borderRadius: '4px' }}>
                <img
                  src={product.image}
                  alt={product.name}
                  className="w-full h-full object-cover"
                  referrerPolicy="no-referrer"
                />
                <span className="absolute top-4 left-4 bg-white/95 text-[#003224] text-[10px] uppercase tracking-wider font-bold font-sans py-1 px-3 rounded-full border border-gray-100">
                  {brandName}
                </span>
              </div>

              {/* Secondary smaller lookbook image below */}
              {product.secondaryImage && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="aspect-[3/4] rounded-[4px] overflow-hidden bg-gray-150 border border-gray-200">
                    <img src={product.secondaryImage} alt="Details" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                  </div>
                  <div className="aspect-[3/4] rounded-[4px] overflow-hidden bg-gray-150 border border-gray-200">
                    <img src={product.image} alt="Fitting" className="w-full h-full object-cover brightness-95" referrerPolicy="no-referrer" />
                  </div>
                  <div className="aspect-[3/4] rounded-[4px] bg-[#003224]/5 border border-[#003224]/10 flex flex-col justify-center items-center text-center p-3">
                    <span className="text-[9px] uppercase font-bold text-[#003224] tracking-wider mb-1">Tailor Match</span>
                    <p className="text-[10px] text-gray-500 font-sans">Handmade custom hem service active.</p>
                  </div>
                </div>
              )}
            </div>

            {/* Right Column: Information panel */}
            <div className="flex flex-col justify-between space-y-6">
              <div className="space-y-4">
                <div className="space-y-1">
                  <span className="text-xs font-semibold uppercase tracking-widest text-[#003224] font-sans">{product.category}</span>
                  <h1 className="font-sans text-2xl lg:text-3xl font-bold text-[#1C1B1B] tracking-tight">{product.name}</h1>
                  <p className="text-xl font-bold text-[#003224] font-sans mt-1">Rs. {product.price.toLocaleString('en-PK')}</p>
                </div>

                {/* Delivery Estimate */}
                {badgeAndEstimate}

                {/* Colors */}
                {colorsAndSwatches}

                {/* Sizes */}
                {sizeSelector}

                {/* Description */}
                <div className="space-y-2 border-t border-gray-100 pt-4">
                  <span className="text-xs uppercase tracking-wider text-gray-400 font-bold font-sans block">Craftsmanship Story</span>
                  <p className="text-xs text-gray-600 leading-relaxed font-sans whitespace-pre-line">{product.description}</p>
                  <div className="flex gap-1.5 pt-1">
                    {product.tags.map(t => (
                      <span key={t} className="bg-[#FCF9F8] border border-gray-200 text-gray-500 text-[10px] font-sans py-0.5 px-2.5 rounded-full">
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Actions */}
              {actionButtons}
            </div>
          </div>

          {/* Alternatives row */}
          {alternativesSection}
        </main>
      )}

      {/* Footer */}
      <footer className="border-t border-gray-100 bg-white py-12 px-8 text-center text-xs text-gray-400 font-sans">
        <p className="font-serif tracking-[0.25em] text-[#003224] font-bold text-sm uppercase mb-2">DHAAGA</p>
        <p>© 2026 Dhaaga Luxury. Hand loomed with honor in Pakistan.</p>
      </footer>
    </div>
  );
}
