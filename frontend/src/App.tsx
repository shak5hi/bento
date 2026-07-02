import { Header } from './components/common/Header';

export default function App() {
  return (
    <div className="w-full h-screen bg-bento-bg text-bento-text flex flex-col relative overflow-hidden">
      <Header />
      <main className="flex-1 flex items-center justify-center relative z-10">
        <h1 className="text-4xl font-bold tracking-tight text-bento-cream">
          Bento SaaS Experience
        </h1>
      </main>
    </div>
  )
}
