'use client';

import React, { useState, useEffect } from 'react';

interface Token {
  address: string;
  name: string;
  symbol: string;
  variant: string;
  age: string;
  memeScore: number;
  risk: string;
  liquidity: string;
  isMeme: boolean;
}

export function TokenDetailDrawer({ 
  token, 
  onClose, 
  onAskAI,
  apiBase 
}: { 
  token: Token; 
  onClose: () => void; 
  onAskAI: () => void;
  apiBase: string;
}) {
  const [riskData, setRiskData] = useState<any>(null);
  const [loadingRisk, setLoadingRisk] = useState(true);

  useEffect(() => {
    const fetchRisk = async () => {
      setLoadingRisk(true);
      try {
        const res = await fetch(`${apiBase}/tokens/${token.address}/risk`);
        const data = await res.json();
        setRiskData(data);
      } catch (e) {
        console.error("Failed to fetch risk analysis");
        setRiskData({
          risk_score: 50,
          risk_level: token.risk || "MEDIUM",
          reasons: ["Using cached data - backend may be offline"],
          details: {}
        });
      } finally {
        setLoadingRisk(false);
      }
    };
    fetchRisk();
  }, [token.address, apiBase]);

  return (
    <div className="fixed inset-0 z-[90] flex justify-end bg-black/60" onClick={onClose}>
      <div 
        className="w-full max-w-md bg-zinc-950 border-l border-zinc-800 h-full overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-6">
          <div className="flex justify-between items-start mb-6">
            <div>
              <div className="text-2xl font-semibold flex items-center gap-2">
                {token.name} <span className="text-lg text-zinc-400">${token.symbol}</span>
              </div>
              <div className="font-mono text-xs text-zinc-500 mt-1 break-all">{token.address}</div>
            </div>
            <button onClick={onClose} className="text-3xl text-zinc-400 hover:text-white">×</button>
          </div>

          {/* Live Risk Analysis from Backend */}
          <div className="mb-8">
            <div className="uppercase text-xs tracking-[1px] text-zinc-500 mb-3 flex items-center gap-2">
              LIVE RISK ANALYSIS 
              {loadingRisk && <span className="text-[10px]">(loading...)</span>}
            </div>
            
            {riskData && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4">
                <div className="flex justify-between items-end">
                  <div>
                    <div className="text-xs text-zinc-500">Risk Score</div>
                    <div className={`text-4xl font-bold tabular-nums ${
                      riskData.risk_level === 'LOW' ? 'text-emerald-400' : 
                      riskData.risk_level === 'MEDIUM' ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {riskData.risk_score}
                    </div>
                  </div>
                  <div className={`px-4 py-1 rounded-full text-sm font-medium ${
                    riskData.risk_level === 'LOW' ? 'bg-emerald-500/10 text-emerald-400' : 
                    riskData.risk_level === 'MEDIUM' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-red-500/10 text-red-400'
                  }`}>
                    {riskData.risk_level} RISK
                  </div>
                </div>

                <div>
                  <div className="text-xs text-zinc-500 mb-2">Key Findings</div>
                  <ul className="space-y-1.5 text-sm">
                    {riskData.reasons?.map((reason: string, i: number) => (
                      <li key={i} className="flex gap-2">• {reason}</li>
                    ))}
                  </ul>
                </div>

                {riskData.details && Object.keys(riskData.details).length > 0 && (
                  <div className="pt-3 border-t border-zinc-800 text-xs text-zinc-400">
                    <div>Admin renounced: {riskData.details.admin_renounced ? "Yes ✓" : "No ⚠️"}</div>
                    <div>Mint renounced: {riskData.details.mint_renounced ? "Yes ✓" : "No ⚠️"}</div>
                  </div>
                )}
              </div>
            )}
          </div>

          <button 
            onClick={onAskAI}
            className="w-full py-4 rounded-2xl bg-white text-black font-semibold active:bg-zinc-200 transition"
          >
            Ask B20 Pulse AI for deeper analysis →
          </button>

          <p className="text-center text-[10px] text-zinc-500 mt-4">
            Real-time on-chain data from B20Factory + Risk Scorer
          </p>
        </div>
      </div>
    </div>
  );
}
