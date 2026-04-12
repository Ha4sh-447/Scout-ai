"use client";

import { motion } from "framer-motion";
import { ChevronRight, Search, FileText, Globe, Mail, Zap, BarChart3, Shield, Clock, CheckCircle, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background selection:bg-emerald-500/30 overflow-hidden relative font-sans">
      <div className="absolute inset-0 hero-gradient pointer-events-none" />

      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 px-6 py-5 bg-background/60 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center font-black text-black text-sm">S</div>
            <span className="text-xl font-bold tracking-tight">Scout AI</span>
          </div>
          <div className="hidden md:flex items-center gap-10 text-sm font-medium text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how" className="hover:text-white transition-colors">How It Works</a>
          </div>
          <div className="flex items-center gap-3 text-sm font-medium">
            <Link href="/auth/login" className="text-slate-400 hover:text-white transition-colors px-4 py-2">
              Sign In
            </Link>
            <Link href="/auth/login" className="px-5 py-2 bg-emerald-500 hover:bg-emerald-400 rounded-lg text-black font-black transition-all active:scale-95">
              Get Started →
            </Link>
          </div>
        </div>
      </nav>

      <main className="relative">
        {/* Hero */}
        <section className="pt-44 pb-28 px-6">
          <div className="max-w-5xl mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: "easeOut" }}
            >
              <span className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-black tracking-[0.12em] uppercase">
                <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                AI-Powered Job Agent
              </span>

              <h1 className="text-5xl md:text-[80px] font-black tracking-[-0.04em] mb-8 leading-[1.0] text-balance">
                Your personal recruiter,<br />
                <span className="text-emerald-400">running 24/7.</span>
              </h1>

              <p className="text-slate-400 text-lg md:text-xl max-w-[600px] mx-auto mb-10 leading-relaxed">
                Scout AI scans LinkedIn, Wellfound, and more — matching your resume against live listings, ranking them, 
                and sending you a tailored job digest every day.
              </p>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/auth/login"
                  className="group px-8 py-4 bg-emerald-500 text-black hover:bg-emerald-400 rounded-xl font-black text-base transition-all active:scale-95 flex items-center gap-2 shadow-2xl shadow-emerald-500/20"
                >
                  Start Scouting Free <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </Link>
                <a
                  href="#how"
                  className="px-8 py-4 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-xl font-semibold text-slate-300 text-base transition-all active:scale-95"
                >
                  See how it works
                </a>
              </div>
            </motion.div>

            {/* Social proof strip */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="mt-16 flex items-center justify-center gap-8 text-slate-600 text-xs font-semibold uppercase tracking-widest flex-wrap"
            >
              <span className="flex items-center gap-2"><CheckCircle size={12} className="text-emerald-500" /> No credit card required</span>
              <span className="flex items-center gap-2"><CheckCircle size={12} className="text-emerald-500" /> Runs on free-tier LLMs</span>
              <span className="flex items-center gap-2"><CheckCircle size={12} className="text-emerald-500" /> Fully open-source</span>
            </motion.div>
          </div>
        </section>

        {/* Features Grid */}
        <section id="features" className="py-28 px-6">
          <div className="max-w-7xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-center mb-20"
            >
              <span className="inline-flex items-center px-4 py-1.5 mb-5 rounded-full bg-emerald-500/10 border border-emerald-500/15 text-emerald-400 text-[11px] font-black tracking-[0.12em] uppercase">
                Features
              </span>
              <h2 className="text-4xl md:text-5xl font-black tracking-[-0.04em] mb-5 text-balance">
                Everything you need to land faster
              </h2>
              <p className="text-slate-400 text-lg max-w-[560px] mx-auto">
                A complete, automated pipeline from job discovery to personalized outreach.
              </p>
            </motion.div>

            <div className="grid md:grid-cols-3 gap-5">
              {FEATURES.map((f, i) => (
                <motion.div
                  key={f.title}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  className={`group relative rounded-2xl p-7 border transition-all cursor-default ${f.highlight
                    ? "bg-emerald-500/10 border-emerald-500/30 hover:border-emerald-400/50"
                    : "bg-slate-900/60 border-slate-800 hover:border-slate-600"
                  }`}
                >
                  {f.highlight && (
                    <span className="absolute top-4 right-4 px-2 py-0.5 bg-emerald-500 text-black text-[9px] font-black rounded-full uppercase tracking-widest">
                      Core
                    </span>
                  )}
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-5 ${f.highlight ? "bg-emerald-500/20" : "bg-slate-800"}`}>
                    <f.icon size={20} className={f.highlight ? "text-emerald-400" : "text-slate-400"} />
                  </div>
                  <h3 className="text-white font-bold text-lg mb-2">{f.title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section id="how" className="py-28 px-6 border-t border-white/5">
          <div className="max-w-4xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-center mb-20"
            >
              <span className="inline-flex items-center px-4 py-1.5 mb-5 rounded-full bg-emerald-500/10 border border-emerald-500/15 text-emerald-400 text-[11px] font-black tracking-[0.12em] uppercase">
                How It Works
              </span>
              <h2 className="text-4xl md:text-5xl font-black tracking-[-0.04em] mb-5 text-balance">
                Set it up once. Let it run.
              </h2>
              <p className="text-slate-400 text-lg max-w-[520px] mx-auto">
                A 3-step setup that takes under 10 minutes — then Scout runs in the background while you focus on what matters.
              </p>
            </motion.div>

            <div className="space-y-6">
              {HOW_STEPS.map((step, i) => (
                <motion.div
                  key={step.title}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="flex gap-6 items-start p-6 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-colors group"
                >
                  <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-xl font-black text-emerald-400">
                    {i + 1}
                  </div>
                  <div className="flex-1 pt-0.5">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-white font-bold text-lg">{step.title}</h3>
                      <ArrowRight size={14} className="text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <p className="text-slate-400 text-sm leading-relaxed">{step.desc}</p>
                    {step.tip && (
                      <p className="text-emerald-400/70 text-xs mt-2 font-semibold">💡 {step.tip}</p>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-28 px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="max-w-3xl mx-auto text-center bg-gradient-to-br from-emerald-500/10 via-slate-900 to-slate-900 border border-emerald-500/20 rounded-3xl p-14"
          >
            <h2 className="text-4xl md:text-5xl font-black tracking-[-0.04em] mb-5 text-balance">
              Stop searching. Start<br /><span className="text-emerald-400">getting found.</span>
            </h2>
            <p className="text-slate-400 text-lg mb-10 max-w-lg mx-auto">
              Upload your resume, add some links, and let Scout do the rest. Your next job might already be waiting.
            </p>
            <Link
              href="/auth/login"
              className="inline-flex items-center gap-2 px-10 py-5 bg-emerald-500 hover:bg-emerald-400 text-black font-black text-lg rounded-xl transition-all active:scale-95 shadow-2xl shadow-emerald-500/20"
            >
              Launch Scout AI <ChevronRight size={20} />
            </Link>
          </motion.div>
        </section>
      </main>

      <footer className="py-10 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4 text-xs font-medium text-slate-600 uppercase tracking-widest">
          <span>© 2026 Scout AI Platform</span>
          <div className="flex gap-8">
            <a href="#" className="hover:text-slate-400 transition-colors">GitHub</a>
            <a href="#" className="hover:text-slate-400 transition-colors">Privacy</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

const FEATURES = [
  {
    icon: Search,
    title: "Multi-Platform Scraping",
    desc: "Automatically scrapes LinkedIn, Indeed, Wellfound, Glassdoor, and Reddit based on your saved search URLs.",
    highlight: true,
  },
  {
    icon: FileText,
    title: "Resume Matching",
    desc: "Uses vector embeddings to semantically match your resume against every job description for a true fit score.",
    highlight: true,
  },
  {
    icon: BarChart3,
    title: "AI-Powered Ranking",
    desc: "Jobs are ranked by a weighted score combining match quality, recency, and source quality.",
    highlight: true,
  },
  {
    icon: Mail,
    title: "Email Digests",
    desc: "Get a beautifully formatted HTML email with your top matches and ready-to-send outreach drafts.",
    highlight: false,
  },
  {
    icon: Zap,
    title: "Outreach Drafting",
    desc: "Generates personalized LinkedIn messages and cold emails for each matched job, powered by LLMs.",
    highlight: false,
  },
  {
    icon: Globe,
    title: "Authenticated Scraping",
    desc: "Save your LinkedIn/Wellfound browser session to unlock personalized job feeds and bypass guest-mode limits.",
    highlight: false,
  },
  {
    icon: Clock,
    title: "Scheduled Runs",
    desc: "Set up recurring pipeline runs on any interval — hourly, daily, or weekly.",
    highlight: false,
  },
  {
    icon: Shield,
    title: "Deduplication",
    desc: "Smart content hashing ensures you never see the same job twice, even across multiple pipeline runs.",
    highlight: false,
  },
  {
    icon: FileText,
    title: "Multi-Resume Support",
    desc: "Upload multiple resumes for different roles. Scout picks the best match automatically.",
    highlight: false,
  },
];

const HOW_STEPS = [
  {
    title: "Upload your resume",
    desc: "Go to 'My Resumes' and upload a PDF. Scout will extract your skills, experience, and goals using AI.",
    tip: "Upload one resume per target role for best results.",
  },
  {
    title: "Add your search URLs",
    desc: "Paste LinkedIn, Indeed, or Wellfound search URLs into 'Saved Search URLs'. These are the pages Scout will scan on every run.",
    tip: "Use filtered search URLs (location, experience) for more precise results.",
  },
  {
    title: "Configure your preferences",
    desc: "Set your target location, experience level, notification email, and search queries in Preferences.",
    tip: "Add your LinkedIn li_at cookie in Preferences for authenticated results.",
  },
  {
    title: "Trigger your first scan",
    desc: "Click 'New Agent Run' from the header or 'Trigger Scan' from the Overview. The pipeline runs in the background.",
    tip: "Enable the scheduler to have scans run automatically on a schedule.",
  },
  {
    title: "Review your matches",
    desc: "Check 'Matched Jobs' for your ranked results. Each job shows a match score, skills alignment, and outreach drafts.",
    tip: "Check 'Pipeline History' to monitor run status and see how many jobs were found.",
  },
];
