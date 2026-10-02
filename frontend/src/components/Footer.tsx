import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="w-full bg-[#030914] border-t border-cyan-950/60 px-4 sm:px-6 lg:px-8 py-2.5 text-xs text-slate-400 select-none z-30">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2.5">
        {/* Left: Indian Antarctic Programme */}
        <div className="flex items-center gap-2.5">
          {/* Authentic Indian Flag SVG */}
          <div className="w-6 h-4 rounded-sm overflow-hidden flex flex-col shadow-sm border border-slate-700/50">
            <div className="w-full h-1/3 bg-[#FF9933]"></div>
            <div className="w-full h-1/3 bg-white relative flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full border-[0.5px] border-[#000080] flex items-center justify-center">
                <div className="w-0.5 h-0.5 rounded-full bg-[#000080]"></div>
              </div>
            </div>
            <div className="w-full h-1/3 bg-[#128807]"></div>
          </div>
          <span className="font-medium text-slate-300 tracking-wide">
            Indian Antarctic Programme
          </span>
        </div>

        {/* Center: Coordinates & Location */}
        <div className="text-center font-mono text-[11px] text-slate-400">
          <span>Maitri Station, Antarctica</span>
          <span className="mx-2 text-cyan-700">|</span>
          <span className="text-cyan-400/90 font-medium">70.8° S, 11.7° E</span>
        </div>

        {/* Right: Version & Tagline */}
        <div className="flex items-center gap-2 text-right text-[11px]">
          <span className="font-mono text-slate-400 font-semibold">DHRUVA v1.0</span>
          <span className="text-cyan-800">|</span>
          <span className="text-slate-400 tracking-wide hidden sm:inline">
            Clean Energy. Resilient Tomorrow.
          </span>
        </div>
      </div>
    </footer>
  );
};
