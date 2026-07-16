import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X } from 'lucide-react';
import { ApiError } from '../api/client';
import Loader from './Loader';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: (email: string, password: string) => Promise<void>;
  onSignup: (email: string, password: string, name: string) => Promise<void>;
}

export default function AuthModal({ isOpen, onClose, onLogin, onSignup }: AuthModalProps) {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const resetAndClose = () => {
    setEmail('');
    setPassword('');
    setName('');
    setError(null);
    setIsSubmitting(false);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (mode === 'login') {
        await onLogin(email, password);
      } else {
        await onSignup(email, password, name);
      }
      resetAndClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Something went wrong. Please try again.');
      }
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            exit={{ opacity: 0 }}
            onClick={resetAndClose}
            className="fixed inset-0 bg-black/60 z-100 backdrop-blur-xs"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-100 w-[90vw] max-w-sm bg-white rounded-2xl shadow-2xl p-6 font-sans"
          >
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-serif text-xl font-bold text-[#003224]">
                {mode === 'login' ? 'Log In' : 'Create Account'}
              </h2>
              <button
                onClick={resetAndClose}
                className="text-gray-400 hover:text-black transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3.5">
              {mode === 'signup' && (
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-1.5">
                    Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#003224] transition-colors"
                    placeholder="Your name"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#003224] transition-colors"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  required
                  minLength={mode === 'signup' ? 8 : undefined}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#003224] transition-colors"
                  placeholder={mode === 'signup' ? 'At least 8 characters' : 'Your password'}
                />
              </div>

              {error && <p className="text-xs text-red-600">{error}</p>}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-[#003224] hover:bg-[#004B37] text-white text-sm font-bold py-2.5 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {isSubmitting && <Loader size="16" color="#ffffff" />}
                {mode === 'login' ? 'Log In' : 'Create Account'}
              </button>
            </form>

            <p className="text-center text-xs text-gray-500 mt-4">
              {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
              <button
                onClick={() => {
                  setMode(mode === 'login' ? 'signup' : 'login');
                  setError(null);
                }}
                className="text-[#003224] font-bold hover:underline cursor-pointer"
              >
                {mode === 'login' ? 'Sign up' : 'Log in'}
              </button>
            </p>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
