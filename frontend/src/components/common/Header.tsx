import logo from '../../assets/logo.png';

export const Header: React.FC = () => {
  return (
    <header className="absolute top-0 left-0 w-full z-50 px-8 py-5 flex items-center justify-between">
      
      {/* Logo: "BENT" + onigiri icon (replaces "O") */}
      <div className="flex items-center cursor-pointer">
        <span className="text-2xl font-black tracking-tight text-bento-text">BENT</span>
        <img
          src={logo}
          alt="O"
          className="h-7 w-7 object-contain -ml-0.5 -mb-0.5"
        />
      </div>

      {/* Nav links + CTA */}
      <nav className="flex items-center gap-8">
        <a href="#" className="text-sm font-medium text-bento-text hover:opacity-70 transition-opacity">Product</a>
        <a href="#" className="text-sm font-medium text-bento-text hover:opacity-70 transition-opacity">Features</a>
        <a href="#" className="text-sm font-medium text-bento-text hover:opacity-70 transition-opacity">About</a>
        <button className="px-5 py-2 bg-bento-lid text-bento-cream rounded-full text-sm font-semibold hover:scale-[0.97] active:scale-[0.95] transition-transform duration-200">
          Get Started
        </button>
      </nav>

    </header>
  );
};

export default Header;
