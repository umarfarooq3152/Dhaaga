import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Heart, Eye, Trash2, ArrowRight } from 'lucide-react';
import { Product } from '../types';

interface WishlistDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  wishlistProducts: Product[];
  onToggleWishlist: (productId: string) => void;
  onSelectProduct: (product: Product) => void;
}

export default function WishlistDrawer({
  isOpen,
  onClose,
  wishlistProducts,
  onToggleWishlist,
  onSelectProduct
}: WishlistDrawerProps) {
  const savedProducts = wishlistProducts;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop blur overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.4 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 z-100 backdrop-blur-xs"
          />

          {/* Slide-over Drawer Panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 240 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-[#FAF9F5] z-100 shadow-[0_-8px_32px_rgba(0,50,36,0.15)] border-l border-gray-200/60 flex flex-col justify-between text-[#1C1B1B] font-sans"
          >
            {/* Header */}
            <div className="p-5 border-b border-gray-200/50 flex items-center justify-between bg-white">
              <div className="flex items-center gap-2">
                <Heart className="w-4 h-4 text-[#003224] fill-[#003224]" />
                <span className="font-serif text-lg font-bold tracking-wide">Saved Collection</span>
                <span className="text-[10px] bg-[#003224]/5 text-[#003224] font-bold px-2 py-0.5 rounded-full">
                  {savedProducts.length} {savedProducts.length === 1 ? 'item' : 'items'}
                </span>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 hover:bg-gray-100 rounded-full transition-colors cursor-pointer text-gray-500 hover:text-black"
                title="Close Saved"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* List Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {savedProducts.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4">
                  <div className="w-12 h-12 rounded-full bg-[#003224]/5 flex items-center justify-center text-[#003224]">
                    <Heart className="w-5 h-5 text-[#003224]/50" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-serif text-base font-semibold text-gray-900">Your collection is empty</h3>
                    <p className="text-xs text-gray-400 max-w-xs leading-relaxed">
                      Tap the heart icon on any design to curate your personal wardrobe of exquisite Pakistani craftsmanship.
                    </p>
                  </div>
                  <button
                    onClick={onClose}
                    className="bg-[#003224] text-white text-[10px] uppercase tracking-widest font-bold py-2.5 px-5 rounded-full hover:bg-[#004B37] transition-all cursor-pointer shadow-xs"
                  >
                    Explore Catalog
                  </button>
                </div>
              ) : (
                <div className="space-y-3.5">
                  {savedProducts.map((p) => (
                    <div
                      key={p.id}
                      className="bg-white border border-gray-150 p-3 rounded-lg flex gap-3.5 hover:border-gray-300 transition-all shadow-xs group"
                    >
                      {/* Product Thumbnail */}
                      <div className="w-20 aspect-[3/4] bg-gray-50 overflow-hidden rounded-[4px] shrink-0 relative">
                        <img
                          src={p.image}
                          alt={p.name}
                          className="w-full h-full object-cover"
                          referrerPolicy="no-referrer"
                        />
                      </div>

                      {/* Details & Actions */}
                      <div className="flex-1 flex flex-col justify-between">
                        <div className="space-y-0.5">
                          <span className="text-[9px] uppercase tracking-wider text-[#003224] font-bold font-sans">
                            {p.brand}
                          </span>
                          <h4 className="font-sans text-xs font-semibold text-gray-900 line-clamp-1">
                            {p.name}
                          </h4>
                          <p className="text-xs font-bold text-[#003224] font-sans">
                            Rs. {p.price.toLocaleString('en-PK')}
                          </p>
                          <span className="inline-block text-[9px] text-gray-400 font-sans italic">
                            {p.occasion}
                          </span>
                        </div>

                        {/* Quick Action buttons */}
                        <div className="flex items-center gap-2 pt-1.5 border-t border-gray-50">
                          <button
                            onClick={() => {
                              onSelectProduct(p);
                              onClose();
                            }}
                            className="text-[10px] text-[#003224] hover:text-[#004B37] font-bold flex items-center gap-1 cursor-pointer hover:underline"
                          >
                            <Eye className="w-3 h-3" />
                            <span>View Details</span>
                          </button>
                          <span className="text-gray-300 text-xs">|</span>
                          <button
                            onClick={() => onToggleWishlist(p.id)}
                            className="text-[10px] text-red-500 hover:text-red-700 font-bold flex items-center gap-1 cursor-pointer hover:underline"
                          >
                            <Trash2 className="w-3 h-3" />
                            <span>Remove</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer summary */}
            {savedProducts.length > 0 && (
              <div className="p-5 border-t border-gray-200/50 bg-white space-y-4">
                <div className="flex justify-between items-baseline">
                  <span className="text-xs font-semibold text-gray-500 uppercase font-sans">Estimated Total</span>
                  <span className="font-sans text-base font-bold text-[#003224]">
                    Rs. {savedProducts.reduce((sum, p) => sum + p.price, 0).toLocaleString('en-PK')}
                  </span>
                </div>
                <p className="text-[10px] text-gray-400 font-sans leading-relaxed">
                  These heritage pieces are custom-made on order. Contact our AI Assistant anytime to proceed with customized fittings or group orders.
                </p>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
