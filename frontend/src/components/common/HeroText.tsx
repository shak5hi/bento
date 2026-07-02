import React from 'react';

export const HeroText: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-start relative z-10 px-8 pt-[20vh] text-center pointer-events-none">
      <div className="max-w-4xl w-full flex flex-col items-center pointer-events-auto">
        <h1 className="text-5xl md:text-6xl lg:text-7xl font-semibold tracking-tighter text-bento-text leading-[1.1]">
          Everything you're building.<br />
          One beautiful place.
        </h1>
        <p className="mt-8 text-lg md:text-xl text-bento-text font-medium opacity-70 max-w-2xl leading-relaxed">
          A workspace designed for clarity. No clutter, just your best work.
        </p>
        <button className="mt-10 px-6 py-2.5 bg-bento-lid text-bento-cream rounded-full font-medium text-sm hover:scale-[0.98] transition-transform duration-300">
          Get Started
        </button>
      </div>
    </div>
  );
};
