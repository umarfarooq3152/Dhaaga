import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';

import OnboardingScreen from './components/OnboardingScreen';
import DiscoveryScreen from './components/DiscoveryScreen';
import ChatSearchScreen from './components/ChatSearchScreen';
import ProductDetailScreen from './components/ProductDetailScreen';
import WishlistDrawer from './components/WishlistDrawer';
import AuthModal from './components/AuthModal';

import { CurrentScreen, Product } from './types';
import { useDeviceId } from './hooks/useDeviceId';
import { useWishlist } from './hooks/useWishlist';
import { useAuth } from './hooks/useAuth';
import { updateDeviceSize } from './api/devices';

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<CurrentScreen>('onboarding');
  const [userName, setUserName] = useState<string>('Meera');
  const [department, setDepartment] = useState<'men' | 'women' | undefined>(undefined);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [chatQuery, setChatQuery] = useState<string>('');
  const [chatFilters, setChatFilters] = useState<{ style?: string, occasion?: string, budget?: string }>({});

  const deviceId = useDeviceId();
  const auth = useAuth();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const { wishlist, wishlistProducts, toggleWishlist: handleToggleWishlist } = useWishlist(
    deviceId,
    auth.user?.id ?? null
  );
  const [isWishlistOpen, setIsWishlistOpen] = useState(false);

  // Once logged in, an account's saved preferences take over from
  // whatever was picked in onboarding (which only ever set client-side
  // state) — mirrors the "wishlist and preferences persist to account" ask.
  useEffect(() => {
    if (!auth.user) return;
    setUserName(auth.user.name);
    if (auth.user.department === 'men' || auth.user.department === 'women') {
      setDepartment(auth.user.department);
    }
  }, [auth.user]);

  const handleOnboardingComplete = (name: string, size: string, dept: 'men' | 'women') => {
    setUserName(name);
    setDepartment(dept);
    // Per TDD §10, only `size` persists server-side — name stays client-only.
    if (deviceId) {
      updateDeviceSize(deviceId, size).catch((error) => {
        console.error('Failed to save preferred size:', error);
      });
    }
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
                department={department}
                onEnterChat={handleEnterChat}
                onSelectCollection={(title) => handleEnterChat(`Show me the ${title}`)}
                wishlist={wishlist}
                onToggleWishlist={handleToggleWishlist}
                onOpenWishlist={() => setIsWishlistOpen(true)}
                authUser={auth.user}
                onOpenAuth={() => setIsAuthModalOpen(true)}
                onLogout={auth.logout}
              />
            )}
            {currentScreen === 'chat' && (
              <ChatSearchScreen
                userName={userName}
                department={department}
                initialQuery={chatQuery}
                initialFilters={chatFilters}
                onBack={() => setCurrentScreen('discovery')}
                onSelectProduct={handleSelectProduct}
                wishlist={wishlist}
                onToggleWishlist={handleToggleWishlist}
                onOpenWishlist={() => setIsWishlistOpen(true)}
                authUser={auth.user}
                onOpenAuth={() => setIsAuthModalOpen(true)}
                onLogout={auth.logout}
              />
            )}
            {currentScreen === 'detail' && selectedProduct && (
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
        wishlistProducts={wishlistProducts}
        onToggleWishlist={handleToggleWishlist}
        onSelectProduct={handleSelectProduct}
      />

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onLogin={auth.login}
        onSignup={auth.signup}
      />

    </div>
  );
}
