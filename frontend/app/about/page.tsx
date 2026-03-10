"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";

const ScalesIcon = ({ className = "" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 100 100" fill="none">
    <defs>
      <linearGradient id="sg" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#fbbf24" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
    </defs>
    <rect x="35" y="85" width="30" height="8" rx="2" fill="url(#sg)" />
    <rect x="45" y="30" width="10" height="58" fill="url(#sg)" />
    <rect x="10" y="25" width="80" height="6" rx="2" fill="url(#sg)" />
    <circle cx="50" cy="20" r="8" fill="url(#sg)" />
  </svg>
);

export default function AboutPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => setUser(data.user));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-0">
          <div className="flex items-center justify-between h-16">
            <button onClick={() => router.push("/")} className="flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <ScalesIcon className="w-5 h-5" />
              </div>
              <span className="text-base font-bold tracking-tight">MockPrep<span className="text-amber-400">AI</span></span>
            </button>
            <nav className="hidden md:flex items-center gap-1">
              <button onClick={() => router.push("/")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">{user ? "Dashboard" : "Home"}</button>
              {!user && <button onClick={() => router.push("/trials")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Recorded Trials</button>}
              <button className="px-4 py-2 text-sm font-medium text-white bg-slate-800/60 rounded-lg transition-colors">Who We Are</button>
              <button onClick={() => router.push("/contact")} className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/50 rounded-lg transition-colors">Contact</button>
            </nav>
            {user ? (
              <button onClick={() => router.push("/profile")} className="hidden sm:flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white text-xs font-bold hover:opacity-80 transition-opacity" title="Profile">{(user.email || "U")[0].toUpperCase()}</button>
            ) : (
              <button onClick={() => router.push("/login")} className="px-4 py-2 text-sm font-medium text-amber-400 border border-amber-500/30 hover:bg-amber-500/10 rounded-lg transition-colors">Sign In</button>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative py-16 md:py-24 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/5 via-transparent to-transparent" />
        <div className="relative max-w-4xl mx-auto px-4 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-full text-amber-400 text-xs font-semibold mb-6">
            <ScalesIcon className="w-3.5 h-3.5" />
            ABOUT MOCKPREP AI
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
            Building the Future of<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-orange-400">Mock Trial Preparation</span>
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto">
            We believe every aspiring attorney deserves world-class trial preparation.
            MockPrepAI combines artificial intelligence with proven legal pedagogy to make that a reality.
          </p>
        </div>
      </section>

      {/* Our Approach */}
      <section id="approach" className="py-16 border-t border-slate-800/50">
        <div className="max-w-5xl mx-auto px-4">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <div className="text-xs text-amber-400 uppercase tracking-widest font-semibold mb-3">Our Approach</div>
              <h2 className="text-3xl font-bold text-white mb-4">AI That Thinks Like a Trial Attorney</h2>
              <p className="text-slate-400 mb-4 leading-relaxed">
                MockPrepAI isn&apos;t a simple chatbot. Our platform uses advanced large language models fine-tuned
                with legal reasoning to simulate authentic courtroom experiences. Each AI agent — from opposing counsel
                to the presiding judge — behaves with strategic intent, adapting to your arguments in real time.
              </p>
              <p className="text-slate-400 leading-relaxed">
                We model our simulations after AMTA (American Mock Trial Association) rules and standards, ensuring
                that the skills you develop transfer directly to competitive mock trial and real-world litigation practice.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { icon: "🧠", title: "Adaptive AI", desc: "Agents adjust strategy based on your performance" },
                { icon: "⚖️", title: "AMTA Standards", desc: "Follows official competition rules and formats" },
                { icon: "📊", title: "Real-time Scoring", desc: "Judicial feedback after every phase" },
                { icon: "🔄", title: "Iterative Practice", desc: "Repeat any phase to refine your technique" },
              ].map((item, i) => (
                <div key={i} className="bg-slate-800/50 border border-slate-700/40 rounded-xl p-5">
                  <div className="text-2xl mb-2">{item.icon}</div>
                  <div className="text-sm font-semibold text-white mb-1">{item.title}</div>
                  <div className="text-xs text-slate-500">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Our History */}
      <section id="history" className="py-16 border-t border-slate-800/50 bg-slate-900/30">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-12">
            <div className="text-xs text-amber-400 uppercase tracking-widest font-semibold mb-3">Our History</div>
            <h2 className="text-3xl font-bold text-white mb-4">From Idea to Innovation</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              What started as a passion project by mock trial competitors grew into a platform serving students,
              law schools, and legal professionals.
            </p>
          </div>
          <div className="relative">
            <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-amber-500/40 via-indigo-500/40 to-transparent hidden md:block" />
            {[
              { year: "2024", title: "The Spark", desc: "Recognized the gap in accessible, high-quality mock trial preparation tools. Began prototyping AI courtroom simulations." },
              { year: "2025", title: "Building the Engine", desc: "Developed multi-agent AI architecture with specialized attorney, witness, and judge personas. Integrated AMTA rule compliance and real-time scoring." },
              { year: "2025", title: "Platform Launch", desc: "Released MockPrepAI with full trial simulation, case analysis, witness preparation, and performance analytics. Opened to law students and mock trial teams." },
              { year: "2026", title: "Growing Forward", desc: "Expanding case library, adding voice-powered interactions, and building community features for team collaboration and coaching." },
            ].map((item, i) => (
              <div key={i} className={`relative flex items-start gap-8 mb-10 ${i % 2 === 0 ? "md:flex-row" : "md:flex-row-reverse"}`}>
                <div className={`flex-1 ${i % 2 === 0 ? "md:text-right" : ""}`}>
                  <div className="bg-slate-800/50 border border-slate-700/40 rounded-xl p-6">
                    <div className="text-amber-400 font-bold text-sm mb-1">{item.year}</div>
                    <div className="text-lg font-semibold text-white mb-2">{item.title}</div>
                    <div className="text-sm text-slate-400 leading-relaxed">{item.desc}</div>
                  </div>
                </div>
                <div className="hidden md:flex items-center justify-center w-4 h-4 mt-6 rounded-full bg-amber-500 border-4 border-slate-900 z-10 shrink-0" />
                <div className="flex-1 hidden md:block" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Our Mission */}
      <section id="mission" className="py-16 border-t border-slate-800/50">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <div className="text-xs text-amber-400 uppercase tracking-widest font-semibold mb-3">Our Mission</div>
          <h2 className="text-3xl font-bold text-white mb-6">Democratize Trial Preparation</h2>
          <p className="text-lg text-slate-400 max-w-3xl mx-auto mb-10 leading-relaxed">
            Great trial advocacy shouldn&apos;t depend on having access to expensive coaching or large teams.
            Our mission is to give every student, attorney, and legal professional the tools to practice,
            improve, and compete at the highest level — powered by AI that understands the art of persuasion.
          </p>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: "🎯", title: "Accessible Excellence", desc: "Professional-grade trial preparation available to anyone, anywhere, anytime." },
              { icon: "🤝", title: "Inclusive by Design", desc: "Built for diverse learners — whether you're a first-generation law student or a seasoned litigator." },
              { icon: "📈", title: "Continuous Growth", desc: "Performance analytics and AI feedback that help you measurably improve with every session." },
            ].map((item, i) => (
              <div key={i} className="bg-gradient-to-b from-slate-800/60 to-slate-800/30 border border-slate-700/40 rounded-xl p-6 text-center">
                <div className="text-3xl mb-3">{item.icon}</div>
                <div className="text-base font-semibold text-white mb-2">{item.title}</div>
                <div className="text-sm text-slate-400 leading-relaxed">{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Team / Values */}
      <section className="py-16 border-t border-slate-800/50 bg-slate-900/30">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Our Values</h2>
          <p className="text-slate-400 mb-10 max-w-2xl mx-auto">The principles that guide everything we build.</p>
          <div className="grid md:grid-cols-4 gap-4">
            {[
              { icon: "⚡", label: "Innovation", desc: "Pushing boundaries with AI" },
              { icon: "🎓", label: "Education", desc: "Learning through practice" },
              { icon: "🔒", label: "Integrity", desc: "Honest, ethical technology" },
              { icon: "🌍", label: "Access", desc: "Open to all learners" },
            ].map((v, i) => (
              <div key={i} className="bg-slate-800/40 border border-slate-700/30 rounded-xl p-5">
                <div className="text-2xl mb-2">{v.icon}</div>
                <div className="text-sm font-bold text-white">{v.label}</div>
                <div className="text-xs text-slate-500 mt-1">{v.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 border-t border-slate-800/50">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-2xl font-bold text-white mb-3">Ready to Sharpen Your Skills?</h2>
          <p className="text-slate-400 mb-6">Start your first AI-powered mock trial session today.</p>
          <div className="flex items-center justify-center gap-4">
            <button onClick={() => router.push("/")} className="px-6 py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-amber-500/20">
              Get Started
            </button>
            <button onClick={() => router.push("/contact")} className="px-6 py-3 bg-slate-800/50 hover:bg-slate-700/50 text-slate-300 border border-slate-700/50 rounded-xl transition-colors">
              Contact Us
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800/50 py-8 bg-slate-950/50">
        <div className="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <ScalesIcon className="w-3.5 h-3.5" />
            </div>
            <span className="text-sm font-bold text-white">MockPrep<span className="text-amber-400">AI</span></span>
          </div>
          <div className="flex items-center gap-6 text-sm text-slate-500">
            <button onClick={() => router.push("/")} className="hover:text-slate-400 transition-colors">Dashboard</button>
            <button onClick={() => router.push("/about")} className="hover:text-slate-400 transition-colors">About</button>
            <button onClick={() => router.push("/contact")} className="hover:text-slate-400 transition-colors">Contact</button>
          </div>
          <p className="text-xs text-slate-600">AI-powered preparation for mock trial excellence.</p>
        </div>
      </footer>
    </div>
  );
}
