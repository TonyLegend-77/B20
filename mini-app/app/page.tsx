'use client';

import React, { useState, useEffect } from 'react';
import { TokenTable } from '../components/TokenTable';
import { AIChat } from '../components/AIChat';
import { TokenDetailDrawer } from '../components/TokenDetailDrawer';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function B20PulseMiniApp() {
  const [tokens, setTokens] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedToken, setSelectedToken] = useState<any>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'new' | 'memes' | 'trending'>('new');

  // Fetch real data from FastAPI backend
  useEffect(() => {
    const fetchTokens = async () => {
      setLoading(true);
      try {
        const memeOnly = activeTab === 'memes';
        const res = await fetch(`${API_BASE}/tokens/recent?limit=30&meme_only=${memeOnly}`);
        if (!res.ok) throw new Error("Backend error");
        const data = await res.json();
        setTokens(data);
      } catch (err) {
        console.error("Failed to fetch from backend. Is FastAPI running on port 8000?", err);
        // Fallback demo data
        setTokens([
          { address: "0xb200000000000000000000231d6c1f1ce455ba32", name: "B420", symbol: "B420", variant: "ASSET", age: "2h ago", memeScore: 85, risk: "MEDIUM", liquidity: "$12.4k", isMeme: true },
          { address: "0xb2000000000000000000003def83e24a9a000b20", name: "First B20", symbol: "B20", variant: "ASSET", age: "18h ago", memeScore: 40, risk: "HIGH", liquidity: "$421k", isMeme: false },
        ]);
      } finally {
        setLoading(false);
      }
    };
    fetchTokens();
  }, [activeTab]);

  const filteredTokens = tokens; // Backend already filters when meme_only=true

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <div className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-xl">B</div>
            <div>
              <div className="font-semibold text-xl tracking-tight">B20 Pulse</div>
              <div className="text-[10px] text-zinc-500 -mt-1">LIVE ON BASE • BERYL</div>
            </div>
          </div>
          
          <div className="flex items-center gap-4 text-sm">
            <div className="px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800 text-xs flex items-center gap-2">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              Base Mainnet
            </div>
            <button 
              onClick={() => setIsChatOpen(true)}
              className="px-4 py-2 rounded-2xl bg-white text-black font-medium text-sm hover:bg-zinc-200 transition flex items-center gap-2"
            >
              💬 Ask AI
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="max-w-5xl mx-auto px-4 flex gap-1 border-t border-zinc-800">
          {[
            { key: 'new', label: 'New Launches' },
            { key: 'memes', label: 'Memes Only' },
            { key: 'trending', label: 'Trending' },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`px-5 py-3 text-sm font-medium border-b-2 transition ${
                activeTab === tab.key 
                  ? 'border-blue-600 text-white' 
                  : 'border-transparent text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Stats Bar */}
        <div className="flex gap-4 mb-6 text-sm">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl px-4 py-3 flex-1">
            <div className="text-zinc-500 text-xs">B20 Tokens (24h)</div>
            <div className="text-2xl font-semibold tabular-nums">{tokens.length}</div>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl px-4 py-3 flex-1">
            <div className="text-zinc-500 text-xs">Showing</div>
            <div className="text-2xl font-semibold tabular-nums">{activeTab === 'memes' ? 'Memes' : 'All'}</div>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl px-4 py-3 flex-1">
            <div className="text-zinc-500 text-xs">Avg Risk</div>
            <div className="text-2xl font-semibold tabular-nums">~65</div>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12 text-zinc-400">Loading latest B20 tokens from backend...</div>
        ) : (
          <TokenTable 
            tokens={filteredTokens} 
            onTokenClick={setSelectedToken}
          />
        )}

        <p className="text-center text-xs text-zinc-500 mt-8">
          Data from B20Factory via FastAPI • Real-time risk scoring enabled
        </p>
      </div>

      {/* Token Detail Drawer */}
      {selectedToken && (
        <TokenDetailDrawer 
          token={selectedToken} 
          onClose={() => setSelectedToken(null)}
          onAskAI={() => {
            setSelectedToken(null);
            setIsChatOpen(true);
          }}
          apiBase={API_BASE}
        />
      )}

      {/* Floating AI Chat */}
      <AIChat 
        isOpen={isChatOpen} 
        onClose={() => setIsChatOpen(false)} 
        apiBase={API_BASE}
      />
    </div>
  );
}
