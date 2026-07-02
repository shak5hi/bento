import React from 'react';
import logo from '../../assets/logo.png';

export const Header: React.FC = () => {
  return (
    <header className="fixed top-0 left-0 w-full z-50 px-8 py-6 flex items-center justify-end pointer-events-none">
      {/* Logo Container */}
      <div className="flex items-center gap-3 pointer-events-auto cursor-pointer">
        <div className="h-14 w-auto flex items-center justify-center overflow-visible">
           <img src={logo} alt="Bento Logo" className="h-full w-auto object-contain" />
        </div>
      </div>
    </header>
  );
};
