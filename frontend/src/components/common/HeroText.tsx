export const HeroText: React.FC = () => {
  return (
    <div className="flex flex-col justify-center h-full pl-10 md:pl-14 lg:pl-20 pr-6" style={{ paddingTop: '80px' }}>

      {/* Tagline label */}
      <p
        className="text-[10px] font-bold tracking-[0.22em] text-bento-text uppercase mb-5"
        style={{ opacity: 0.4 }}
      >
        Workspace Reimagined
      </p>

      {/* Headline — 3 lines, big but contained */}
      <h1
        className="font-black text-bento-text tracking-tighter"
        style={{ fontSize: 'clamp(2.8rem, 6vw, 5.5rem)', lineHeight: '1.0' }}
      >
        Everything<br />
        you're<br />
        building.
      </h1>

      {/* Supporting paragraph */}
      <p
        className="mt-6 text-sm md:text-base font-medium leading-relaxed max-w-[260px] text-bento-text"
        style={{ opacity: 0.65 }}
      >
        One beautiful place.<br />
        A workspace designed for clarity —<br />
        no clutter, just your best work.
      </p>

      {/* CTA row */}
      <div className="mt-8 flex items-center gap-5">
        <button className="px-6 py-2.5 bg-bento-lid text-bento-cream rounded-full text-sm font-bold hover:scale-[0.97] active:scale-[0.95] transition-transform duration-200">
          Get Started
        </button>
        <a
          href="#"
          className="text-sm font-semibold text-bento-text flex items-center gap-1.5 hover:opacity-70 transition-opacity duration-200"
          style={{ opacity: 0.8 }}
        >
          See how it works <span className="ml-0.5">→</span>
        </a>
      </div>

    </div>
  );
};

export default HeroText;
