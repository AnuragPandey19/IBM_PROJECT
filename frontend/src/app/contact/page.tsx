"use client";

import { useState } from "react";
import { PublicShell } from "@/components/PublicShell";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [category, setCategory] = useState("General inquiry");
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Simulated submit — real backend integration would POST to /api/contact.
    console.log({ name, email, company, category, message });
    setSubmitted(true);
    setTimeout(() => {
      setName("");
      setEmail("");
      setCompany("");
      setMessage("");
      setCategory("General inquiry");
      setSubmitted(false);
    }, 3500);
  }

  return (
    <PublicShell>
      {/* Hero */}
      <section className="pt-24 pb-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-radial from-red-950/20 via-transparent to-transparent" />
        <div className="max-w-4xl mx-auto px-6 text-center relative">
          <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-4">
            Contact us
          </div>
          <h1 className="text-4xl md:text-6xl font-serif font-black tracking-tight mb-6">
            Let&apos;s talk.
          </h1>
          <p className="text-lg text-slate-400 leading-relaxed">
            Questions about the model, deployment guidance, custom integrations,
            or research collaboration &mdash; we&apos;re happy to help.
          </p>
        </div>
      </section>

      {/* Content */}
      <section className="py-12">
        <div className="max-w-6xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Contact info */}
          <div className="lg:col-span-2 space-y-6">
            <ContactCard
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                  <polyline points="22,6 12,13 2,6" />
                </svg>
              }
              title="Email"
              lines={["anurag.apwork@gmail.com", "Response within 48 hours"]}
            />
            <ContactCard
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
              }
              title="Live demo"
              lines={["undebuggedbit-chimera-fd.hf.space", "Public instance on Hugging Face"]}
            />
            <ContactCard
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              }
              title="Support"
              lines={["Bug reports & feature requests", "GitHub Issues on the project repo"]}
            />

            <div className="bg-gradient-to-br from-red-950/40 to-slate-900 border border-red-500/20 rounded-2xl p-6">
              <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-2">
                Office hours
              </div>
              <div className="text-2xl font-bold mb-1">Mon &ndash; Fri</div>
              <div className="text-slate-400 text-sm">10:00 AM &ndash; 7:00 PM IST</div>
              <div className="text-slate-500 text-xs mt-3">
                Best time to reach us for real-time chat.
              </div>
            </div>
          </div>

          {/* Form */}
          <div className="lg:col-span-3">
            {submitted ? (
              <div className="bg-slate-900/60 border border-emerald-500/30 rounded-3xl p-12 text-center">
                <div className="w-20 h-20 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 text-4xl mx-auto mb-4">
                  &#10003;
                </div>
                <h2 className="text-2xl font-bold mb-2">Message received</h2>
                <p className="text-slate-400">
                  Thanks for reaching out. We&apos;ll get back to you within 48 hours.
                </p>
              </div>
            ) : (
              <form
                onSubmit={handleSubmit}
                className="bg-slate-900/60 border border-slate-800 rounded-3xl p-8"
              >
                <h2 className="text-2xl font-bold mb-2">Send us a note</h2>
                <p className="text-sm text-slate-400 mb-6">
                  All fields required unless marked optional.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <label className="block">
                    <span className="text-sm text-slate-300 mb-1 block">Full name</span>
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-red-500 transition"
                    />
                  </label>

                  <label className="block">
                    <span className="text-sm text-slate-300 mb-1 block">Work email</span>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-red-500 transition"
                    />
                  </label>
                </div>

                <label className="block mb-4">
                  <span className="text-sm text-slate-300 mb-1 block">Company (optional)</span>
                  <input
                    type="text"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="Where do you work?"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-red-500 transition"
                  />
                </label>

                <label className="block mb-4">
                  <span className="text-sm text-slate-300 mb-1 block">Category</span>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-red-500"
                  >
                    <option>General inquiry</option>
                    <option>Product demo request</option>
                    <option>Deployment consultation</option>
                    <option>Custom integration</option>
                    <option>Research collaboration</option>
                    <option>Bug report</option>
                    <option>Media / press</option>
                  </select>
                </label>

                <label className="block mb-6">
                  <span className="text-sm text-slate-300 mb-1 block">Message</span>
                  <textarea
                    required
                    rows={5}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Tell us what you're working on..."
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-red-500 transition resize-none"
                  />
                </label>

                <button
                  type="submit"
                  className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-lg transition shadow-lg shadow-red-500/20"
                >
                  Send message
                </button>
              </form>
            )}
          </div>
        </div>
      </section>
    </PublicShell>
  );
}

function ContactCard({ icon, title, lines }: { icon: React.ReactNode; title: string; lines: string[] }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 hover:border-red-500/40 transition">
      <div className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400 mb-3">
        {icon}
      </div>
      <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
        {title}
      </div>
      {lines.map((l, i) => (
        <div key={i} className={i === 0 ? "text-base font-semibold mt-1" : "text-xs text-slate-400 mt-0.5"}>
          {l}
        </div>
      ))}
    </div>
  );
}
