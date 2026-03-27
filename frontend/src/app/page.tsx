"use client";

import { motion } from "framer-motion";
import { ChevronRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background selection:bg-indigo-500/30 overflow-hidden relative">
      <div className="absolute inset-0 hero-gradient pointer-events-none" />
      
      {/* Navbar - Minimal */}
      <nav className="fixed top-0 w-full z-50 px-6 py-6 bg-background/50 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center font-bold text-black text-sm">S</div>
            <span className="text-xl font-bold tracking-tight">Scout AI</span>
          </div>
          <div className="flex items-center gap-8 text-sm font-medium">
            <Link href="/auth/login" className="text-muted hover:text-white transition-colors">
              Sign In
            </Link>
            <Link href="/auth/login" className="px-6 py-2 bg-white hover:bg-emerald-50 rounded-full text-black font-bold transition-all active:scale-95">
              Launch App
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section - The "Pitch" */}
      <main className="relative pt-48 pb-32">
        <div className="max-w-[1100px] mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="flex flex-col items-center text-center"
          >
            <span className="inline-flex items-center px-4 py-1.5 mb-10 rounded-full bg-emerald-500/10 border border-emerald-500/15 text-emerald-400 text-[10px] font-black tracking-[0.1em] uppercase">
              Autonomous Intelligence
            </span>
            
            <h1 className="text-[52px] md:text-[88px] font-[700] tracking-[-0.04em] mb-10 leading-[0.98] text-balance">
              The only agent that <br />
              truly <span className="text-emerald-500">finds you work.</span>
            </h1>
            
            <p className="text-muted text-lg md:text-xl max-w-[650px] mb-14 leading-relaxed font-medium">
              Scout AI scans the market 24/7, matching your profile against 
              hidden opportunities and sending you perfectly tailored 
              referrals before they hit the mainstream.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center gap-6">
              <Link 
                href="/auth/login" 
                className="group px-10 py-5 bg-emerald-500 text-black hover:bg-emerald-400 rounded-full font-black text-lg transition-all active:scale-95 flex items-center gap-3 shadow-2xl shadow-emerald-500/20"
              >
                Get Started <ChevronRight size={22} className="group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link 
                href="#how" 
                className="px-10 py-5 bg-secondary border-reveal rounded-full font-black text-lg transition-all active:scale-95 flex items-center gap-3 text-slate-400 hover:text-white"
              >
                Watch Demo
              </Link>
            </div>
          </motion.div>

          {/* Simple Feature Preview - Box Spacing Focus */}
          <motion.div 
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-32 grid md:grid-cols-3 gap-6"
          >
            <MinimalCard 
              num="01"
              title="Connect"
              description="Upload your resume and links. Our agent analyzes your profile in seconds."
            />
            <MinimalCard 
              num="02"
              title="Scout"
              description="Your personal agent scans LinkedIn, Wellfound, and hidden boards 24/7."
            />
            <MinimalCard 
              num="03"
              title="Apply"
              description="Get a daily digest with pre-generated outreach. Just click and apply."
            />
          </motion.div>
        </div>
      </main>

      <footer className="py-20 border-t border-white/5 opacity-40">
        <div className="max-w-7xl mx-auto px-6 flex justify-between items-center text-xs font-medium uppercase tracking-widest">
            <span>&copy; 2026 Scout AI Platform</span>
            <div className="flex gap-8">
                <a href="#" className="hover:text-indigo-400">GitHub</a>
                <a href="#" className="hover:text-indigo-400">Privacy</a>
            </div>
        </div>
      </footer>
    </div>
  );
}

function MinimalCard({ num, title, description }: { num: string, title: string, description: string }) {
  return (
    <div className="group p-10 rounded-[28px] bg-secondary border-reveal hover:bg-emerald-500/[0.02] transition-colors">
      <div className="text-[12px] font-black text-emerald-500 mb-8 tracking-widest opacity-40 group-hover:opacity-100 transition-opacity uppercase">{num}</div>
      <h3 className="text-2xl font-bold mb-5 flex items-center gap-3">
        {title} <ArrowUpRight size={20} className="opacity-0 group-hover:opacity-100 -translate-y-1 translate-x-1 transition-all" />
      </h3>
      <p className="text-muted text-base leading-relaxed font-medium">{description}</p>
    </div>
  );
}
