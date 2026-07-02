import { Header } from './components/common/Header';

export default function App() {
  return (
    <div className="w-full h-screen bg-bento-bg text-bento-text flex flex-col relative overflow-hidden">
      <Header />
      <main className="flex-1 flex flex-col justify-center relative z-10 px-12 md:px-24">
        <div className="max-w-5xl w-full flex flex-col items-start pt-16">
          <h1 className="text-6xl md:text-7xl lg:text-8xl font-playful font-bold tracking-tight text-bento-text leading-[0.95]">
            Every project <br/>
            deserves a <br/>
            place at the <br/>
            table.
          </h1>
          <p className="mt-6 mb-10 text-lg md:text-xl text-bento-text font-medium opacity-80">
            Strategy, identity, and campaign ideas with flavor
          </p>
          <button className="px-8 py-4 bg-bento-lid text-bento-cream rounded-full font-bold text-lg hover:bg-black transition-colors shadow-lg hover:shadow-xl hover:-translate-y-0.5 transform duration-200">
            Get Started
          </button>
        </div>
      </main>
    </div>
  )
}
