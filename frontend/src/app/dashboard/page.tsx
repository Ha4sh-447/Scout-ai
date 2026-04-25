"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, FileText, Globe, MapPin, 
  Settings, LogOut, Bell, Plus, 
  ExternalLink, ChevronRight, Filter,
  Layers, CheckCircle, Clock, Mail, Briefcase,
  Loader2, X, AlertTriangle, Square, Activity, RotateCw,
  Award, Building2, Sparkles, DollarSign, Target, User,
  Terminal, Copy
} from "lucide-react";
import { fetchJobs, fetchSettings, triggerPipeline, scrapeLinks, cancelPipeline, updateSettings, fetchRuns, uploadResume, saveSearchLinks, getSearchLinks, deleteSearchLink, triggerBrowserAuthentication, getAuthenticationStatus, clearBrowserSession, fetchResumes, updateLinkedinCookie } from "@/lib/api";
import Link from "next/link";
import { signOut } from "next-auth/react";
import PipelineHistory from "@/components/PipelineHistory";

export default function Dashboard() {
  const { data: session, status } = useSession();
  const [activeTab, setActiveTab] = useState("overview");
  const [isSearchExpanded, setIsSearchExpanded] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [liAtCookie, setLiAtCookie] = useState("");
  const [isTriggerDialogOpen, setIsTriggerDialogOpen] = useState(false);
  
  const [searchQuery, setSearchQuery] = useState("");
  const [location, setLocation] = useState("");
  const [experience, setExperience] = useState("0");
  const [customUrls, setCustomUrls] = useState("");

  const [jobs, setJobs] = useState<any[]>([]);
  const [stats, setStats] = useState({ notifications: 0, jobsFound: 0 });
  const [rawSettings, setRawSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [tempSearchQueries, setTempSearchQueries] = useState("");
  const [runs, setRuns] = useState<any[]>([]);
  const [lastRefresh, setLastRefresh] = useState<number>(Date.now());
  const [uploading, setUploading] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [uploadedResumes, setUploadedResumes] = useState<any[]>([]);
  const [savedSearchLinks, setSavedSearchLinks] = useState<any[]>([]);
  const [showSaveLinksPrompt, setShowSaveLinksPrompt] = useState(false);
  const [authStatus, setAuthStatus] = useState<any>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["linkedin", "wellfound", "indeed"]);
  
  const [enableScheduler, setEnableScheduler] = useState(false);
  const [schedulerInterval, setSchedulerInterval] = useState(3);

  useEffect(() => {
    if (status === "authenticated" && session?.user) {
      loadData();
      
      const pollInterval = setInterval(async () => {
        const token = (session as any)?.user?.accessToken || "";
        try {
          const runsData = await fetchRuns(token);
          setRuns(runsData);
          
          const wasActive = activeRunId !== null;
          const activeRun = runsData.find((r: any) => r.status === "running" || r.status === "pending");
          const isNowActive = activeRun !== undefined;
          
          if (wasActive && !isNowActive) {
            await loadData(true);
          } else {
            const jobsData = await fetchJobs(token);
            setJobs(jobsData);
            setStats({
              notifications: runsData.length,
              jobsFound: jobsData.length
            });
          }
          
          setActiveRunId(activeRun?.id || null);
        } catch (error) {
          console.error("Polling failed:", error);
        }
      }, 10000); // Poll every 10 seconds to detect changes quickly
      
      return () => clearInterval(pollInterval);
    }
  }, [status, session?.user?.email]);

  const loadData = async (silent = false) => {
    const token = (session as any)?.user?.accessToken || "";
    try {
      if (!silent) setLoading(true);
      const [jobsData, settingsData, runsData, linksData, statusData, resumesData] = await Promise.all([
        fetchJobs(token),
        fetchSettings(token),
        fetchRuns(token),
        getSearchLinks(token).catch(() => []), // Gracefully handle if endpoint not ready
        getAuthenticationStatus(token).catch(() => null), // Gracefully handle if endpoint not ready
        fetchResumes(token).catch(() => []) // Gracefully handle if endpoint not ready
      ]);
      console.log("Fetched settings data:", settingsData);
      setJobs(jobsData);
      setRuns(runsData);
      setRawSettings(settingsData);
      setSavedSearchLinks(linksData);
      setAuthStatus(statusData);
      setUploadedResumes(resumesData);
      if (linksData.length > 0) {
        setCustomUrls(prev => prev.trim() ? prev : linksData.map((l: any) => l.url).join('\n'));
      }
      setStats({
        notifications: runsData.length,
        jobsFound: jobsData.length
      });
      setLocation(settingsData.location || "India");
      setExperience(settingsData.job_experience || "0");
      
      const active = runsData.find((r: any) => r.status === "running" || r.status === "pending");
      if (active) setActiveRunId(active.id);
      else setActiveRunId(null);
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const handleTrigger = async () => {
    const token = (session as any)?.user?.accessToken || "";
    
    if (uploadedResumes.length === 0) {
      alert("Please upload at least one resume before starting a pipeline.");
      setActiveTab("resumes");
      return;
    }
    
    try {
      setTriggering(true);
      const urlList = customUrls.split("\n").map(u => u.trim()).filter(u => u.length > 0);
      
      console.log("[Dashboard] handleTrigger START");
      console.log("[Dashboard] enableScheduler state:", enableScheduler);
      console.log("[Dashboard] schedulerInterval state:", schedulerInterval);
      console.log("[Dashboard] searchQuery:", searchQuery);
      console.log("[Dashboard] location:", location);
      console.log("[Dashboard] experience:", experience);
      
      if (urlList.length > 0) {
        const linkedinOrWellfoundUrls = urlList.filter(u => 
          u.toLowerCase().includes("linkedin") || u.toLowerCase().includes("wellfound")
        );
        if (linkedinOrWellfoundUrls.length > 0) {
          try {
            await saveSearchLinks(linkedinOrWellfoundUrls, token);
          } catch (err) {
            console.warn("Could not save search links:", err);
          }
        }
      }
      
      let res;
      if (searchQuery.trim().startsWith("http") || urlList.length > 0) {
        const links = searchQuery.trim().startsWith("http") ? [searchQuery.trim(), ...urlList] : urlList;
        res = await scrapeLinks(links, token, {
          is_scheduled: enableScheduler,
          interval_hours: schedulerInterval
        });
        alert(`Scraper started for the provided links!${enableScheduler ? ` Scheduled every ${schedulerInterval}h` : ""}`);
      } else {
        console.log("[Dashboard] Calling triggerPipeline with:");
        console.log("  - queries:", [searchQuery]);
        console.log("  - location:", location || undefined);
        console.log("  - experience:", experience || undefined);
        console.log("  - is_scheduled:", enableScheduler);
        console.log("  - interval_hours:", schedulerInterval);
        
        res = await triggerPipeline({
          queries: searchQuery ? [searchQuery] : undefined,
          location: location || undefined,
          experience: experience || undefined,
        }, {
          is_scheduled: enableScheduler,
          interval_hours: schedulerInterval
        }, token);
        
        console.log("[Dashboard] triggerPipeline response:", res);
        alert(`Custom agent run triggered!${enableScheduler ? ` Scheduled every ${schedulerInterval}h` : ""}`);
      }
      
      if (res?.run_id) setActiveRunId(res.run_id);
      setIsSearchExpanded(false);
      setIsTriggerDialogOpen(false);
      
      console.log("[Dashboard] Resetting enableScheduler to false and interval to 3");
      setEnableScheduler(false);
      setSchedulerInterval(3);
      
      loadData(true); // Silent refresh after trigger
    } catch (error) {
      alert("Failed to start agent: " + (error as Error).message);
    } finally {
      setTriggering(false);
    }
  };

  const handleOpenSettings = () => {
    if (rawSettings?.search_queries) {
      setTempSearchQueries(rawSettings.search_queries.join(", "));
    }
    setLiAtCookie(""); // Ensure password field is cleared
    setIsSettingsOpen(true);
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = (session as any)?.user?.accessToken || "";
    const updatedSettings = {
      ...rawSettings,
      search_queries: tempSearchQueries.split(",").map(q => q.trim()).filter(q => q.length > 0)
    };
    try {
      await updateSettings(updatedSettings, token);
      setRawSettings(updatedSettings);
      
      if (liAtCookie.trim() !== "") {
        try {
          await updateLinkedinCookie(liAtCookie.trim(), token);
          setLiAtCookie(""); // Clear after saving
        } catch(err) {
          console.error("Failed to update linkedin cookie", err);
          alert("Settings saved, but failed to link LinkedIn session.");
        }
      }
      
      alert("Settings & Session saved!");
      setIsSettingsOpen(false);
      loadData(true); // Silent refresh
    } catch (error) {
      alert("Failed to save settings.");
    }
  };

  if (status === "loading" || (loading && status === "authenticated" && jobs.length === 0)) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0c]">
        <Loader2 className="animate-spin text-emerald-500" size={48} />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#0a0a0c] text-slate-200">
      <aside className="w-64 border-r border-slate-900 flex flex-col glass z-30">
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center font-bold text-black">S</div>
          <span className="text-xl font-bold tracking-tight text-white">Scout AI</span>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-1">
          <SidebarItem icon={<Layers size={20} />} label="Overview" active={activeTab === "overview"} onClick={() => setActiveTab("overview")} />
          <SidebarItem icon={<BriefcaseIcon size={20} />} label="Matched Jobs" active={activeTab === "jobs"} onClick={() => setActiveTab("jobs")} />
          <SidebarItem icon={<Activity size={20} />} label="Pipeline History" active={activeTab === "history"} onClick={() => setActiveTab("history")} />
          <SidebarItem icon={<FileText size={20} />} label="My Resumes" active={activeTab === "resumes"} onClick={() => setActiveTab("resumes")} />
          <SidebarItem icon={<Globe size={20} />} label="Saved Search URLs" active={activeTab === "savedlinks"} onClick={() => setActiveTab("savedlinks")} />
          <SidebarItem icon={<Activity size={20} />} label="Browser Sync" active={activeTab === "authenticator"} onClick={() => setActiveTab("authenticator")} />
          <div className="pt-8 pb-2 px-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">Settings</div>
          <SidebarItem icon={<Settings size={20} />} label="Preferences" onClick={handleOpenSettings} />
        </nav>

        <div className="p-4 mt-auto border-t border-slate-900">
          <div className="flex items-center gap-3 p-2 rounded-xl hover:bg-slate-900 transition-colors cursor-pointer group">
            <div className="w-8 h-8 bg-slate-800 rounded-full flex items-center justify-center text-xs font-bold text-slate-400 group-hover:bg-slate-700 transition-colors">
              {session?.user?.name?.substring(0, 2).toUpperCase() || "US"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{session?.user?.name || "User Account"}</p>
              <p className="text-xs text-slate-500 truncate">Pro Plan</p>
            </div>
            <button onClick={() => signOut({ callbackUrl: "/" })}>
              <LogOut size={16} className="text-slate-500 hover:text-red-400" />
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto relative">
        {!(session as any)?.user?.accessToken && status === "authenticated" && (
          <div className="bg-amber-500/10 border-b border-amber-500/20 p-2 text-center text-[10px] font-bold text-amber-500 flex items-center justify-center gap-2">
            <AlertTriangle size={12} /> Authentication token missing. Please sign out and sign in again to enable scouting.
          </div>
        )}
        <header className="sticky top-0 h-16 border-b border-slate-900 glass z-20 px-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-white">
              {activeTab === "jobs" ? "Matched Listings" : activeTab === "history" ? "Pipeline History" : activeTab === "resumes" ? "My Resumes" : activeTab === "savedlinks" ? "Saved Search URLs" : activeTab === "authenticator" ? "Browser Sync" : "Overview"}
            </h2>
          </div>
          
          <div className="flex items-center gap-4">
            <button 
              onClick={async () => {
                const token = (session as any)?.user?.accessToken || "";
                if (activeTab === "jobs") {
                  const jobsData = await fetchJobs(token);
                  setJobs(jobsData);
                } else if (activeTab === "history") {
                  const runsData = await fetchRuns(token);
                  setRuns(runsData);
                }
              }}
              className="p-2 text-slate-400 hover:text-white transition-colors"
              title="Refresh current tab"
            >
              <RotateCw size={20} />
            </button>
            <button className="p-2 text-slate-400 hover:text-white transition-colors relative">
               <Bell size={20} />
               <span className="absolute top-2 right-2 w-2 h-2 bg-emerald-500 rounded-full border-2 border-[#0a0a0c]" />
            </button>

            <AnimatePresence mode="wait">
              {isSearchExpanded ? (
                <motion.div
                  key="search-expanded"
                  initial={{ width: 0, opacity: 0, x: 20 }}
                  animate={{ width: 600, opacity: 1, x: 0 }}
                  exit={{ width: 0, opacity: 0, x: 20 }}
                  className="flex flex-col bg-slate-900 rounded-2xl border border-slate-800 p-4 shadow-2xl z-50 absolute top-4 right-8 overflow-hidden"
                >
                  <div className="flex items-center gap-3 mb-4">
                    <Search size={18} className="text-emerald-500" />
                    <input 
                      type="text" 
                      autoFocus
                      placeholder="Role (e.g. AI Engineer) or Job Link..." 
                      className="bg-transparent border-none outline-none flex-1 text-white text-base font-medium placeholder:text-slate-600"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                    <button onClick={() => setIsSearchExpanded(false)} className="text-slate-500 hover:text-white"><X size={20} /></button>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-2 mb-2">
                         <MapPin size={12} /> Target Location
                      </label>
                      <input 
                        type="text" 
                        placeholder="Remote, SF, India..." 
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs outline-none focus:border-emerald-500 transition-colors"
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-2 mb-2">
                         <BriefcaseIcon size={12} className="text-slate-500" /> Experience
                      </label>
                      <select 
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs outline-none focus:border-emerald-500 appearance-none transition-colors"
                        value={experience}
                        onChange={(e) => setExperience(e.target.value)}
                      >
                         <option value="0">Entry (0-2y)</option>
                         <option value="2">Mid (2-5y)</option>
                         <option value="5">Senior (5+y)</option>
                      </select>
                    </div>
                  </div>

                  <div className="mb-4">
                    <div className="flex justify-between items-end mb-2">
                      <label className="text-[10px] font-bold text-emerald-500 uppercase flex items-center gap-2">
                         <ExternalLink size={12} /> Scrape specific URLs (One per line)
                      </label>
                      {savedSearchLinks.length > 0 && (
                        <button 
                          type="button"
                          onClick={() => setCustomUrls(savedSearchLinks.map((l: any) => l.url).join('\n'))}
                          className="text-[10px] font-bold pb-0 text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors underline decoration-blue-500/30"
                        >
                          Autofill Saved Links ({savedSearchLinks.length})
                        </button>
                      )}
                    </div>
                    <textarea 
                      placeholder="Paste LinkedIn, Indeed, or other job URLs here..." 
                      rows={3}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs outline-none focus:border-emerald-500 transition-colors resize-none text-slate-200"
                      value={customUrls}
                      onChange={(e) => setCustomUrls(e.target.value)}
                    />
                  </div>

                  <div className="flex justify-end pt-2 border-t border-slate-800">
                    <button 
                      onClick={() => setIsTriggerDialogOpen(true)}
                      disabled={triggering || (!searchQuery.trim() && !customUrls.trim())}
                      className="px-6 py-2 bg-emerald-500 text-black font-black rounded-lg text-sm hover:bg-emerald-400 transition-colors disabled:opacity-50"
                    >
                      {triggering ? "Launching Agent..." : "Start Scouting"}
                    </button>
                  </div>
                </motion.div>
              ) : (
                <motion.button
                  key="search-collapsed"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => {
                    setIsSearchExpanded(true);
                  }}
                  className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 rounded-lg text-sm font-bold text-black transition-all active:scale-95 shadow-lg shadow-emerald-500/10"
                >
                  <Plus size={18} /> New Agent Run
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </header>

        <div className="p-8">
           <div className="grid grid-cols-4 gap-6 mb-12">
              <StatCard label="Jobs Found" value={stats.jobsFound.toString()} icon={<BriefcaseIcon size={20} className="text-emerald-500" />} />
              <StatCard label="Emails Sent" value={runs.filter((r: any) => r.emails_sent).length.toString()} icon={<Mail className="text-blue-500" />} />
              <StatCard label="Verified Matches" value={jobs.length.toString()} icon={<CheckCircle className="text-purple-500" />} />
              <div className="glass p-5 rounded-2xl border border-slate-900 border-t-slate-800/10 relative overflow-hidden group">
                 <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-slate-900 rounded-lg">
                      <Clock size={20} className={triggering || activeRunId ? "text-emerald-500 animate-pulse" : "text-amber-500"} />
                    </div>
                    <span className="text-[10px] font-black text-slate-500 tracking-widest uppercase">Agent Status</span>
                 </div>
                 <div className="flex items-center justify-between">
                    <p className="text-2xl font-bold text-white">{triggering || activeRunId ? "Running" : "Idle"}</p>
                    {activeRunId && (
                      <button 
                        onClick={() => setActiveTab("history")}
                        className="p-1 px-3 bg-blue-500/10 text-blue-500 hover:bg-blue-500 hover:text-white rounded-md text-[10px] font-black border border-blue-500/20 transition-all flex items-center gap-1"
                      >
                         View Pipeline
                      </button>
                    )}
                 </div>
              </div>
           </div>


           {activeTab === "overview" ? (
             <div className="p-8 space-y-8">

               <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-500/10 via-slate-900 to-slate-900 border border-emerald-500/20 p-8">
                 <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[10px] font-black text-emerald-400 uppercase tracking-widest mb-4 inline-block">
                   <span className="inline-block w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                   {" "} Scout AI
                 </span>
                 <h2 className="text-2xl font-black text-white mb-2">
                   Welcome, {session?.user?.name?.split(" ")[0] || "Scout"} 👋
                 </h2>
                 <p className="text-slate-400 text-sm max-w-xl">
                   Follow the setup checklist below to get the most out of Scout AI. Once configured, your agent will run automatically and deliver curated job matches to your inbox.
                 </p>
               </div>

               <div className="glass rounded-3xl border border-slate-800 overflow-hidden">
                 <div className="px-8 py-5 border-b border-slate-800 flex items-center justify-between">
                   <h3 className="text-white font-bold text-lg">Setup Checklist</h3>
                   <span className="text-xs text-slate-500 font-semibold">
                     {[uploadedResumes.length > 0, savedSearchLinks.length > 0, authStatus?.authenticated, !!rawSettings?.notification_email].filter(Boolean).length} / 4 complete
                   </span>
                 </div>
                 <div className="p-6 space-y-4">
                   {[
                     {
                       done: uploadedResumes.length > 0,
                       step: "01",
                       title: "Upload a Resume",
                       desc: "Scout uses your resume to semantically match against job descriptions. Upload a PDF under 'My Resumes'.",
                       tip: "Upload one resume per target role for best results (e.g. SWE vs ML).",
                       action: { label: "Go to Resumes →", onClick: () => setActiveTab("resumes") },
                     },
                     {
                       done: savedSearchLinks.length > 0,
                       step: "02",
                       title: "Add Search URLs",
                       desc: "Paste filtered LinkedIn, Wellfound, or Indeed search URLs. Scout will scrape these on every run.",
                       tip: 'Use pre-filtered URLs with location/experience — e.g. linkedin.com/jobs/search/?keywords=AI+Engineer',
                       action: { label: "Manage URLs →", onClick: () => setActiveTab("savedlinks") },
                     },
                     {
                       done: authStatus?.authenticated,
                       step: "03",
                       title: "Authenticate LinkedIn / Wellfound",
                       desc: "Save your browser session cookie to access personalized job feeds and bypass guest rate limits.",
                       tip: "Open Preferences and paste your li_at cookie. One-time setup.",
                       action: { label: "Open Preferences →", onClick: handleOpenSettings },
                     },
                     {
                       done: !!rawSettings?.notification_email,
                       step: "04",
                       title: "Set Notification Email",
                       desc: "Get a formatted HTML digest daily with your top matches and ready-to-send outreach messages.",
                       tip: "Configure Gmail SMTP or Resend in your .env file to enable email delivery.",
                       action: { label: "Open Preferences →", onClick: handleOpenSettings },
                     },
                   ].map((item) => (
                     <div
                       key={item.step}
                       className={`flex gap-5 p-5 rounded-2xl border transition-colors ${
                         item.done
                           ? "bg-emerald-500/5 border-emerald-500/20"
                           : "bg-slate-900/50 border-slate-700/60 hover:border-slate-600"
                       }`}
                     >
                       <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-black flex-shrink-0 ${
                         item.done ? "bg-emerald-500 text-black" : "bg-slate-800 text-slate-400"
                       }`}>
                         {item.done ? <CheckCircle size={18} /> : item.step}
                       </div>
                       <div className="flex-1 min-w-0">
                         <div className="flex items-start justify-between gap-4 flex-wrap">
                           <div>
                             <p className={`font-bold text-sm mb-1 ${item.done ? "text-emerald-300" : "text-white"}`}>
                               {item.title} {item.done && <span className="text-emerald-500 font-black">✓</span>}
                             </p>
                             <p className="text-slate-400 text-xs leading-relaxed mb-1">{item.desc}</p>
                             <p className="text-slate-600 text-[11px]">💡 {item.tip}</p>
                           </div>
                           {!item.done && (
                             <button
                               onClick={item.action.onClick}
                               className="text-xs font-bold text-emerald-400 hover:text-emerald-300 transition-colors whitespace-nowrap flex-shrink-0 mt-0.5"
                             >
                               {item.action.label}
                             </button>
                           )}
                         </div>
                       </div>
                     </div>
                   ))}
                 </div>
               </div>

               <div>
                 <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4 px-1">All-time Pipeline Stats</h3>
                 <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                   <div className="glass p-5 rounded-2xl border border-slate-800">
                     <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Discovered</p>
                     <p className="text-2xl font-bold text-white">{runs.reduce((sum: number, r: any) => sum + (r.jobs_found || 0), 0)}</p>
                     <p className="text-emerald-400 text-[10px] mt-1">Across {runs.length} run{runs.length !== 1 ? "s" : ""}</p>
                   </div>
                   <div className="glass p-5 rounded-2xl border border-slate-800">
                     <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Matched</p>
                     <p className="text-2xl font-bold text-white">{runs.reduce((sum: number, r: any) => sum + (r.jobs_matched || 0), 0)}</p>
                     <p className="text-blue-400 text-[10px] mt-1">Resume-matched</p>
                   </div>
                   <div className="glass p-5 rounded-2xl border border-slate-800">
                     <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Ranked</p>
                     <p className="text-2xl font-bold text-white">{runs.reduce((sum: number, r: any) => sum + (r.jobs_ranked || 0), 0)}</p>
                     <p className="text-purple-400 text-[10px] mt-1">Scored &amp; ranked</p>
                   </div>
                   <div className="glass p-5 rounded-2xl border border-slate-800">
                     <p className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Emails Sent</p>
                     <p className="text-2xl font-bold text-white">{runs.filter((r: any) => r.emails_sent).length}</p>
                     <p className="text-amber-400 text-[10px] mt-1">Notification digests</p>
                   </div>
                 </div>
               </div>

               <div className="glass p-7 rounded-3xl border border-slate-800">
                 <h3 className="text-white font-bold mb-5">System Status</h3>
                 <div className="space-y-3">
                   {[
                     { label: "Browser Authentication", sub: authStatus?.authenticated ? `LinkedIn ${authStatus?.has_linkedin ? "✓" : "✗"}  Wellfound ${authStatus?.has_wellfound ? "✓" : "✗"}` : "Not authenticated", ok: authStatus?.authenticated },
                     { label: "Resume", sub: uploadedResumes.length > 0 ? `${uploadedResumes.length} resume${uploadedResumes.length > 1 ? "s" : ""} uploaded` : "No resumes uploaded", ok: uploadedResumes.length > 0 },
                     { label: "Search URLs", sub: savedSearchLinks.length > 0 ? `${savedSearchLinks.length} URL${savedSearchLinks.length > 1 ? "s" : ""} saved` : "No URLs configured", ok: savedSearchLinks.length > 0 },
                     ...(runs.length > 0 ? [{ label: "Last Pipeline Run", sub: `${runs[0]?.status?.charAt(0).toUpperCase() + runs[0]?.status?.slice(1)} — ${new Date(runs[0]?.started_at).toLocaleDateString()}`, ok: runs[0]?.status === "done" }] : []),
                   ].map((row) => (
                     <div key={row.label} className="flex items-center justify-between p-4 bg-slate-900 rounded-xl border border-slate-800">
                       <div className="flex items-center gap-3">
                         <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${row.ok ? "bg-emerald-500" : "bg-amber-500"}`} />
                         <div>
                           <p className="text-white font-semibold text-sm">{row.label}</p>
                           <p className="text-slate-500 text-xs">{row.sub}</p>
                         </div>
                       </div>
                     </div>
                   ))}
                 </div>
               </div>

               <div className="glass p-7 rounded-3xl border border-slate-800">
                 <h3 className="text-white font-bold mb-5">Quick Actions</h3>
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                   <button onClick={() => setActiveTab("savedlinks")} className="p-4 bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-slate-600 rounded-xl flex items-center gap-3 transition-all text-left">
                     <Globe size={20} className="text-orange-400 flex-shrink-0" />
                     <div><p className="text-white font-semibold text-sm">Manage Search URLs</p><p className="text-slate-500 text-xs">{savedSearchLinks.length} saved</p></div>
                   </button>
                   <button onClick={() => setActiveTab("resumes")} className="p-4 bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-slate-600 rounded-xl flex items-center gap-3 transition-all text-left">
                     <FileText size={20} className="text-blue-400 flex-shrink-0" />
                     <div><p className="text-white font-semibold text-sm">Upload Resume</p><p className="text-slate-500 text-xs">{uploadedResumes.length} uploaded</p></div>
                   </button>
                   <button
                     onClick={async () => {
                       if (uploadedResumes.length === 0) { alert("Please upload at least one resume first."); setActiveTab("resumes"); return; }
                       const token = (session as any)?.user?.accessToken || "";
                       try {
                         setTriggering(true);
                         const res = await triggerPipeline({}, token);
                         if (res?.run_id) setActiveRunId(res.run_id);
                         await loadData(true);
                         alert("Pipeline triggered! Check Pipeline History for status.");
                       } catch (err) { alert("Failed: " + (err as Error).message); } finally { setTriggering(false); }
                     }}
                     disabled={triggering || activeRunId !== null}
                     className="p-4 bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center gap-3 transition-all text-left"
                   >
                     <RotateCw size={20} className={`text-white flex-shrink-0 ${triggering ? "animate-spin" : ""}`} />
                     <div><p className="text-white font-semibold text-sm">Trigger Full Scan</p><p className="text-white/60 text-xs">{activeRunId ? "Already running..." : "Run pipeline on all saved URLs"}</p></div>
                   </button>
                   <button onClick={handleOpenSettings} className="p-4 bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-slate-600 rounded-xl flex items-center gap-3 transition-all text-left">
                     <Settings size={20} className="text-slate-400 flex-shrink-0" />
                     <div><p className="text-white font-semibold text-sm">Preferences</p><p className="text-slate-500 text-xs">Location, email, search queries</p></div>
                   </button>
                 </div>
               </div>
             </div>

           ) : activeTab === "history" ? (
             <PipelineHistory 
               runs={runs} 
               token={(session as any)?.user?.accessToken || ""} 
               activeRunId={activeRunId}
               onRunCancelled={() => {
                 loadData(true);
                 setActiveRunId(null);
               }}
             />
           ) : activeTab === "resumes" ? (
             <div className="p-8 space-y-8">
               <div className="glass p-8 rounded-3xl border border-slate-800 space-y-6">
                 <div>
                   <h3 className="text-xl font-bold text-white mb-2">Upload Resumes</h3>
                   <p className="text-slate-400 text-sm">Upload PDF resumes for job ranking and email outreach</p>
                 </div>
                 
                 <div className="flex items-center gap-4">
                   <label className="flex-1 relative cursor-pointer">
                     <div className="border-2 border-dashed border-slate-700 hover:border-emerald-500 rounded-2xl p-6 transition-colors">
                       <div className="flex flex-col items-center justify-center gap-2">
                         <Plus size={24} className="text-slate-500 hover:text-emerald-500" />
                         <span className="text-sm text-slate-400">
                           {resumeFile ? resumeFile.name : "Click to select PDF"}
                         </span>
                         <span className="text-xs text-slate-600">or drag and drop</span>
                       </div>
                       <input
                         type="file"
                         accept=".pdf"
                         onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                         className="hidden"
                       />
                     </div>
                   </label>
                   <button
                     onClick={async () => {
                       if (!resumeFile) {
                         alert("Please select a PDF file first");
                         return;
                       }
                       const token = (session as any)?.user?.accessToken || "";
                       try {
                         setUploading(true);
                         await uploadResume(resumeFile, token);
                         
                         const resumesData = await fetchResumes(token);
                         setUploadedResumes(resumesData);
                         
                         alert("Resume uploaded and processed successfully!");
                         setResumeFile(null);
                       } catch (error) {
                         alert("Failed to upload resume: " + (error as Error).message);
                       } finally {
                         setUploading(false);
                       }
                     }}
                     disabled={!resumeFile || uploading}
                     className="px-6 py-3 bg-emerald-500 text-white font-semibold rounded-xl hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                   >
                     {uploading ? "Uploading..." : "Upload"}
                   </button>
                 </div>
               </div>

               {uploadedResumes.length > 0 && (
                 <div className="glass p-8 rounded-3xl border border-slate-800 space-y-4">
                   <div>
                     <h3 className="text-lg font-bold text-white mb-2">Your Resumes</h3>
                     <p className="text-slate-400 text-sm">Uploaded resumes being used for job matching</p>
                   </div>
                   <div className="space-y-2">
                     {uploadedResumes.map((resume: any) => (
                       <div key={resume.id} className="flex items-center gap-3 p-3 bg-slate-900 rounded-lg border border-slate-700 hover:border-emerald-500/50 transition-colors">
                         <FileText size={16} className="text-emerald-500 flex-shrink-0" />
                         <div className="flex-1 min-w-0">
                           <p className="text-sm text-white truncate">{resume.file_name}</p>
                           <p className="text-xs text-slate-500">{new Date(resume.created_at).toLocaleDateString()}</p>
                         </div>
                       </div>
                     ))}
                   </div>
                 </div>
               )}

               <div className="glass p-8 rounded-3xl border border-slate-800 space-y-4">
                 <div>
                   <h3 className="text-lg font-bold text-white mb-2">Resume Summary</h3>
                   <p className="text-slate-400 text-sm">Brief summary for better job matching accuracy</p>
                 </div>
                 <textarea
                   value={rawSettings?.resume_summary || ""}
                   onChange={(e) => setRawSettings({...rawSettings, resume_summary: e.target.value})}
                   placeholder="e.g., Senior Full Stack Developer with 10 years experience in React, Node.js, and cloud technologies..."
                   className="w-full h-32 bg-slate-900 border border-slate-700 rounded-xl p-4 text-white placeholder-slate-600 focus:border-emerald-500 focus:outline-none resize-none"
                 />
                 <button
                   onClick={async () => {
                     const token = (session as any)?.user?.accessToken || "";
                     try {
                       await updateSettings({resume_summary: rawSettings?.resume_summary}, token);
                       alert("Resume summary updated!");
                     } catch (error) {
                       alert("Failed to update: " + (error as Error).message);
                     }
                   }}
                   className="px-6 py-2 bg-emerald-500 text-white font-semibold rounded-xl hover:bg-emerald-600 transition-colors"
                 >
                   Save Summary
                 </button>
               </div>
             </div>
           ) : activeTab === "authenticator" ? (
             <div className="p-8 space-y-8">
               <div className="glass p-8 rounded-3xl border border-slate-800 space-y-6">
                 <div className="flex items-start justify-between">
                   <div>
                     <h3 className="text-xl font-bold text-white mb-2">Browser Session Authentication</h3>
                     <p className="text-slate-400 text-sm">Log in to LinkedIn and Wellfound to enable personalized job scraping with saved session</p>
                   </div>
                   <div className="flex items-center gap-3">
                     {authStatus?.authenticated && (
                       <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/20 border border-emerald-500/30 rounded-lg">
                         <CheckCircle size={16} className="text-emerald-400" />
                         <span className="text-sm font-semibold text-emerald-400">Authenticated</span>
                       </div>
                     )}
                     <button
                       onClick={async () => {
                         const token = (session as any)?.user?.accessToken || "";
                         try {
                           const statusData = await getAuthenticationStatus(token);
                           setAuthStatus(statusData);
                           if (statusData?.authenticated) {
                             alert("✓ Session found and loaded!");
                           } else {
                             alert("No saved session found. Click 'Authenticate' to log in.");
                           }
                         } catch (error) {
                           alert("Failed to check status");
                         }
                       }}
                       className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition-colors"
                       title="Manually check for saved session"
                     >
                       ↻ Refresh
                     </button>
                   </div>
                 </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div 
                      onClick={() => {
                        setSelectedPlatforms(prev => 
                          prev.includes("linkedin") ? prev.filter(p => p !== "linkedin") : [...prev, "linkedin"]
                        );
                      }}
                      className={`p-4 rounded-lg border-2 transition-all cursor-pointer hover:border-blue-500/50 ${selectedPlatforms.includes("linkedin") ? 'bg-blue-500/10 border-blue-500/50 shadow-lg shadow-blue-500/5' : 'bg-slate-900/50 border-slate-700'}`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {authStatus?.has_linkedin ? (
                          <CheckCircle size={18} className="text-blue-400" />
                        ) : selectedPlatforms.includes("linkedin") ? (
                          <div className="w-[18px] h-[18px] border-2 border-blue-400 rounded-sm" />
                        ) : (
                          <Square size={18} className="text-slate-500" />
                        )}
                        <span className="font-semibold text-white">LinkedIn</span>
                      </div>
                      <p className="text-xs text-slate-400">{authStatus?.has_linkedin ? 'Connected' : 'Click to select'}</p>
                    </div>

                    <div 
                      onClick={() => {
                        setSelectedPlatforms(prev => 
                          prev.includes("wellfound") ? prev.filter(p => p !== "wellfound") : [...prev, "wellfound"]
                        );
                      }}
                      className={`p-4 rounded-lg border-2 transition-all cursor-pointer hover:border-orange-500/50 ${selectedPlatforms.includes("wellfound") ? 'bg-orange-500/10 border-orange-500/30 shadow-lg shadow-orange-500/5' : 'bg-slate-900/50 border-slate-700'}`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {authStatus?.has_wellfound ? (
                          <CheckCircle size={18} className="text-orange-400" />
                        ) : selectedPlatforms.includes("wellfound") ? (
                          <div className="w-[18px] h-[18px] border-2 border-orange-400 rounded-sm" />
                        ) : (
                          <Square size={18} className="text-slate-500" />
                        )}
                        <span className="font-semibold text-white">Wellfound</span>
                      </div>
                      <p className="text-xs text-slate-400">{authStatus?.has_wellfound ? 'Connected' : 'Click to select'}</p>
                    </div>

                    <div 
                      onClick={() => {
                        setSelectedPlatforms(prev => 
                          prev.includes("indeed") ? prev.filter(p => p !== "indeed") : [...prev, "indeed"]
                        );
                      }}
                      className={`p-4 rounded-lg border-2 transition-all cursor-pointer hover:border-blue-300/50 ${selectedPlatforms.includes("indeed") ? 'bg-blue-300/10 border-blue-300/30 shadow-lg shadow-blue-300/5' : 'bg-slate-900/50 border-slate-700'}`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {authStatus?.has_indeed ? (
                          <CheckCircle size={18} className="text-blue-300" />
                        ) : selectedPlatforms.includes("indeed") ? (
                          <div className="w-[18px] h-[18px] border-2 border-blue-300 rounded-sm" />
                        ) : (
                          <Square size={18} className="text-slate-500" />
                        )}
                        <span className="font-semibold text-white">Indeed</span>
                      </div>
                      <p className="text-xs text-slate-400">{authStatus?.has_indeed ? 'Connected' : 'Click to select'}</p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {selectedPlatforms.length > 0 ? (
                      <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-inner">
                        <div className="flex items-center justify-between mb-3">
                           <h4 className="text-sm font-bold text-white flex items-center gap-2">
                             <Terminal size={16} className="text-emerald-400" /> Run this locally
                           </h4>
                           <span className="text-xs text-slate-500">From project root</span>
                        </div>
                        <div className="flex gap-2">
                          <code className="flex-1 bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-emerald-300 font-mono overflow-x-auto whitespace-nowrap">
                            python scripts/auth_helper.py --platforms {selectedPlatforms.join(" ")} --user-id {(session as any)?.user?.id || "your-user-id"}
                          </code>
                          <button
                            onClick={() => {
                              const command = `python scripts/auth_helper.py --platforms ${selectedPlatforms.join(" ")} --user-id ${(session as any)?.user?.id || "your-user-id"}`;
                              navigator.clipboard.writeText(command);
                              const btn = document.getElementById('copy-cmd-btn');
                              if (btn) {
                                const orig = btn.innerHTML;
                                btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-400"><polyline points="20 6 9 17 4 12"></polyline></svg>';
                                setTimeout(() => btn.innerHTML = orig, 2000);
                              }
                            }}
                            id="copy-cmd-btn"
                            className="bg-slate-800 hover:bg-slate-700 text-white p-3 rounded-lg border border-slate-700 transition-colors flex items-center justify-center min-w-[44px]"
                            title="Copy command"
                          >
                            <Copy size={16} />
                          </button>
                        </div>
                        <p className="text-xs text-slate-400 mt-3 flex items-start gap-2">
                          <span className="text-blue-400">ℹ️</span>
                          Because the app runs in Docker, the browser window must be opened locally on your machine. Paste this command in your terminal, log in, and then click Refresh above.
                        </p>
                      </div>
                    ) : (
                      <button
                        disabled
                        className="w-full px-6 py-3 bg-slate-800 text-slate-500 font-semibold rounded-xl border border-slate-700 cursor-not-allowed"
                      >
                        Select platforms to generate command
                      </button>
                    )}

                   {authStatus?.authenticated && (
                     <button
                       onClick={async () => {
                         const token = (session as any)?.user?.accessToken || "";
                         try {
                           const result = await clearBrowserSession(token);
                           alert(result.message);
                           await loadData(true);
                         } catch (error) {
                           alert("Failed to clear session: " + (error as Error).message);
                         }
                       }}
                       className="w-full px-6 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-sm font-semibold rounded-xl border border-red-500/20 transition-colors"
                     >
                       Clear Saved Session
                     </button>
                   )}
                 </div>
               </div>
              </div>
            ) : activeTab === "savedlinks" ? (
              <div className="p-8 space-y-8">
                <div className="glass p-8 rounded-3xl border border-slate-800 space-y-6">
                  <div>
                    <h3 className="text-xl font-bold text-white mb-2">Add Search URLs</h3>
                   <p className="text-slate-400 text-sm">Paste job search URLs from any platform. LinkedIn/Wellfound links will use your authenticated session for personalized results.</p>
                 </div>
                 
                 <textarea
                   placeholder="Paste search URLs (one per line)&#10;e.g.,&#10;https://www.linkedin.com/jobs/search/?keywords=react&location=India&#10;https://wellfound.com/search?filters=roles:engineering&#10;https://www.indeed.com/jobs?q=python&l=remote"
                   value={customUrls}
                   onChange={(e) => setCustomUrls(e.target.value)}
                   className="w-full h-32 bg-slate-900 border border-slate-700 rounded-xl p-4 text-white placeholder-slate-600 focus:border-emerald-500 focus:outline-none resize-none"
                 />
                 
                 <button
                   onClick={async () => {
                     const token = (session as any)?.user?.accessToken || "";
                     const urlList = customUrls.split("\n").map(u => u.trim()).filter(u => u.length > 0);
                     if (urlList.length === 0) {
                       alert("Please paste at least one URL");
                       return;
                     }
                     try {
                       const result = await saveSearchLinks(urlList, token);
                       alert(result.message);
                       setCustomUrls("");
                       await loadData(true);
                     } catch (error) {
                       alert("Failed to save links: " + (error as Error).message);
                     }
                   }}
                   className="px-6 py-3 bg-emerald-500 text-white font-semibold rounded-xl hover:bg-emerald-600 transition-colors"
                 >
                   Save Search URLs
                 </button>
               </div>

               {savedSearchLinks.length > 0 ? (
                 <div className="glass p-8 rounded-3xl border border-slate-800 space-y-4">
                   <div>
                     <h3 className="text-lg font-bold text-white mb-1">Saved Search URLs</h3>
                     <p className="text-slate-400 text-sm">These URLs will be used in your scheduled pipeline runs</p>
                   </div>
                   <div className="space-y-3">
                     {savedSearchLinks.map((link) => (
                       <div key={link.id} className="flex items-center gap-3 p-4 bg-slate-900 rounded-lg border border-slate-700 hover:border-emerald-500/50 transition-colors group">
                         <div className="flex-1 min-w-0">
                           <div className="flex items-center gap-2 mb-1">
                             <span className="inline-block px-2 py-1 text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 rounded border border-emerald-500/30">
                               {link.platform.toUpperCase()}
                             </span>
                           </div>
                           <p className="text-sm text-slate-300 truncate font-mono text-xs">{link.url}</p>
                           <p className="text-xs text-slate-500 mt-1">Added {new Date(link.created_at).toLocaleDateString()}</p>
                         </div>
                         <button
                           onClick={async () => {
                             const token = (session as any)?.user?.accessToken || "";
                             try {
                               await deleteSearchLink(link.id, token);
                               alert("Search URL removed");
                               await loadData(true);
                             } catch (error) {
                               alert("Failed to delete: " + (error as Error).message);
                             }
                           }}
                           className="px-3 py-2 text-red-400 hover:bg-red-500/10 rounded-lg border border-red-500/20 transition-colors text-sm font-medium"
                         >
                           Remove
                         </button>
                       </div>
                     ))}
                   </div>
                 </div>
               ) : (
                 <div className="glass p-8 rounded-3xl border border-dashed border-slate-700 flex flex-col items-center justify-center h-64 text-center">
                   <Globe size={48} className="text-slate-600 mb-4" />
                   <p className="text-slate-400 font-medium">No saved search URLs yet</p>
                   <p className="text-slate-500 text-sm mt-2">Add LinkedIn or Wellfound search URLs above to automate your job searches</p>
                 </div>
               )}

               <div className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-6">
                 <h4 className="text-sm font-bold text-blue-400 mb-2">How It Works</h4>
                 <ul className="text-sm text-blue-300/80 space-y-1">
                   <li>✓ Save search URLs from any job platform (LinkedIn, Wellfound, Indeed, etc.)</li>
                   <li>✓ LinkedIn/Wellfound links use authenticated session for personalized results</li>
                   <li>✓ Saved URLs are scraped automatically on your schedule</li>
                   <li>✓ Results matched with your resume and ranked by relevance</li>
                   <li>✓ Top matches sent to you via email daily</li>
                 </ul>
               </div>
             </div>
           ) : (
             <>
               {jobs.length > 0 ? (
                 <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    {jobs.map((job) => (
                      <JobCard 
                        key={job.id}
                        id={job.id}
                        resumeId={job.resume_id}
                        title={job.title} 
                        company={job.company} 
                        score={Math.round(job.final_score * 100)} 
                        location={job.location || "Remote"} 
                        skills={job.top_matching_skills || []}
                        platform={job.source_platform}
                        salary={job.salary}
                        time={new Date(job.created_at).toLocaleDateString()}
                        url={job.source_url}
                        description={job.description}
                        experience={job.experience}
                        aboutCompany={job.about_company}
                        responsibilities={job.responsibilities}
                        requirements={job.requirements}
                        benefits={job.benefits}
                        emailDraft={job.outreach_email_draft}
                        linkedinDraft={job.outreach_linkedin_draft}
                      />
                    ))}
                 </div>
               ) : (
                 <div className="h-64 flex flex-col items-center justify-center border-2 border-dashed border-slate-900 rounded-3xl">
                    <Search size={48} className="text-slate-700 mb-4" />
                    <p className="text-slate-500 font-medium text-lg">No jobs matched yet. Start your first scan!</p>
                 </div>
               )}
             </>
           )}
        </div>
      </main>

      <AnimatePresence>
        {isSettingsOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
             <motion.div 
               initial={{ scale: 0.9, opacity: 0 }}
               animate={{ scale: 1, opacity: 1 }}
               exit={{ scale: 0.9, opacity: 0 }}
               className="bg-[#0f0f12] border border-slate-800 w-full max-w-2xl rounded-3xl overflow-hidden shadow-2xl"
             >
                <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-zinc-900/50">
                   <h3 className="text-xl font-bold text-white flex items-center gap-3">
                     <Settings className="text-emerald-500" /> Default Search Preferences
                   </h3>
                   <button onClick={() => setIsSettingsOpen(false)} className="text-slate-500 hover:text-white transition-colors"><X size={24} /></button>
                </div>

                <form onSubmit={handleSaveSettings} className="p-8 space-y-6">
                   <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Search Keywords</label>
                        <input 
                          type="text" 
                          className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm text-white focus:border-emerald-500 transition-colors"
                          placeholder="e.g. Python, React, Remote"
                          value={tempSearchQueries}
                          onChange={(e) => setTempSearchQueries(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Notification Email</label>
                        <input 
                          type="email" 
                          className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm text-white focus:border-emerald-500 transition-colors"
                          value={rawSettings?.notification_email || ""}
                          onChange={(e) => setRawSettings({...rawSettings, notification_email: e.target.value})}
                        />
                      </div>
                   </div>

                   <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Default Location</label>
                        <input 
                          type="text" 
                          className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm text-white focus:border-emerald-500 transition-colors"
                          value={rawSettings?.location || ""}
                          onChange={(e) => setRawSettings({...rawSettings, location: e.target.value})}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Default Experience Target</label>
                        <select 
                          className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm text-white focus:border-emerald-500 transition-colors appearance-none"
                          value={rawSettings?.job_experience || "0"}
                          onChange={(e) => setRawSettings({...rawSettings, job_experience: e.target.value})}
                        >
                           <option value="0">0-2 years (Fresher/Entry)</option>
                           <option value="2">2-5 years (Mid-Level)</option>
                           <option value="5">5+ years (Senior+</option>
                        </select>
                      </div>
                   </div>



                   <div className="grid grid-cols-2 gap-6 mt-6">
                      <div className="space-y-2 flex flex-col justify-start">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Max Jobs to Process per Run</label>
                        <p className="text-[10px] text-slate-600 mb-1 leading-tight">Lower this number (e.g. 10 or 20) if you are running into AI quota limits. (Max 100)</p>
                        <input 
                          type="number" 
                          min="1"
                          max="100"
                          className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm text-white focus:border-emerald-500 transition-colors"
                          value={rawSettings?.max_jobs_per_run || 20}
                          onChange={(e) => setRawSettings({...rawSettings, max_jobs_per_run: parseInt(e.target.value) || 20})}
                        />
                      </div>
                      <div className="space-y-2 flex flex-col justify-start">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Enable AI Outreach Generation</label>
                        <p className="text-[10px] text-slate-600 mb-2 leading-tight">Write personalized cold emails and LinkedIn messages. Turn off to save your daily AI budget.</p>
                        <div className="flex items-center gap-3 mt-1">
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input 
                              type="checkbox" 
                              className="sr-only peer" 
                              checked={rawSettings?.enable_outreach ?? true}
                              onChange={(e) => setRawSettings({...rawSettings, enable_outreach: e.target.checked})}
                            />
                            <div className="w-11 h-6 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-emerald-500 after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                          </label>
                          <span className="text-sm font-medium text-slate-300">
                            {rawSettings?.enable_outreach !== false ? "Enabled" : "Disabled"}
                          </span>
                        </div>
                      </div>
                   </div>

                   <div className="space-y-2 mt-6">
                      <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Resume Summary (for LLM matching)</label>
                      <textarea 
                        rows={4}
                        className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm text-white focus:border-emerald-500 transition-colors resize-none"
                        value={rawSettings?.resume_summary || ""}
                        onChange={(e) => setRawSettings({...rawSettings, resume_summary: e.target.value})}
                      />
                   </div>

                   <div className="pt-4 flex justify-end gap-4">
                      <button type="button" onClick={() => setIsSettingsOpen(false)} className="px-6 py-2 text-sm font-bold text-slate-400 hover:text-white transition-colors">Cancel</button>
                      <button type="submit" className="px-8 py-2 bg-emerald-500 text-black font-black rounded-xl text-sm hover:bg-emerald-400 transition-all shadow-lg shadow-emerald-500/10">
                        Save Preferences
                      </button>
                   </div>
                </form>
             </motion.div>
          </div>
        )}

        {isTriggerDialogOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
             <motion.div 
               initial={{ scale: 0.9, opacity: 0 }}
               animate={{ scale: 1, opacity: 1 }}
               exit={{ scale: 0.9, opacity: 0 }}
               className="bg-[#0f0f12] border border-slate-800 w-full max-w-md rounded-3xl overflow-hidden shadow-2xl"
             >
                <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-zinc-900/50">
                   <h3 className="text-xl font-bold text-white flex items-center gap-3">
                     <RotateCw className="text-emerald-500" size={24} /> Pipeline Configuration
                   </h3>
                   <button onClick={() => setIsTriggerDialogOpen(false)} className="text-slate-500 hover:text-white transition-colors"><X size={24} /></button>
                </div>

                <div className="p-8 space-y-6">
                   <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
                      <div>
                        <label className="text-sm font-bold text-slate-300">Enable Auto-Scheduling</label>
                        <p className="text-xs text-slate-500 mt-1">Automatically run this pipeline on a schedule</p>
                      </div>
                      <button
                        type="button"
                        onClick={() =>{ 
                          const newState = !enableScheduler;
                          setEnableScheduler(newState);
                          console.log("[Dashboard] Toggle clicked - enableScheduler changing from:", enableScheduler, "to:", newState);
                        }}
                        className={`relative inline-flex h-8 w-16 items-center rounded-full transition-colors ${
                          enableScheduler ? "bg-emerald-500" : "bg-slate-700"
                        }`}
                      >
                        <span
                          className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
                            enableScheduler ? "translate-x-9" : "translate-x-1"
                          }`}
                        />
                      </button>
                   </div>

                   {enableScheduler && (
                     <div className="space-y-2">
                       <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Scheduling Interval</label>
                       <select 
                         className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 text-sm text-white focus:border-emerald-500 transition-colors appearance-none"
                         value={schedulerInterval}
                         onChange={(e) => setSchedulerInterval(parseInt(e.target.value))}
                       >
                         <option value="1">Every 1 hour</option>
                         <option value="3">Every 3 hours</option>
                         <option value="6">Every 6 hours</option>
                         <option value="12">Every 12 hours</option>
                         <option value="24">Every 24 hours</option>
                       </select>
                     </div>
                   )}

                   <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
                     <p className="text-xs text-blue-300">
                       {enableScheduler 
                         ? `✓ This pipeline will automatically re-run every ${schedulerInterval} hours after completion.`
                         : "✓ This pipeline will run once and complete."
                       }
                     </p>
                   </div>

                   <div className="pt-4 flex justify-end gap-4">
                      <button type="button" onClick={() => setIsTriggerDialogOpen(false)} className="px-6 py-2 text-sm font-bold text-slate-400 hover:text-white transition-colors">Cancel</button>
                      <button type="button" onClick={handleTrigger} disabled={triggering} className="px-8 py-2 bg-emerald-500 text-black font-black rounded-xl text-sm hover:bg-emerald-400 transition-all shadow-lg shadow-emerald-500/10 disabled:opacity-50">
                        {triggering ? "Starting..." : "Start Pipeline"}
                      </button>
                   </div>
                </div>
             </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SidebarItem({ icon, label, active = false, onClick }: { icon: React.ReactNode, label: string, active?: boolean, onClick?: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all group ${active ? 'bg-emerald-500/10 text-emerald-400 font-bold' : 'text-slate-400 hover:text-white hover:bg-slate-900'}`}
    >
      <div className={`${active ? 'text-emerald-500' : 'group-hover:text-white'}`}>{icon}</div>
      <span className="text-sm">{label}</span>
      {active && <div className="ml-auto w-1 h-4 bg-emerald-500 rounded-full" />}
    </button>
  );
}

function StatCard({ label, value, icon }: { label: string, value: string, icon: React.ReactNode }) {
  return (
    <div className="glass p-5 rounded-2xl border border-slate-900 border-t-slate-800/10">
       <div className="flex items-center gap-3 mb-3">
          <div className="p-2 bg-slate-900 rounded-lg">{icon}</div>
          <span className="text-[10px] font-black text-slate-500 tracking-widest uppercase">{label}</span>
       </div>
       <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}

function JobCard({ id, resumeId, title, company, score, location, skills, time, url, platform, salary, description, experience, aboutCompany, responsibilities, requirements, benefits, emailDraft, linkedinDraft }: any) {
  const [showDetails, setShowDetails] = useState(false);
  
  const getPlatformColor = (platform: string) => {
    const p = platform?.toLowerCase() || "";
    if (p.includes("linkedin")) return "bg-blue-500/10 text-blue-400 border-blue-500/20";
    if (p.includes("indeed")) return "bg-purple-500/10 text-purple-400 border-purple-500/20";
    if (p.includes("wellfound")) return "bg-orange-500/10 text-orange-400 border-orange-500/20";
    return "bg-slate-500/10 text-slate-400 border-slate-500/20";
  };

  return (
    <>
      <motion.div 
        whileHover={{ y: -8 }}
        onClick={() => setShowDetails(true)}
        className="glass rounded-3xl border border-slate-800 hover:border-emerald-500/30 p-7 transition-all cursor-pointer group shadow-lg hover:shadow-emerald-500/10"
      >
         <div className="flex items-start justify-between mb-4">
            <div className="flex-1 pr-4">
              <div className="flex items-center gap-2 mb-2">
                <span className={`px-2 py-1 text-[10px] font-bold uppercase tracking-widest rounded-md border ${getPlatformColor(platform)}`}>
                  {platform || "Unknown"}
                </span>
                {experience && (
                  <span className="px-2 py-1 text-[10px] font-bold uppercase tracking-widest rounded-md border border-slate-700 bg-slate-800 text-slate-400">
                    {experience}
                  </span>
                )}
              </div>
              <h3 className="text-lg font-bold text-white group-hover:text-emerald-400 transition-colors line-clamp-2 mb-1">{title}</h3>
              <p className="text-sm text-slate-400">{company}</p>
            </div>
            <div className="flex flex-col items-end shrink-0">
               <div className="px-4 py-2 bg-gradient-to-r from-emerald-500/20 to-emerald-500/10 text-emerald-400 rounded-xl text-sm font-black border border-emerald-500/30 uppercase tracking-tight shadow-lg shadow-emerald-500/5">
                 {score}%
               </div>
            </div>
         </div>

         <div className="space-y-3 mb-5 pb-5 border-b border-slate-700/50">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500 flex items-center gap-2">
                <MapPin size={14} /> {location}
              </span>
              {salary && <span className="text-emerald-400 font-semibold">{salary}</span>}
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500 flex items-center gap-1"><Clock size={12} /> {time}</span>
              <span className="text-slate-600 font-medium">Match Level: {score > 85 ? 'High' : score > 70 ? 'Moderate' : 'Low'}</span>
            </div>
            <div className="text-xs text-slate-500">Matched Resume: <span className="text-slate-300 font-semibold">{resumeId || "default"}</span></div>
         </div>

         <div className="flex flex-wrap gap-2 mb-6 max-h-16 overflow-hidden">
            {(skills || []).slice(0, 6).map((s: string, idx: number) => (
              <span key={idx} className="px-2.5 py-1 bg-slate-800 text-slate-300 text-xs font-semibold rounded-lg border border-slate-700 hover:border-emerald-500/30 transition-colors">{s}</span>
            ))}
            {skills?.length > 6 && <span className="px-2.5 py-1 text-xs text-slate-500 flex items-center">+{skills.length - 6} more</span>}
         </div>

         <div className="flex items-center gap-2 pt-4 border-t border-slate-700/50">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setShowDetails(true);
              }}
              className="flex-1 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-sm font-bold rounded-lg flex items-center justify-center gap-2 transition-colors text-slate-300 border border-slate-700"
            >
              <Search size={14} /> View Analysis
            </button>
            <Link 
              href={url || "#"} 
              target="_blank"
              onClick={(e) => e.stopPropagation()}
              className="flex-1 px-4 py-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-sm font-bold rounded-lg text-black flex items-center justify-center gap-2 transition-all shadow-lg shadow-emerald-500/20"
            >
              <ExternalLink size={14} /> Apply Now
            </Link>
         </div>
      </motion.div>

      <AnimatePresence>
        {showDetails && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4" onClick={() => setShowDetails(false)}>
            <motion.div
              initial={{ scale: 0.9, y: 20, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.9, y: 20, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-[#0f0f12] border border-slate-800 w-full max-w-5xl rounded-[2.5rem] overflow-hidden shadow-2xl max-h-[90vh] flex flex-col"
            >
              <div className="p-8 border-b border-slate-800 bg-zinc-900/30 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-6">
                  <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-emerald-700 rounded-2xl flex items-center justify-center text-black shadow-lg shadow-emerald-500/20">
                    <Briefcase size={32} />
                  </div>
                  <div>
                    <h3 className="text-3xl font-black text-white tracking-tight leading-tight">{title}</h3>
                    <div className="flex items-center gap-3 mt-1.5">
                      <span className="text-emerald-400 font-bold text-lg">{company}</span>
                      <span className="w-1 h-1 bg-slate-700 rounded-full" />
                      <span className="text-slate-500 flex items-center gap-1.5 text-sm font-medium">
                        <MapPin size={14} /> {location}
                      </span>
                    </div>
                  </div>
                </div>
                <button 
                  onClick={() => setShowDetails(false)} 
                  className="w-12 h-12 flex items-center justify-center rounded-2xl bg-slate-900 text-slate-500 hover:text-white hover:bg-slate-800 transition-all border border-slate-800"
                >
                  <X size={24} />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-10 space-y-12 custom-scrollbar">
                {/* Meta Highlights */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="bg-slate-900/50 rounded-3xl p-5 border border-slate-800/50 hover:border-emerald-500/30 transition-colors">
                    <div className="flex items-center gap-2 text-slate-500 font-bold text-[10px] uppercase tracking-widest mb-2">
                      <Target size={14} className="text-emerald-500" /> Match Quality
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-black text-white">{score}%</span>
                      <span className={`text-[10px] font-black uppercase ${score > 85 ? 'text-emerald-500' : score > 70 ? 'text-blue-500' : 'text-amber-500'}`}>
                         {score > 85 ? 'High' : score > 70 ? 'Moderate' : 'Review'}
                      </span>
                    </div>
                  </div>
                  <div className="bg-slate-900/50 rounded-3xl p-5 border border-slate-800/50 hover:border-blue-500/30 transition-colors">
                    <div className="flex items-center gap-2 text-slate-500 font-bold text-[10px] uppercase tracking-widest mb-2">
                      <Award size={14} className="text-blue-500" /> Experience
                    </div>
                    <div className="text-xl font-bold text-white truncate">{experience || "Not specified"}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded-3xl p-5 border border-slate-800/50 hover:border-amber-500/30 transition-colors">
                    <div className="flex items-center gap-2 text-slate-500 font-bold text-[10px] uppercase tracking-widest mb-2">
                      <DollarSign size={14} className="text-amber-500" /> Comp Range
                    </div>
                    <div className="text-xl font-bold text-white truncate">{salary || "Undisclosed"}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded-3xl p-5 border border-slate-800/50 hover:border-purple-500/30 transition-colors">
                    <div className="flex items-center gap-2 text-slate-500 font-bold text-[10px] uppercase tracking-widest mb-2">
                      <Globe size={14} className="text-purple-500" /> Platform
                    </div>
                    <div className="text-xl font-bold text-white uppercase tracking-tight">{platform || "Generic"}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded-3xl p-5 border border-slate-800/50 hover:border-emerald-500/30 transition-colors">
                    <div className="flex items-center gap-2 text-slate-500 font-bold text-[10px] uppercase tracking-widest mb-2">
                      <FileText size={14} className="text-emerald-500" /> Matched Resume
                    </div>
                    <div className="text-xl font-bold text-white truncate">{resumeId || "default"}</div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
                  <div className="lg:col-span-2 space-y-12">
                    {/* Role Description */}
                    <section>
                      <div className="flex items-center gap-3 mb-6">
                        <div className="p-2 bg-emerald-500/10 rounded-xl">
                          <Sparkles size={20} className="text-emerald-500" />
                        </div>
                        <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">Role Overview</h4>
                      </div>
                      <div className="bg-slate-900/30 border border-slate-800/50 rounded-[2.5rem] p-8 text-slate-300 leading-relaxed text-base italic font-medium shadow-inner">
                        "{description}"
                      </div>
                    </section>

                    {/* Responsibilities (What You'll Do) */}
                    {responsibilities && (
                      <section>
                        <div className="flex items-center gap-3 mb-6">
                           <div className="p-2 bg-blue-500/10 rounded-xl">
                             <Activity size={20} className="text-blue-500" />
                           </div>
                           <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">What You'll Do</h4>
                        </div>
                        <div className="bg-slate-900/20 border border-slate-800/30 rounded-[2rem] p-8 text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                          {responsibilities}
                        </div>
                      </section>
                    )}

                    {/* Requirements (What You'll Need) */}
                    {requirements && (
                      <section>
                        <div className="flex items-center gap-3 mb-6">
                           <div className="p-2 bg-amber-500/10 rounded-xl">
                             <CheckCircle size={20} className="text-amber-500" />
                           </div>
                           <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">What You'll Need</h4>
                        </div>
                        <div className="bg-slate-900/20 border border-slate-800/30 rounded-[2rem] p-8 text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                          {requirements}
                        </div>
                      </section>
                    )}

                    {/* Benefits (What You can Expect) */}
                    {benefits && (
                      <section>
                        <div className="flex items-center gap-3 mb-6">
                           <div className="p-2 bg-purple-500/10 rounded-xl">
                             <Plus size={20} className="text-purple-500" />
                           </div>
                           <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">What You can Expect</h4>
                        </div>
                        <div className="bg-slate-900/20 border border-slate-800/30 rounded-[2rem] p-8 text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                          {benefits}
                        </div>
                      </section>
                    )}

                    {/* Outreach Drafts */}
                    <div className="grid grid-cols-1 gap-8">
                      {emailDraft && (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <Mail size={20} className="text-blue-400" />
                              <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">Email Outreach</h4>
                            </div>
                            <button 
                              onClick={() => {
                                navigator.clipboard.writeText(emailDraft);
                                const btn = document.getElementById(`copy-email-${id}`);
                                if (btn) {
                                  const originalText = btn.innerHTML;
                                  btn.innerHTML = "Copied!";
                                  setTimeout(() => btn.innerHTML = originalText, 2000);
                                }
                              }}
                              id={`copy-email-${id}`}
                              className="px-6 py-2 bg-blue-500/10 text-blue-400 rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-blue-500 hover:text-white transition-all shadow-lg shadow-blue-500/10"
                            >
                              Copy Draft
                            </button>
                          </div>
                          <div className="bg-slate-950 border border-slate-800 rounded-[2rem] p-8 text-slate-400 text-xs font-mono leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto custom-scrollbar shadow-inner">
                            {emailDraft}
                          </div>
                        </div>
                      )}

                      {linkedinDraft && (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <Briefcase size={20} className="text-emerald-400" />
                              <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">LinkedIn Direct</h4>
                            </div>
                            <button 
                              onClick={() => {
                                navigator.clipboard.writeText(linkedinDraft);
                                const btn = document.getElementById(`copy-li-${id}`);
                                if (btn) {
                                  const originalText = btn.innerHTML;
                                  btn.innerHTML = "Copied!";
                                  setTimeout(() => btn.innerHTML = originalText, 2000);
                                }
                              }}
                              id={`copy-li-${id}`}
                              className="px-6 py-2 bg-emerald-500/10 text-emerald-400 rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-emerald-500 hover:text-black transition-all shadow-lg shadow-emerald-500/10"
                            >
                              Copy Draft
                            </button>
                          </div>
                          <div className="bg-slate-950 border border-slate-800 rounded-[2rem] p-8 text-slate-400 text-xs font-mono leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto custom-scrollbar shadow-inner">
                            {linkedinDraft}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="space-y-12">
                    {/* Skills Breakdown */}
                    <section>
                      <div className="flex items-center gap-3 mb-6">
                        <div className="p-2 bg-emerald-500/10 rounded-xl">
                          <Target size={20} className="text-emerald-500" />
                        </div>
                        <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">Core Skills</h4>
                      </div>
                      <div className="flex flex-wrap gap-2.5">
                        {(skills || []).map((s: string, idx: number) => (
                          <span key={idx} className="px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-slate-300 text-[10px] font-black uppercase hover:border-emerald-500/50 transition-colors shadow-sm tracking-wider">
                            {s}
                          </span>
                        ))}
                      </div>
                    </section>

                    {/* About Company */}
                    {aboutCompany && (
                      <section>
                        <div className="flex items-center gap-3 mb-6">
                           <div className="p-2 bg-blue-500/10 rounded-xl">
                             <Building2 size={20} className="text-blue-500" />
                           </div>
                           <h4 className="text-sm font-black text-white uppercase tracking-[0.2em]">Company Insights</h4>
                        </div>
                        <div className="bg-blue-500/5 border border-blue-500/10 rounded-[2rem] p-8 text-slate-400 text-sm leading-relaxed font-medium shadow-inner">
                          {aboutCompany}
                        </div>
                      </section>
                    )}

                    {/* Stats */}
                    <div className="bg-gradient-to-br from-slate-900 to-[#0a0a0c] rounded-[2.5rem] border border-slate-800 p-8">
                       <div className="flex items-center justify-between mb-5">
                          <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Scanned on</span>
                          <span className="text-xs text-white font-black">{time}</span>
                       </div>
                       <div className="flex items-center justify-between">
                          <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Job Fingerprint</span>
                          <span className="text-[10px] text-slate-600 font-mono italic tracking-tighter">{id.substring(0, 12)}...</span>
                       </div>
                    </div>
                  </div>
                </div>

                <div className="pt-10 flex gap-5 shrink-0">
                  <Link
                    href={url || "#"}
                    target="_blank"
                    className="flex-1 h-20 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-black font-black rounded-[1.5rem] flex items-center justify-center gap-4 transition-all shadow-xl shadow-emerald-500/30 text-xl uppercase tracking-[0.1em]"
                  >
                    <ExternalLink size={24} /> Application Portal
                  </Link>
                  <button
                    onClick={() => setShowDetails(false)}
                    className="h-20 px-12 bg-slate-900 hover:bg-slate-800 text-white font-black rounded-[1.5rem] transition-all border border-slate-800 uppercase tracking-widest text-sm"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}

function BriefcaseIcon({ size, className }: { size: number, className?: string }) {
  return <Briefcase size={size} className={className} />;
}