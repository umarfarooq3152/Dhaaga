import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, Mic, Heart, ShoppingBag, ArrowRight, User, LogOut, ShieldCheck, LogIn } from 'lucide-react';
// @ts-ignore
import searchBarBg from '../assets/images/search_bar_bg_1783947191734.jpg';
import dhaagaLogo from '../assets/images/dhaaga-logo.png';
import { fetchCollections } from '../api/collections';
import { fetchBrands } from '../api/brands';
import { ApiBrand, ApiCollection } from '../types';
import { AuthUser } from '../api/auth';
import { useVoiceRecording } from '../hooks/useVoiceRecording';

interface DiscoveryScreenProps {
  userName: string;
  department?: 'men' | 'women';
  onEnterChat: (initialQuery?: string, initialFilters?: { style?: string, occasion?: string, budget?: string }) => void;
  onSelectCollection: (colTitle: string) => void;
  wishlist: string[];
  onToggleWishlist: (productId: string) => void;
  onOpenWishlist: () => void;
  authUser: AuthUser | null;
  onOpenAuth: () => void;
  onLogout: () => void;
}

// Quick-search suggestion chips — clicking one routes into chat search with
// that phrase as the query (Discovery screen itself has no results grid).
const QUICK_SEARCH_CHIPS = ['Eid Edit', 'Budget under 50k', 'Subtle embroidery work'];

export default function DiscoveryScreen({
  userName,
  department,
  onEnterChat,
  onSelectCollection,
  wishlist,
  onToggleWishlist,
  onOpenWishlist,
  authUser,
  onOpenAuth,
  onLogout
}: DiscoveryScreenProps) {
  const [searchInput, setSearchInput] = useState('');
  const [showProfile, setShowProfile] = useState(false);
  const [activeChips, setActiveChips] = useState<string[]>(QUICK_SEARCH_CHIPS);
  const [collections, setCollections] = useState<ApiCollection[]>([]);
  const [menswearBrands, setMenswearBrands] = useState<ApiBrand[]>([]);

  useEffect(() => {
    fetchCollections()
      .then(setCollections)
      .catch((error) => console.error('Failed to load collections:', error));
  }, []);

  useEffect(() => {
    if (department !== 'men') return;
    fetchBrands()
      .then((brands) => setMenswearBrands(brands.filter((b) => b.department === 'men')))
      .catch((error) => console.error('Failed to load menswear brands:', error));
  }, [department]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onEnterChat(searchInput || 'I need an elegant outfit for a special occasion');
  };

  // Voice search: records via the mic, transcribes through the backend
  // (Whisper via Groq), then jumps straight into chat with the spoken
  // query — "speak and get results," matching the search bar's own flow.
  const { isRecording, isTranscribing, error: voiceError, startRecording, stopRecording } =
    useVoiceRecording((text) => onEnterChat(text));

  const handleMicClick = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleChipClick = (chip: string) => {
    onEnterChat(chip);
  };

  const removeChip = (chipToRemove: string) => {
    setActiveChips(prev => prev.filter(c => c !== chipToRemove));
  };

  return (
    <div className="min-h-screen bg-[#FBF9F6] flex flex-col justify-start relative overflow-x-hidden selection:bg-[#003224]/10 selection:text-[#003224] text-[#1C1B1B]">
      
      {/* 1. Header — Ultra-Minimalist & Pristine */}
      <header className="bg-[#FBF9F6] z-50 px-6 sm:px-12 py-6 border-b border-gray-100/40">
        <div className="max-w-6xl mx-auto flex items-center justify-between relative">
          {/* Left spacer for symmetry */}
          <div className="w-24 sm:w-32" />

          {/* Center Brand Name Logo */}
          <div className="text-center flex-1 flex justify-center">
            <img
              src={dhaagaLogo}
              alt="Dhaaga"
              onClick={() => window.location.reload()}
              className="h-9 sm:h-11 w-auto cursor-pointer"
            />
          </div>

          {/* Minimalist Utility Icons */}
          <div className="flex items-center gap-3.5 sm:gap-4.5 justify-end w-24 sm:w-32">
            <button
              onClick={onOpenWishlist}
              className="p-1 text-gray-500 hover:text-[#003224] transition-all cursor-pointer relative"
              title="Saved Collection"
            >
              <Heart className={`w-4 h-4 sm:w-4.5 sm:h-4.5 ${wishlist.length > 0 ? 'fill-[#003224] text-[#003224]' : ''}`} />
              {wishlist.length > 0 && (
                <span className="absolute -top-1 -right-1.5 bg-[#003224] text-white text-[8px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center">
                  {wishlist.length}
                </span>
              )}
            </button>
            <button className="p-1 text-gray-500 hover:text-[#003224] transition-all cursor-pointer" title="Shopping Bag">
              <ShoppingBag className="w-4 h-4 sm:w-4.5 sm:h-4.5" />
            </button>
            
            {/* Profile Dropdown Trigger */}
            <div className="relative">
              <button 
                onClick={() => setShowProfile(!showProfile)}
                className={`p-1 rounded-full transition-all cursor-pointer flex items-center justify-center ${showProfile ? 'bg-gray-100 text-[#003224]' : 'text-gray-500 hover:text-[#003224]'}`}
                title="My Profile"
              >
                <User className="w-4 h-4 sm:w-4.5 sm:h-4.5" />
              </button>

              <AnimatePresence>
                {showProfile && (
                  <>
                    {/* Backdrop to close dropdown */}
                    <div 
                      className="fixed inset-0 z-40" 
                      onClick={() => setShowProfile(false)}
                    />
                    
                    {/* Minimalist Profile Card */}
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 8, scale: 0.95 }}
                      transition={{ duration: 0.15, ease: 'easeOut' }}
                      className="absolute right-0 mt-3 w-56 bg-white border border-gray-200/60 rounded-xl shadow-xl z-50 p-4 text-left font-sans"
                    >
                      {authUser ? (
                        <>
                          <div className="pb-3 border-b border-gray-100 mb-2">
                            <p className="text-[10px] uppercase tracking-wider text-gray-400 font-bold mb-0.5">Account</p>
                            <p className="font-serif text-sm font-bold text-gray-900 leading-snug">{authUser.name}</p>
                            <p className="text-[10px] text-gray-500 truncate mt-0.5">{authUser.email}</p>
                          </div>

                          <div className="space-y-1 text-xs">
                            <div className="flex items-center gap-2.5 py-2 px-2 rounded-lg text-gray-600">
                              <ShieldCheck className="w-4 h-4 text-emerald-700" />
                              <span>Member</span>
                            </div>
                            <div
                              onClick={() => {
                                setShowProfile(false);
                                onLogout();
                              }}
                              className="flex items-center gap-2.5 py-2 px-2 rounded-lg text-red-600 hover:bg-red-50 cursor-pointer transition-colors mt-1.5 pt-2 border-t border-gray-100"
                            >
                              <LogOut className="w-4 h-4" />
                              <span>Log Out</span>
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="pb-3 border-b border-gray-100 mb-2">
                            <p className="text-[10px] uppercase tracking-wider text-gray-400 font-bold mb-0.5">Account</p>
                            <p className="text-xs text-gray-600 leading-snug">
                              Log in to save your wishlist and preferences across devices.
                            </p>
                          </div>
                          <div
                            onClick={() => {
                              setShowProfile(false);
                              onOpenAuth();
                            }}
                            className="flex items-center gap-2.5 py-2 px-2 rounded-lg text-[#003224] font-bold hover:bg-gray-50 cursor-pointer transition-colors text-xs"
                          >
                            <LogIn className="w-4 h-4" />
                            <span>Log In / Sign Up</span>
                          </div>
                        </>
                      )}
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </header>

      {/* 2. Hero Interactive Workspace */}
      <main className="flex-1 flex flex-col justify-center">
        
        {/* Soft, textured ambient background wrapper */}
        <div className="relative w-full min-h-[500px] lg:min-h-[550px] flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-12">
          
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            {/* Custom generated aesthetic watercolor thread background */}
            <img 
              src={searchBarBg} 
              alt="Search Background" 
              className="w-full h-full object-cover opacity-90"
              referrerPolicy="no-referrer"
            />
            {/* Subtle overlay to guarantee high-contrast text readability */}
            <div className="absolute inset-0 bg-[#FBF9F6]/10 mix-blend-multiply" />
          </div>

          {/* Core Content Cluster */}
          <div className="relative z-20 max-w-4xl mx-auto w-full space-y-8 sm:space-y-10">
            
            {/* Clean Minimal Search Header */}
            <div className="max-w-2xl mx-auto text-center space-y-4">
              <h1 className="font-serif text-3xl sm:text-4xl lg:text-4.5xl font-medium text-gray-900 tracking-tight leading-tight">
                Find your perfect outfit
              </h1>
              <p className="text-xs sm:text-sm text-gray-500 max-w-lg mx-auto leading-relaxed">
                Describe what you need, and find matches instantly.
              </p>

              {/* Floating Input Bar */}
              <form onSubmit={handleSearchSubmit} className="relative max-w-xl mx-auto pt-2">
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="e.g. Ivory raw silk sherwani, or red lehenga under 50k"
                  className="w-full bg-white/90 backdrop-blur-md border-2 border-[#003224]/30 focus:border-[#003224] focus:ring-2 focus:ring-[#003224]/20 rounded-full py-4.5 pl-12 pr-14 text-xs sm:text-sm font-sans outline-none transition-all shadow-md hover:shadow-lg text-[#003224] placeholder-[#003224]/70 font-semibold"
                />
                <Search className="absolute left-4.5 top-1/2 -translate-y-1/2 text-[#003224] w-5 h-5 opacity-90" />
                
                {/* Voice mic button */}
                <button
                  type="button"
                  onClick={handleMicClick}
                  disabled={isTranscribing}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 text-white rounded-full p-2.5 transition-all shadow-sm cursor-pointer flex items-center justify-center hover:scale-105 active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed ${isRecording ? 'bg-red-500 hover:bg-red-600' : 'bg-[#003224] hover:bg-[#004B37]'}`}
                  title="Search with Voice"
                >
                  <Mic className={`w-4 h-4 ${isRecording ? 'animate-pulse' : ''}`} />
                </button>
              </form>
              {isRecording && (
                <p className="text-xs text-[#003224] font-sans font-semibold flex items-center justify-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                  Listening... tap the mic again to stop
                </p>
              )}
              {isTranscribing && (
                <p className="text-xs text-gray-500 font-sans">Transcribing your voice search...</p>
              )}
              {voiceError && <p className="text-xs text-red-600 font-sans">{voiceError}</p>}

              {/* Quick-search suggestion chips */}
              {activeChips.length > 0 && (
                <div className="flex flex-wrap justify-center gap-1.5 pt-1">
                  {activeChips.map((chip) => (
                    <span
                      key={chip}
                      className="inline-flex items-center gap-1 bg-white border border-gray-200/60 text-gray-600 text-[10px] font-sans font-medium py-1 px-3 rounded-full"
                    >
                      <button
                        type="button"
                        onClick={() => handleChipClick(chip)}
                        className="cursor-pointer hover:text-[#003224]"
                      >
                        {chip}
                      </button>
                      <button
                        type="button"
                        onClick={() => removeChip(chip)}
                        className="hover:text-red-600 transition-colors cursor-pointer ml-1 text-xs font-bold"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Elegant Center Explore Button */}
              <div className="pt-6">
                <button
                  onClick={() => onEnterChat('')}
                  className="bg-[#003224] hover:bg-[#004b37] text-white text-[11px] uppercase tracking-[0.25em] font-bold py-3.5 px-8 rounded-full transition-all cursor-pointer shadow-md flex items-center gap-2.5 mx-auto hover:scale-101 hover:shadow-lg"
                >
                  <span>Explore Collection</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>

          </div>
        </div>

        {/* 3. Menswear Labels — shown only when the shopper picked Menswear at onboarding */}
        {department === 'men' && menswearBrands.length > 0 && (
          <section className="px-6 sm:px-12 pb-10">
            <div className="max-w-6xl mx-auto space-y-5">
              <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#1C1B1B]">
                Menswear Labels
              </h2>
              <div className="flex flex-wrap gap-2.5">
                {menswearBrands.map((brand) => (
                  <button
                    key={brand.id}
                    onClick={() => onEnterChat(`Show me ${brand.name}`)}
                    className="bg-white border border-gray-200/60 text-[#1C1B1B] text-xs font-sans font-semibold py-2 px-4 rounded-full hover:border-[#003224] hover:text-[#003224] transition-all cursor-pointer shadow-xs"
                  >
                    {brand.name}
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* 4. Curated Editorial Collections */}
        {collections.length > 0 && (
          <section className="px-6 sm:px-12 pb-16">
            <div className="max-w-6xl mx-auto space-y-5">
              <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#1C1B1B]">
                Curated for you
              </h2>
              <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-none -mx-1 px-1">
                {collections.map((collection) => (
                  <button
                    key={collection.id}
                    onClick={() => onSelectCollection(collection.title)}
                    className="text-left flex-shrink-0 w-56 bg-white border border-gray-100 rounded-[4px] overflow-hidden shadow-sm hover:border-gray-300 transition-all cursor-pointer"
                  >
                    <div className="aspect-[4/3] w-full bg-gray-50 overflow-hidden">
                      {collection.image_url ? (
                        <img
                          src={collection.image_url}
                          alt={collection.title}
                          className="w-full h-full object-cover"
                          referrerPolicy="no-referrer"
                        />
                      ) : (
                        <div className="w-full h-full bg-[#003224]/5" />
                      )}
                    </div>
                    <div className="p-3.5 space-y-0.5">
                      <h3 className="font-serif text-sm font-bold text-[#1C1B1B]">{collection.title}</h3>
                      {collection.subtitle && (
                        <p className="text-[10px] text-gray-500 font-sans">{collection.subtitle}</p>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </section>
        )}

      </main>

      {/* 5. Footer */}
      <footer className="border-t border-gray-150/50 bg-[#FBF9F6] py-10 px-6 text-center text-[11px] text-gray-400 font-sans">
        <p className="font-serif tracking-[0.2em] text-[#003224] font-bold text-xs uppercase mb-1">DHAAGA</p>
        <p>© 2026 Dhaaga. Crafted with dignity and heritage honor in Pakistan.</p>
      </footer>

    </div>
  );
}
