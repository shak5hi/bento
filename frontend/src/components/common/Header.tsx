import React from 'react';
import logo from '../../assets/logo.png';

export const Header: React.FC = () => {
  return (
    <header className="fixed top-0 left-0 w-full z-50 px-8 py-6 flex items-center justify-between pointer-events-none">
      {/* Logo Container */}
      <div className="flex items-center gap-3 pointer-events-auto cursor-pointer">
        <div className="w-8 h-8 rounded flex items-center justify-center overflow-hidden">
           <img src={logo} alt="Bento Logo" className="w-full h-full object-contain" />
        </div>
        <span className="text-bento-lid font-bold tracking-tight text-xl">bento</span>
      </div>

      {/* Navigation or CTA */}
      <nav className="pointer-events-auto">
        <button className="px-5 py-2.5 bg-bento-lid text-bento-cream rounded-full font-medium text-sm hover:bg-black transition-colors">
          Get Started
        </button>
      </nav>
    </header>
  );
};
