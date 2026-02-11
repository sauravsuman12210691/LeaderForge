import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { leaderboardAPI } from '../api/client'

const PlayerRank = () => {
  const [userId, setUserId] = useState('')
  const [searchUserId, setSearchUserId] = useState(null)

  const { data, isLoading, error, isError } = useQuery({
    queryKey: ['playerRank', searchUserId],
    queryFn: () => leaderboardAPI.getPlayerRank(searchUserId),
    enabled: searchUserId !== null && searchUserId > 0,
    retry: false,
  })

  const handleSearch = (e) => {
    e.preventDefault()
    const id = parseInt(userId)
    if (!isNaN(id) && id > 0) {
      setSearchUserId(id)
    }
  }

  const getRankBadgeColor = (rank) => {
    if (rank === 1) return 'from-yellow-400 to-yellow-600'
    if (rank === 2) return 'from-gray-300 to-gray-500'
    if (rank === 3) return 'from-orange-400 to-orange-600'
    if (rank <= 10) return 'from-purple-400 to-purple-600'
    if (rank <= 100) return 'from-blue-400 to-blue-600'
    return 'from-green-400 to-green-600'
  }

  return (
    <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-2xl p-8 shadow-2xl border border-purple-500/20 h-fit">
      {/* Header */}
      <h2 className="text-2xl font-bold text-white mb-6">Player Rank Lookup</h2>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex space-x-2">
          <input
            type="number"
            placeholder="Enter User ID..."
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="flex-1 px-4 py-3 bg-purple-500/20 border border-purple-500/30 rounded-lg text-white placeholder-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
            min="1"
          />
          <button
            type="submit"
            className="px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all duration-300 transform hover:scale-105"
          >
            Search
          </button>
        </div>
      </form>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto"></div>
          <p className="text-purple-300 mt-4">Loading player data...</p>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
          <p className="text-red-400 font-semibold mb-2">Player Not Found</p>
          <p className="text-red-300 text-sm">
            {error.response?.status === 404
              ? 'This player has not played any games yet.'
              : 'An error occurred while fetching player data.'}
          </p>
        </div>
      )}

      {/* Player Data */}
      {data && !isLoading && (
        <div className="space-y-6 animate-fade-in">
          {/* Rank Badge */}
          <div className="text-center">
            <div
              className={`inline-block bg-gradient-to-br ${getRankBadgeColor(
                data.rank
              )} rounded-full p-1 mb-4`}
            >
              <div className="bg-slate-900 rounded-full px-8 py-6">
                <p className="text-sm text-purple-300 mb-1">Rank</p>
                <p className="text-5xl font-bold text-white">#{data.rank}</p>
              </div>
            </div>
          </div>

          {/* Player Stats */}
          <div className="space-y-4">
            {/* Username */}
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <p className="text-sm text-purple-300 mb-1">Username</p>
              <p className="text-xl font-semibold text-white">{data.username}</p>
            </div>

            {/* Total Score */}
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <p className="text-sm text-purple-300 mb-1">Total Score</p>
              <p className="text-2xl font-bold text-white">
                {data.total_score.toLocaleString()}
              </p>
            </div>

            {/* Games Played */}
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <p className="text-sm text-purple-300 mb-1">Games Played</p>
              <p className="text-xl font-semibold text-white">{data.session_count}</p>
            </div>

            {/* Percentile */}
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <p className="text-sm text-purple-300 mb-1">Percentile</p>
              <div className="flex items-center space-x-3">
                <div className="flex-1 bg-purple-900/50 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-green-400 to-blue-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(data.percentile, 100)}%` }}
                  ></div>
                </div>
                <span className="text-white font-semibold">
                  Top {data.percentile.toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Average Score Per Game */}
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <p className="text-sm text-purple-300 mb-1">Avg Score/Game</p>
              <p className="text-xl font-semibold text-white">
                {Math.round(data.total_score / data.session_count).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Achievement Badge */}
          {data.rank <= 10 && (
            <div className="bg-gradient-to-r from-yellow-500/20 to-orange-500/20 rounded-lg p-4 border border-yellow-500/30 text-center">
              <p className="text-yellow-400 font-semibold">Top 10 Player!</p>
              <p className="text-sm text-yellow-300 mt-1">Keep up the great work!</p>
            </div>
          )}
        </div>
      )}

      {/* Instructions */}
      {!searchUserId && !isLoading && (
        <div className="text-center py-8">
          <div className="text-6xl mb-4">🔍</div>
          <p className="text-purple-300">
            Enter a User ID to see their rank and stats
          </p>
          <p className="text-sm text-purple-400 mt-2">
            Try IDs between 1 and 1,000,000
          </p>
        </div>
      )}
    </div>
  )
}

export default PlayerRank
