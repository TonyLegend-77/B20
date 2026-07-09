'use client';

import React from 'react';

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

interface Props {
  tokens: Token[];
  onTokenClick: (token: Token) => void;
}

export function TokenTable({ tokens, onTokenClick }: Props) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-3xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="border-b border-zinc-800 bg-zinc-950">
          <tr className="text-left text-zinc-400">
            <th className="px-6 py-4 font-normal">Token</th>
            <th className="px-4 py-4 font-normal">Age</th>
            <th className="px-4 py-4 font-normal">Meme Score</th>
            <th className="px-4 py-4 font-normal">Risk</th>
            <th className="px-4 py-4 font-normal text-right">Liquidity</th>
            <th className="px-6 py-4 w-12"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800">
          {tokens.length === 0 && (
            <tr>
              <td colSpan={6} className="px-6 py-12 text-center text-zinc-500">
                No tokens found in this filter.
              </td>
            </tr>
          )}
          {tokens.map((token, index) => (
            <tr 
              key={index}
              onClick={() => onTokenClick(token)}
              className="hover:bg-zinc-800/60 cursor-pointer transition group"
            >
              <td className="px-6 py-4">
                <div className="font-medium flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-mono">
                    {token.symbol.slice(0,2)}
                  </div>
                  <div>
                    <div>{token.name}</div>
                    <div className="text-xs text-zinc-500 font-mono">${token.symbol}</div>
                  </div>
                  {token.isMeme && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20">MEME</span>
                  )}
                </div>
              </td>
              <td className="px-4 py-4 text-zinc-400 text-xs tabular-nums">{token.age}</td>
              <td className="px-4 py-4">
                <div className="flex items-center gap-2">
                  <div className="font-mono text-sm">{token.memeScore}</div>
                  <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden max-w-[60px]">
                    <div 
                      className="h-full bg-orange-500 transition-all" 
                      style={{ width: `${token.memeScore}%` }}
                    />
                  </div>
                </div>
              </td>
              <td className="px-4 py-4">
                <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
                  token.risk === 'LOW' ? 'bg-emerald-500/10 text-emerald-400' :
                  token.risk === 'MEDIUM' ? 'bg-yellow-500/10 text-yellow-400' :
                  'bg-red-500/10 text-red-400'
                }`}>
                  {token.risk}
                </span>
              </td>
              <td className="px-4 py-4 text-right font-mono text-sm tabular-nums text-zinc-300">
                {token.liquidity}
              </td>
              <td className="px-6 py-4 text-right">
                <button 
                  onClick={(e) => { e.stopPropagation(); onTokenClick(token); }}
                  className="opacity-0 group-hover:opacity-100 text-xs px-3 py-1.5 rounded-xl border border-zinc-700 hover:bg-zinc-800 transition"
                >
                  Analyze →
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
