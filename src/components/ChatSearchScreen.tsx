import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, Mic, Send, ArrowLeft, Sparkles, SlidersHorizontal, Eye, RefreshCw, Compass, Heart, User, LogOut, ShieldCheck, LogIn } from 'lucide-react';
import { Product } from '../types';
import { useSessionChat } from '../hooks/useSessionChat';
import dhaagaLogo from '../assets/images/dhaaga-logo.png';
import { AuthUser } from '../api/auth';

interface ChatSearchScreenProps {
  userName: string;
  department?: 'men' | 'women';
  initialQuery?: string;
  initialFilters?: { style?: string, occasion?: string, budget?: string };
  onBack: () => void;
  onSelectProduct: (product: Product) => void;
  wishlist: string[];
  onToggleWishlist: (productId: string) => void;
  onOpenWishlist: () => void;
  authUser: AuthUser | null;
  onOpenAuth: () => void;
  onLogout: () => void;
}

// Beautiful Skeleton placeholders for high-fidelity loading experience
const ProductCardSkeleton = () => (
  <div className="bg-white rounded-[4px] p-2.5 overflow-hidden border border-gray-100 shadow-sm flex flex-col justify-between animate-pulse">
    <div className="space-y-3.5">
      {/* Image container skeleton */}
      <div className="aspect-[3/4] w-full bg-gray-200/60 rounded-[4px] relative overflow-hidden" />
      
      {/* Meta/Brand skeleton */}
      <div className="h-2.5 w-1/3 bg-gray-200/60 rounded" />
      
      {/* Title skeleton */}
      <div className="space-y-1.5">
        <div className="h-3.5 w-4/5 bg-gray-200/70 rounded" />
        <div className="h-2.5 w-1/2 bg-gray-200/40 rounded" />
      </div>
    </div>
    
    {/* Price & Occasion Footer */}
    <div className="pt-3.5 mt-3 border-t border-gray-50 flex items-center justify-between">
      <div className="h-3.5 w-16 bg-gray-200/70 rounded" />
      <div className="h-2.5 w-10 bg-gray-200/40 rounded" />
    </div>
  </div>
);

const ChatMessageSkeleton = () => (
  <div className="flex justify-start animate-pulse">
    <div className="max-w-[85%] px-4 py-3.5 rounded-2xl rounded-tl-none border border-gray-100 bg-[#FCF9F8] space-y-2.5 w-[280px] sm:w-[320px]">
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-[#004B37] animate-ping" />
        <span className="text-[9px] uppercase tracking-wider text-gray-400 font-bold font-sans">Formulating response...</span>
      </div>
      <div className="space-y-2">
        <div className="h-3 w-11/12 bg-gray-200/70 rounded" />
        <div className="h-3 w-10/12 bg-gray-200/70 rounded" />
        <div className="h-3 w-7/12 bg-gray-200/70 rounded" />
      </div>
    </div>
  </div>
);

export default function ChatSearchScreen({
  userName,
  department,
  initialQuery = '',
  initialFilters = {},
  onBack,
  onSelectProduct,
  wishlist,
  onToggleWishlist,
  onOpenWishlist,
  authUser,
  onOpenAuth,
  onLogout
}: ChatSearchScreenProps) {
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

  const [inputText, setInputText] = useState('');
  const { messages, filteredProducts, filters, isChatLoading, isProductsLoading, sendMessage, resetSession } =
    useSessionChat(userName, department, initialQuery, initialFilters);

  // Mobile sheet states
  const [isSheetExpanded, setIsSheetExpanded] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [showProfile, setShowProfile] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll chat to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSheetExpanded, isChatLoading]);

  // Custom user message submit
  const handleSendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim()) return;
    sendMessage(inputText);
    setInputText('');
  };

  // Voice note search (Feature 6) is deferred post-MVP — mic just toggles a
  // visual recording state for now, no real transcription yet.
  const handleMicClick = () => {
    setIsRecording((prev) => !prev);
  };

  // Individual chip removal isn't independently supported server-side yet
  // (session state has no "clear this one field" signal) — both actions
  // fall back to a full session reset, which is reliable.
  const removeFilter = (_key: keyof typeof filters) => {
    resetSession();
  };

  const resetAllFilters = () => {
    resetSession();
  };

  const storyStep = messages.length > 1 ? 1 : 0;

  // Shared Product Grid Component
  const renderProductGrid = (gridColsClass: string) => (
    <div className="space-y-6">
      {/* Active Filter Indicators */}
      <div className="flex items-center justify-between flex-wrap gap-3 bg-[#FCF9F8] p-4 rounded-[4px] border border-gray-150 shadow-sm">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1 font-sans">
            <SlidersHorizontal className="w-3.5 h-3.5 text-[#003224]" /> parsed intent:
          </span>
          {filters.occasion !== 'All Occasions' && (
            <span className="bg-[#003224] text-white text-xs font-semibold py-1.5 px-3.5 rounded-full flex items-center gap-1.5 shadow-sm">
              <span>Occasion: {filters.occasion}</span>
              <button onClick={() => removeFilter('occasion')} className="hover:text-red-300 font-bold ml-1 cursor-pointer transition-colors text-sm">×</button>
            </span>
          )}
          {filters.style !== 'All Styles' && (
            <span className="bg-[#003224] text-white text-xs font-semibold py-1.5 px-3.5 rounded-full flex items-center gap-1.5 shadow-sm">
              <span>Style: {filters.style}</span>
              <button onClick={() => removeFilter('style')} className="hover:text-red-300 font-bold ml-1 cursor-pointer transition-colors text-sm">×</button>
            </span>
          )}
          {filters.budget !== 'All Budgets' && (
            <span className="bg-[#003224] text-white text-xs font-semibold py-1.5 px-3.5 rounded-full flex items-center gap-1.5 shadow-sm">
              <span>Budget: {filters.budget}</span>
              <button onClick={() => removeFilter('budget')} className="hover:text-red-300 font-bold ml-1 cursor-pointer transition-colors text-sm">×</button>
            </span>
          )}
          {storyStep > 0 && (
            <button
              onClick={resetAllFilters}
              className="text-xs text-gray-400 hover:text-[#003224] underline ml-2 font-sans font-semibold cursor-pointer"
            >
              Clear All
            </button>
          )}
        </div>
        <span className="text-xs text-gray-500 font-sans font-semibold bg-white px-2.5 py-1 rounded border border-gray-150 shadow-xs">
          {filteredProducts.length} results
        </span>
      </div>

      {isProductsLoading ? (
        <div className={`grid ${gridColsClass} gap-4 sm:gap-6`}>
          {Array.from({ length: 6 }).map((_, i) => (
            <ProductCardSkeleton key={`skeleton-${i}`} />
          ))}
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="text-center py-16 bg-white border border-gray-100 rounded-[4px] shadow-xs">
          <p className="text-sm text-gray-400 font-sans">No matching heritage garments found in this range.</p>
          <button onClick={resetAllFilters} className="text-[#003224] text-xs underline font-semibold mt-2 cursor-pointer">
            Reset Filters
          </button>
        </div>
      ) : (
        <div className={`grid ${gridColsClass} gap-4 sm:gap-6`}>
          {filteredProducts.map((p) => (
            <motion.div
              layout
              key={p.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ duration: 0.3 }}
              onClick={() => onSelectProduct(p)}
              className={`bg-white rounded-[4px] p-2.5 overflow-hidden group cursor-pointer hover:border-gray-400 transition-all shadow-sm flex flex-col justify-between ${
                p.id === filteredProducts[0]?.id
                  ? 'border-2 border-[#003224]'
                  : 'border border-gray-100'
              }`}
            >
              <div className="relative aspect-[3/4] w-full bg-gray-50 overflow-hidden mb-3" style={{ borderRadius: '4px' }}>
                <img
                  src={p.image}
                  alt={p.name}
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-102"
                  referrerPolicy="no-referrer"
                />
                
                {p.id === filteredProducts[0]?.id && (
                  <div className="absolute top-2.5 right-2.5 bg-[#003224] text-[#FCF9F8] text-[8px] font-extrabold tracking-widest px-2.5 py-1 rounded-sm shadow-md z-20">
                    MOST MATCHED
                  </div>
                )}

                {/* Heart toggle button on card */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleWishlist(p.id);
                  }}
                  className={`absolute ${p.id === filteredProducts[0]?.id ? 'top-11' : 'top-2.5'} right-2.5 z-30 p-1.5 rounded-full bg-white/90 backdrop-blur-xs hover:bg-white text-gray-500 hover:text-red-500 transition-all shadow-sm cursor-pointer`}
                  title={wishlist.includes(p.id) ? "Remove from Saved" : "Save Item"}
                >
                  <Heart
                    className={`w-3.5 h-3.5 transition-colors ${
                      wishlist.includes(p.id) ? 'fill-red-500 text-red-500' : 'text-gray-600'
                    }`}
                  />
                </button>

                <span className="absolute top-2.5 left-2.5 bg-white/95 backdrop-blur-sm text-[#003224] text-[9px] uppercase tracking-wider font-semibold font-sans py-1 px-2 rounded-full border border-gray-100">
                  {p.brand}
                </span>
                
                {/* Micro info on hover */}
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent p-3 opacity-0 group-hover:opacity-100 transition-opacity flex justify-between items-end">
                  <span className="text-[10px] text-white font-sans flex items-center gap-1">
                    <Eye className="w-3.5 h-3.5" /> Quick View
                  </span>
                  <span className="text-[10px] text-white/90 font-sans italic">{p.occasion}</span>
                </div>
              </div>

              <div className="space-y-1.5 px-1.5">
                <h4 className="font-sans text-xs sm:text-sm font-medium text-gray-900 line-clamp-1 group-hover:text-[#003224] transition-colors">
                  {p.name}
                </h4>
                <div className="flex justify-between items-baseline flex-wrap gap-1">
                  <p className="text-xs sm:text-sm font-bold text-[#003224] font-sans">
                    Rs. {p.price.toLocaleString('en-PK')}
                  </p>
                  {p.deliveryEstimate && (
                    <span className="text-[8px] sm:text-[9px] text-[#004B37] font-semibold bg-[#004B37]/5 px-2 py-0.5 rounded-full font-sans">
                      ⚡ Quick Delivery
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );

  if (isMobile) {
    return (
      <div className="min-h-screen bg-[#FCF9F8] relative overflow-hidden flex flex-col justify-between pb-16">
        {/* Sticky Mobile Filter/Header Area */}
        <div className="p-3 bg-white border-b border-gray-100 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-2">
            <button onClick={onBack} className="p-1.5 text-gray-600 hover:text-black">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider font-sans">Dhaaga AI</span>
              <p className="text-xs text-gray-700 font-sans font-semibold italic truncate max-w-[150px]">
                {storyStep === 0 ? 'Ask Dhaaga anything...' : filters.occasion}
              </p>
            </div>
          </div>

          {/* Quick simulation controls for mobile */}
          <div className="flex gap-1.5 items-center">
            <button
              onClick={onOpenWishlist}
              className="p-1.5 hover:bg-gray-100 rounded-full transition-colors cursor-pointer text-gray-500 hover:text-[#003224] relative flex items-center justify-center mr-1"
              title="Saved Collection"
            >
              <Heart className={`w-5 h-5 ${wishlist.length > 0 ? 'fill-[#003224] text-[#003224]' : ''}`} />
              {wishlist.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-[#003224] text-white text-[8px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center">
                  {wishlist.length}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Scrollable Background Layer (Product Grid) */}
        <div className="flex-1 overflow-y-auto px-4 py-4 pb-24">
          {renderProductGrid("grid-cols-2")}
        </div>

        {/* Bottom Floating Pill indicating Chat State */}
        {!isSheetExpanded && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40">
            <button
              onClick={() => setIsSheetExpanded(true)}
              className="bg-[#003224] text-[#FCF9F8] rounded-full py-2.5 px-6 font-sans font-semibold text-xs tracking-wider flex items-center gap-2 shadow-[0_8px_24px_rgba(0,50,36,0.3)] transition-transform hover:scale-105 cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5 animate-pulse text-amber-300" />
              <span>AI ASSISTANT CHAT ({filteredProducts.length} OUTFITS)</span>
            </button>
          </div>
        )}

        {/* Mobile Overlay Sheet for Chat */}
        <AnimatePresence>
          {isSheetExpanded && (
            <>
              {/* Backdrop */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 0.3 }}
                exit={{ opacity: 0 }}
                onClick={() => setIsSheetExpanded(false)}
                className="fixed inset-0 bg-black/60 z-40"
              />

              {/* Chat Sheet */}
              <motion.div
                initial={{ y: '100%' }}
                animate={{ y: 0 }}
                exit={{ y: '100%' }}
                transition={{ type: 'spring', damping: 25, stiffness: 220 }}
                className="fixed bottom-0 inset-x-0 bg-white rounded-t-2xl z-50 flex flex-col border-t border-gray-150 shadow-[0_-12px_32px_rgba(0,50,36,0.18)]"
                style={{ height: '75%' }}
              >
                {/* Drag Handle & Header */}
                <div className="py-3 px-4 flex flex-col items-center border-b border-gray-100 cursor-pointer" onClick={() => setIsSheetExpanded(false)}>
                  <div className="w-12 h-1.5 bg-gray-300 rounded-full mb-2"></div>
                  <div className="flex justify-between items-center w-full px-2">
                    <span className="text-xs uppercase tracking-widest text-[#003224] font-bold font-sans">Dhaaga AI Chat</span>
                    <span className="text-[10px] bg-emerald-50 text-[#004B37] px-2 py-0.5 rounded-full font-sans font-semibold">Active Assistant</span>
                  </div>
                </div>

                {/* Messages Thread */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] px-4 py-3 rounded-2xl text-xs sm:text-sm leading-relaxed font-sans ${
                          m.sender === 'user'
                            ? 'bg-[#003224] text-white rounded-tr-none'
                            : 'bg-[#FCF9F8] text-[#1C1B1B] rounded-tl-none border border-gray-100'
                        }`}
                      >
                        {m.sender === 'assistant' ? (
                          <div className="space-y-1">
                            <p className="whitespace-pre-line text-[#1C1B1B]">{m.text}</p>
                          </div>
                        ) : (
                          <p className="whitespace-pre-line">{m.text}</p>
                        )}
                        <span className={`block text-[9px] mt-1.5 ${m.sender === 'user' ? 'text-white/60 text-right' : 'text-gray-400 text-left'}`}>
                          {m.timestamp}
                        </span>
                      </div>
                    </div>
                  ))}
                  {isChatLoading && <ChatMessageSkeleton />}
                  <div ref={messagesEndRef} />
                </div>

                {/* Fixed Voice Waveform / Input Bar */}
                <div className="p-3 border-t border-gray-100 bg-white">
                  {isRecording ? (
                    <div className="bg-[#003224]/5 rounded-full py-2.5 px-4 flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                        <span className="text-xs text-gray-600 font-sans">Listening... Speak now</span>
                      </div>
                      {/* Sound Waveform Animation */}
                      <div className="flex gap-1 h-4 items-center">
                        {[1, 2, 3, 4, 5, 4, 3, 2, 4, 6, 2, 1].map((h, i) => (
                          <motion.div
                            key={i}
                            animate={{ height: [4, h * 3, 4] }}
                            transition={{ repeat: Infinity, duration: 0.6, delay: i * 0.05 }}
                            className="w-0.75 bg-[#003224] rounded-full"
                          />
                        ))}
                      </div>
                      <button
                        onClick={handleMicClick}
                        className="bg-[#003224] text-white py-1 px-3.5 rounded-full text-xs font-sans font-medium"
                      >
                        Stop
                      </button>
                    </div>
                  ) : (
                    <form onSubmit={handleSendMessage} className="flex gap-2 items-center">
                      <input
                        type="text"
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        placeholder="Type message..."
                        className="flex-1 bg-[#FCF9F8] border border-gray-200 focus:border-[#003224] focus:ring-0 rounded-full py-2.5 px-4 text-xs font-sans outline-none"
                      />
                      <button
                        type="button"
                        onClick={handleMicClick}
                        className="p-2.5 rounded-full bg-gray-100 text-[#003224] hover:bg-gray-200"
                      >
                        <Mic className="w-4 h-4" />
                      </button>
                      <button
                        type="submit"
                        disabled={!inputText.trim()}
                        className="bg-[#003224] disabled:bg-gray-200 text-white p-2.5 rounded-full transition-colors"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    </form>
                  )}
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    );
  }

  // Desktop Rendering
  return (
    <div className="fixed inset-0 bg-[#FCF9F8] flex flex-col overflow-hidden z-25">
      {/* Mini top nav */}
      <header className="border-b border-gray-100 bg-white/80 backdrop-blur-md px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-1.5 hover:bg-gray-100 rounded-full transition-colors cursor-pointer">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <img src={dhaagaLogo} alt="Dhaaga" className="h-6 w-auto" />
        </div>

        {/* Optional Reset Button */}
        <div className="flex items-center gap-2.5 relative">
          {storyStep > 0 && (
            <button
              onClick={resetAllFilters}
              className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-[10px] font-sans font-bold py-1.5 px-3 rounded-full transition-all cursor-pointer flex items-center gap-1"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Reset Chat</span>
            </button>
          )}
          
          <div className="h-4 w-px bg-gray-200 mx-1.5"></div>

          {/* Saved Collection Header Button */}
          <button
            onClick={onOpenWishlist}
            className="p-1.5 hover:bg-gray-100 rounded-full transition-colors cursor-pointer text-gray-500 hover:text-[#003224] relative flex items-center justify-center"
            title="Saved Collection"
          >
            <Heart className={`w-4.5 h-4.5 ${wishlist.length > 0 ? 'fill-[#003224] text-[#003224]' : ''}`} />
            {wishlist.length > 0 && (
              <span className="absolute -top-0.5 -right-0.5 bg-[#003224] text-white text-[8px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center animate-bounce-subtle">
                {wishlist.length}
              </span>
            )}
          </button>

          <div className="h-4 w-px bg-gray-200 mx-1.5"></div>

          {/* User Profile Button */}
          <div className="relative">
            <button 
              onClick={() => setShowProfile(!showProfile)}
              className={`p-1.5 rounded-full transition-all cursor-pointer flex items-center justify-center ${showProfile ? 'bg-gray-100 text-[#003224]' : 'text-gray-500 hover:text-[#003224]'}`}
              title="My Profile"
            >
              <User className="w-4.5 h-4.5" />
            </button>

            <AnimatePresence>
              {showProfile && (
                <>
                  <div 
                    className="fixed inset-0 z-40" 
                    onClick={() => setShowProfile(false)}
                  />
                  
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
      </header>

      {/* Split Panels */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: Catalog Feed Grid */}
        <div className="flex-1 overflow-y-auto px-6 sm:px-8 py-8">
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex justify-between items-baseline border-b border-gray-100 pb-2">
              <h3 className="font-serif text-xl font-bold text-[#1C1B1B]">Curation Recommendations</h3>
              <p className="text-xs text-gray-400 font-sans uppercase tracking-widest font-bold">Real-time Visual Updates</p>
            </div>
            {renderProductGrid("grid-cols-2 xl:grid-cols-3")}
          </div>
        </div>

        {/* Right Panel: Conversation Bar (420-450px width) */}
        <div className="w-[420px] xl:w-[450px] border-l border-gray-150 bg-white flex flex-col justify-between h-full shadow-lg relative z-10 shrink-0">
          <div className="p-4 border-b border-gray-100 bg-[#FCF9F8] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#004B37] animate-pulse"></span>
              <span className="text-xs font-bold text-[#003224] uppercase tracking-wider font-sans">Active AI Assistant</span>
            </div>
            <span className="text-[10px] text-gray-400 font-sans font-bold">Dhaaga Luxury</span>
          </div>

          {/* Messages Log */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-white">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] px-4 py-3 rounded-2xl text-xs sm:text-sm leading-relaxed font-sans ${
                    m.sender === 'user'
                      ? 'bg-[#003224] text-white rounded-tr-none'
                      : 'bg-[#FCF9F8] text-[#1C1B1B] rounded-tl-none border border-gray-100'
                  }`}
                >
                  {m.sender === 'assistant' ? (
                    <div className="space-y-1">
                      <p className="whitespace-pre-line text-[#1C1B1B]">{m.text}</p>
                    </div>
                  ) : (
                    <p className="whitespace-pre-line">{m.text}</p>
                  )}
                  <span className={`block text-[9px] mt-1.5 ${m.sender === 'user' ? 'text-white/60 text-right' : 'text-gray-400 text-left'}`}>
                    {m.timestamp}
                  </span>
                </div>
              </div>
            ))}
            {isChatLoading && <ChatMessageSkeleton />}
            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Fixed Input bar */}
          <div className="p-4 border-t border-gray-100 bg-white shadow-xs">
            {isRecording && (
              <div className="bg-[#003224]/5 rounded-full py-2.5 px-4 flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping"></span>
                  <span className="text-xs text-gray-600 font-sans font-semibold">Recording voice query...</span>
                </div>
                {/* Sound Waveform Animation */}
                <div className="flex gap-1 h-4 items-center">
                  {[1, 3, 2, 5, 4, 2, 4, 6, 2, 1].map((h, i) => (
                    <motion.div
                      key={i}
                      animate={{ height: [4, h * 3.5, 4] }}
                      transition={{ repeat: Infinity, duration: 0.5, delay: i * 0.04 }}
                      className="w-0.75 bg-[#003224] rounded-full"
                    />
                  ))}
                </div>
                <button
                  onClick={handleMicClick}
                  className="bg-[#003224] text-white py-1 px-3 rounded-full text-xs font-sans font-bold cursor-pointer"
                >
                  Done
                </button>
              </div>
            )}

            <form onSubmit={handleSendMessage} className="flex gap-2 items-center">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Ask Dhaaga AI... e.g. show under 30k"
                className="flex-1 bg-[#FCF9F8] border border-gray-200 focus:border-[#003224] focus:ring-0 rounded-full py-2.5 px-4.5 text-xs sm:text-sm font-sans outline-none transition-all"
              />
              <button
                type="button"
                onClick={handleMicClick}
                title="Search with Voice"
                className={`p-2.5 rounded-full transition-colors cursor-pointer ${isRecording ? 'bg-red-500 text-white' : 'bg-gray-100 text-[#003224] hover:bg-gray-200'}`}
              >
                <Mic className="w-4 h-4 sm:w-4.5 sm:h-4.5" />
              </button>
              <button
                type="submit"
                disabled={!inputText.trim()}
                className="bg-[#003224] disabled:bg-gray-200 text-white p-2.5 rounded-full disabled:cursor-not-allowed transition-colors cursor-pointer"
              >
                <Send className="w-4 h-4 sm:w-4.5 sm:h-4.5" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
