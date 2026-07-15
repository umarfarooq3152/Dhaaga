import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Check } from 'lucide-react';
import dhaagaLogo from '../assets/images/dhaaga-logo.png';

interface OnboardingScreenProps {
  onComplete: (userName: string, preferredSize: string, department: 'men' | 'women') => void;
  onSkip: () => void;
}

interface StepData {
  department: 'Menswear' | 'Womenswear' | '';
  size: string;
}

export default function OnboardingScreen({ onComplete, onSkip }: OnboardingScreenProps) {
  const [step, setStep] = useState(0); // 0: Department & Fitting, 1: Personalize Name
  const [userName, setUserName] = useState('');
  
  const [selections, setSelections] = useState<StepData>({
    department: 'Womenswear', // default selected to make it even easier
    size: 'M'
  });

  const totalSteps = 2;

  const handleNext = () => {
    if (step < totalSteps - 1) {
      setStep(step + 1);
    } else {
      onComplete(userName || 'Meera', selections.size, selections.department === 'Menswear' ? 'men' : 'women');
    }
  };

  const selectDepartment = (dept: 'Menswear' | 'Womenswear') => {
    setSelections(prev => ({ ...prev, department: dept }));
  };

  const selectSize = (sz: string) => {
    setSelections(prev => ({ ...prev, size: sz }));
  };

  // Ultra-clean South Asian luxury assets
  const images = {
    // Previous menswear URL (photo-1607990283143-e81e7a2c93ab) 404s — Unsplash
    // removed that photo. Replaced with a verified-working sherwani/turban photo.
    menswear: 'https://images.unsplash.com/photo-1576470189712-50fe3ec06b04?q=80&w=600&auto=format&fit=crop',
    womenswear: 'https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?q=80&w=600&auto=format&fit=crop',
  };

  const slideVariants = {
    enter: { opacity: 0, y: 12 },
    center: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -12 }
  };

  return (
    <div className="min-h-screen bg-[#FAF9F5] flex flex-col justify-between p-6 md:p-12 relative text-[#1C1B1B] font-sans selection:bg-[#003224]/10">
      
      {/* Top Header */}
      <header className="flex justify-between items-center w-full max-w-5xl mx-auto z-10">
        <div className="flex flex-col items-start">
          <img src={dhaagaLogo} alt="Dhaaga" className="h-8 sm:h-10 w-auto" />
        </div>
        <button 
          onClick={onSkip}
          className="text-xs font-bold uppercase tracking-widest text-gray-400 hover:text-black transition-colors cursor-pointer"
        >
          Skip Onboarding
        </button>
      </header>

      {/* Centered Luxury Card Container */}
      <main className="flex-1 flex items-center justify-center py-6">
        <div className="bg-[#FAF9F5] rounded-[16px] border border-gray-200/50 w-full max-w-xl p-6 sm:p-8 flex flex-col justify-between min-h-[420px]">
          
          {/* Step Dash Progress Bar */}
          <div className="flex justify-center gap-1.5 mb-8">
            {Array.from({ length: totalSteps }).map((_, idx) => (
              <div 
                key={idx} 
                className={`h-1 rounded-full transition-all duration-300 ${
                  idx === step 
                    ? 'w-12 bg-[#003224]' 
                    : 'w-6 bg-gray-200'
                }`}
              />
            ))}
          </div>

          {/* Sliding step contents */}
          <div className="flex-1 flex flex-col justify-center">
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.25, ease: 'easeInOut' }}
                className="space-y-6"
              >
                {step === 0 && (
                  <div className="space-y-6">
                    <div className="space-y-1 text-center">
                      <span className="text-[10px] uppercase tracking-widest text-gray-400 font-extrabold">Step 1 of 2 • Department & Fit</span>
                      <h2 className="font-serif text-2xl font-bold tracking-tight text-gray-950">
                        Select your style department.
                      </h2>
                    </div>

                    {/* Department cards selection */}
                    <div className="grid grid-cols-2 gap-4">
                      <div 
                        onClick={() => selectDepartment('Menswear')}
                        className={`group relative aspect-[4/5] rounded-[8px] overflow-hidden cursor-pointer transition-all border-2 ${
                          selections.department === 'Menswear' 
                            ? 'border-[#003224] shadow-md' 
                            : 'border-transparent opacity-85 hover:opacity-100'
                        }`}
                      >
                        <img 
                          src={images.menswear} 
                          alt="Menswear" 
                          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-102"
                          referrerPolicy="no-referrer"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-transparent"></div>
                        <div className="absolute bottom-3 left-3 text-white flex items-center justify-between w-[calc(100%-24px)]">
                          <span className="font-serif text-sm tracking-wide font-bold">Menswear</span>
                          {selections.department === 'Menswear' && (
                            <div className="bg-[#003224] p-0.5 rounded-full text-white">
                              <Check className="w-3.5 h-3.5" />
                            </div>
                          )}
                        </div>
                      </div>

                      <div 
                        onClick={() => selectDepartment('Womenswear')}
                        className={`group relative aspect-[4/5] rounded-[8px] overflow-hidden cursor-pointer transition-all border-2 ${
                          selections.department === 'Womenswear' 
                            ? 'border-[#003224] shadow-md' 
                            : 'border-transparent opacity-85 hover:opacity-100'
                        }`}
                      >
                        <img 
                          src={images.womenswear} 
                          alt="Womenswear" 
                          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-102"
                          referrerPolicy="no-referrer"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-transparent"></div>
                        <div className="absolute bottom-3 left-3 text-white flex items-center justify-between w-[calc(100%-24px)]">
                          <span className="font-serif text-sm tracking-wide font-bold">Womenswear</span>
                          {selections.department === 'Womenswear' && (
                            <div className="bg-[#003224] p-0.5 rounded-full text-white">
                              <Check className="w-3.5 h-3.5" />
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Simple Size selection right below */}
                    <div className="space-y-2 pt-2">
                      <div className="flex justify-between items-center">
                        <label className="text-[10px] uppercase tracking-wider text-gray-500 font-extrabold font-sans">
                          Preferred Size
                        </label>
                        <span className="text-[10px] text-gray-400 font-sans italic">Custom sizing available in chat</span>
                      </div>
                      <div className="flex justify-between gap-1.5 bg-white p-1 rounded-lg border border-gray-200">
                        {['XS', 'S', 'M', 'L', 'XL'].map((sz) => (
                          <button
                            key={sz}
                            type="button"
                            onClick={() => selectSize(sz)}
                            className={`flex-1 py-2 rounded-md text-[11px] font-bold transition-all cursor-pointer ${
                              selections.size === sz
                                ? 'bg-[#003224] text-white shadow-xs'
                                : 'text-gray-600 hover:bg-gray-50'
                            }`}
                          >
                            {sz}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {step === 1 && (
                  <div className="space-y-6 text-center max-w-sm mx-auto py-4">
                    <div className="space-y-1.5">
                      <span className="text-[10px] uppercase tracking-widest text-gray-400 font-extrabold">Step 2 of 2 • Personalize</span>
                      <h2 className="font-serif text-2xl font-bold tracking-tight text-gray-950">
                        What is your name?
                      </h2>
                      <p className="text-xs text-gray-500 font-sans">To configure your automated chat assistant.</p>
                    </div>

                    <div className="pt-2">
                      <input
                        type="text"
                        value={userName}
                        onChange={(e) => setUserName(e.target.value)}
                        placeholder="e.g. Meera, Zain, Zara"
                        className="w-full bg-white border border-gray-200 focus:border-[#003224] focus:ring-1 focus:ring-[#003224]/10 rounded-full py-3 px-5 text-sm font-sans outline-none text-center shadow-xs text-gray-800"
                        autoFocus
                      />
                    </div>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Bottom Solid Dark Green Continue Button */}
          <div className="pt-6">
            <button
              onClick={handleNext}
              disabled={step === 0 && !selections.department}
              className="w-full bg-[#003224] disabled:bg-gray-100 disabled:text-gray-400 text-white hover:bg-[#004B37] rounded-full py-3.5 px-6 font-sans font-semibold text-[11px] tracking-widest transition-all text-center block uppercase shadow-sm cursor-pointer disabled:cursor-not-allowed"
            >
              Continue
            </button>
          </div>

        </div>
      </main>

      {/* Footer Branding */}
      <footer className="text-center text-xs text-gray-400 font-sans tracking-wide max-w-5xl mx-auto w-full">
        © 2026 Dhaaga Pakistan. Premium slow fashion.
      </footer>

    </div>
  );
}
