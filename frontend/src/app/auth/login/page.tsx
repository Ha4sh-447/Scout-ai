"use client";

import { motion } from "framer-motion";
import { signIn } from "next-auth/react";
import { Globe } from "lucide-react";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center p-6 bg-grid">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full glass p-8 rounded-3xl border border-slate-800 shadow-2xl"
      >
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center font-bold text-2xl mx-auto mb-4 text-white shadow-lg shadow-blue-600/20">
            S
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Welcome to Scout AI</h1>
          <p className="text-slate-400">Sign in to start your automated job search</p>
        </div>

        <button 
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
          className="w-full flex items-center justify-center gap-3 py-4 px-6 bg-white hover:bg-slate-100 text-black font-bold rounded-xl transition-all active:scale-[0.98] mb-4"
        >
          <img src="https://www.google.com/favicon.ico" className="w-5 h-5" alt="Google" />
          Continue with Google
        </button>

        <div className="text-center">
            <p className="text-[10px] text-slate-500 max-w-[240px] mx-auto uppercase tracking-widest font-bold">
                By continuing, you agree to Scout AI&apos;s Terms of Service and Privacy Policy.
            </p>
        </div>
      </motion.div>
    </div>
  );
}
