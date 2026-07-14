import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, ArrowRightLeft, Settings, X, HelpCircle } from 'lucide-react';

import OnboardingScreen from './components/OnboardingScreen';
import DiscoveryScreen from './components/DiscoveryScreen';
import ChatSearchScreen from './components/ChatSearchScreen';
import ProductDetailScreen from './components/ProductDetailScreen';
import WishlistDrawer from './components/WishlistDrawer';

import { CurrentScreen, Product } from './types';
import { INITIAL_PRODUCTS } from './data';

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<CurrentScreen>('onboarding');
  const [userName, setUserName] = useState<string>('Meera');
  const [preferredSize, setPreferredSize] = useState<string>('M');
  const [selectedProduct, setSelectedProduct] = useState<Product>(INITIAL_PRODUCTS[0]);
  const [chatQuery, setChatQuery] = useState<string>('');
  const [chatFilters, setChatFilters] = useState<{ style?: string, occasion?: string, budget?: string }>({});
  
  // Wishlist global state
  const [wishlist, setWishlist] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('dhaaga_wishlist');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [isWishlistOpen, setIsWishlistOpen] = useState(false);

  const handleToggleWishlist = (id: string) => {
    setWishlist((prev) => {
      const updated = prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id];
      try {
        localStorage.setItem('dhaaga_wishlist', JSON.stringify(updated));
      } catch (e) {
        console.error(e);
      }
      return updated;
    });
  };

  // Collapse controller for the minor helper switcher
  const [isSwitcherOpen, setIsSwitcherOpen] = useState(false);

  const handleOnboardingComplete = (name: string, size: string) => {
    setUserName(name);
    setPreferredSize(size);
    setCurrentScreen('discovery');
  };

  const handleOnboardingSkip = () => {
    setCurrentScreen('discovery');
  };

  const handleEnterChat = (query?: string, filters?: { style?: string, occasion?: string, budget?: string }) => {
    setChatQuery(query || '');
    setChatFilters(filters || {});
    setCurrentScreen('chat');
  };

  const handleSelectProduct = (prod: Product) => {
    setSelectedProduct(prod);
    setCurrentScreen('detail');
  };

  // Switch between screens directly
  const jumpToScreen = (screen: CurrentScreen) => {
    setCurrentScreen(screen);
    // Preset default selected product if jumping straight to detail
    if (screen === 'detail' && !selectedProduct) {
      setSelectedProduct(INITIAL_PRODUCTS[0]);
    }
  };

  return (
    <div className="min-h-screen bg-[#FCF9F8] text-[#1C1B1B] flex flex-col font-sans selection:bg-[#003224]/10 selection:text-[#003224] overflow-x-hidden">
      
      {/* Main Responsive Layout Wrapper */}
      <div className="flex-1 flex flex-col">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentScreen}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="flex-1 flex flex-col"
          >
            {currentScreen === 'onboarding' && (
              <OnboardingScreen
                onComplete={handleOnboardingComplete}
                onSkip={handleOnboardingSkip}
              />
            )}
            {currentScreen === 'discovery' && (
              <DiscoveryScreen
                userName={userName}
                onEnterChat={handleEnterChat}
                onSelectCollection={(title) => handleEnterChat('', { style: 'Anarkali Peshwas', occasion: 'Mehndi & Sangeet' })}
                wishlist={wishlist}
                onToggleWishlist={handleToggleWishlist}
                onOpenWishlist={() => setIsWishlistOpen(true)}
              />
            )}
            {currentScreen === 'chat' && (
              <ChatSearchScreen
                userName={userName}
                initialQuery={chatQuery}
                initialFilters={chatFilters}
                onBack={() => setCurrentScreen('discovery')}
                onSelectProduct={handleSelectProduct}
                wishlist={wishlist}
                onToggleWishlist={handleToggleWishlist}
                onOpenWishlist={() => setIsWishlistOpen(true)}
              />
            )}
            {currentScreen === 'detail' && (
              <ProductDetailScreen
                product={selectedProduct}
                onBack={() => setCurrentScreen('chat')}
                onSelectProduct={handleSelectProduct}
                wishlist={wishlist}
                onToggleWishlist={handleToggleWishlist}
                onOpenWishlist={() => setIsWishlistOpen(true)}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Global Saved Collection Drawer Panel */}
      <WishlistDrawer
        isOpen={isWishlistOpen}
        onClose={() => setIsWishlistOpen(false)}
        wishlist={wishlist}
        onToggleWishlist={handleToggleWishlist}
        onSelectProduct={handleSelectProduct}
      />

      {/* Minor Floating Step Switcher (Collapsible, non-intrusive drawer for review ease) */}
      <div className="fixed bottom-4 right-4 z-100 flex flex-col items-end gap-2">
        <AnimatePresence>
          {isSwitcherOpen && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 10 }}
              className="bg-[#003224] text-white p-4 rounded-lg shadow-2xl border border-[#004B37] max-w-xs font-sans"
            >
              <div className="flex items-center justify-between border-b border-[#004B37] pb-2 mb-2">
                <div className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
                  <span className="text-[10px] uppercase tracking-widest font-bold">Prototype Switcher</span>
                </div>
                <button
                  onClick={() => setIsSwitcherOpen(false)}
                  className="text-white/70 hover:text-white cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-[9px] text-emerald-200/80 mb-3 leading-relaxed">
                Jump directly between the four core screens of the custom journey:
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { id: 'onboarding', label: '1. Onboarding' },
                  { id: 'discovery', label: '2. Discovery' },
                  { id: 'chat', label: '3. AI Chat' },
                  { id: 'detail', label: '4. Detail View' }
                ].map((step) => (
                  <button
                    key={step.id}
                    onClick={() => {
                      jumpToScreen(step.id as CurrentScreen);
                      setIsSwitcherOpen(false);
                    }}
                    className={`px-2 py-1.5 rounded text-[10px] font-bold text-left transition-all cursor-pointer ${
                      currentScreen === step.id
                        ? 'bg-amber-400 text-[#003224]'
                        : 'bg-[#004B37] hover:bg-emerald-800 text-white'
                    }`}
                  >
                    {step.label}
                  </button>
                ))}
              </div>
              <div className="mt-3 pt-2 border-t border-[#004B37] flex items-center justify-between text-[9px] text-emerald-200/65">
                <span>Active User: <strong>{userName}</strong> (Size: {preferredSize})</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <button
          onClick={() => setIsSwitcherOpen(!isSwitcherOpen)}
          className="bg-[#003224] hover:bg-[#004B37] text-white p-3 rounded-full shadow-lg border border-emerald-600/30 transition-transform hover:scale-105 flex items-center justify-center cursor-pointer"
          title="Interactive Screen Switcher"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
