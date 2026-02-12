import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Leaderboard from './components/Leaderboard'
import PlayerRank from './components/PlayerRank'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 5000, // Refetch every 5 seconds for live updates
      staleTime: 3000,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        {/* Header */}
        <header className="bg-black bg-opacity-30 backdrop-blur-md border-b border-purple-500/20">
          <div className="container mx-auto px-4 py-6">
            <h1 className="text-4xl font-bold text-center text-gradient">
              LeaderForge
            </h1>
            <p className="text-center text-purple-300 mt-2">
              High-Performance Gaming Leaderboard
            </p>
          </div>
        </header>

        {/* Main Content */}
        <main className="container mx-auto px-4 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Leaderboard - Takes 2 columns on large screens */}
            <div className="lg:col-span-2">
              <Leaderboard />
            </div>

            {/* Player Rank Lookup - Takes 1 column */}
            <div className="lg:col-span-1">
              <PlayerRank />
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="mt-16 py-6 text-center text-purple-300 text-sm">
          <p>LeaderForge v1.0 - Built with FastAPI, React, PostgreSQL & Redis</p>
        </footer>
      </div>
    </QueryClientProvider>
  )
}

export default App
