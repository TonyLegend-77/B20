'use client';

import React, { useState } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export function AIChat({ isOpen, onClose, apiBase }: { 
  isOpen: boolean; 
  onClose: () => void;
  apiBase: string;
}) {
  const [messages, setMessages] = useState<Message[]>([
    { 
      role: 'assistant', 
      content: "Hey, I'm B20 Pulse. I track new B20 tokens on Base and analyze issuer risk, memes, and on-chain signals.\n\nWhat do you want to know? (e.g. 'latest memes with renounced roles' or paste a 0xb200 address)" 
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setIsLoading(true);

    try {
      const res = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: currentInput })
      });
      
      const data = await res.json();
      
      const reply: Message = {
        role: 'assistant',
        content: data.response || data.error || "Sorry, something went wrong with the agent."
      };
      setMessages(prev => [...prev, reply]);
    } catch (error) {
      const reply: Message = {
        role: 'assistant',
        content: "Could not connect to the Gemini agent. Is the FastAPI backend running on port 8000?"
      };
      setMessages(prev => [...prev, reply]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/70 md:items-center" onClick={onClose}>
      <div 
        className="bg-zinc-950 border border-zinc-800 w-full max-w-lg rounded-t-3xl md:rounded-3xl flex flex-col h-[75vh] md:h-[520px]"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-sm font-bold">AI</div>
            <div>
              <div className="font-semibold">B20 Pulse AI (Gemini)</div>
              <div className="text-[10px] text-emerald-400">Tool-calling + Streaming Ready</div>
            </div>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-white text-xl leading-none">×</button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 text-sm">
          {messages.map((msg, i) => (
            <div key={i} className={msg.role === 'user' ? 'text-right' : ''}>
              <div className={`inline-block max-w-[85%] rounded-2xl px-4 py-3 ${
                msg.role === 'user' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-zinc-900 border border-zinc-800'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="text-xs text-zinc-500 flex items-center gap-2">
              <div className="animate-pulse">Gemini thinking + using tools...</div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-zinc-800">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Ask about latest B20 memes, a specific address, or risk..."
              className="flex-1 bg-zinc-900 border border-zinc-800 rounded-2xl px-4 py-3 text-sm placeholder:text-zinc-500 focus:outline-none focus:border-zinc-700"
            />
            <button 
              onClick={sendMessage}
              disabled={isLoading || !input.trim()}
              className="px-5 rounded-2xl bg-white text-black disabled:opacity-50 font-medium"
            >
              Send
            </button>
          </div>
          <p className="text-[10px] text-center text-zinc-600 mt-2">Powered by Gemini + real on-chain tools • Not financial advice</p>
        </div>
      </div>
    </div>
  );
}
