import { useQuery } from '@tanstack/react-query'
import { leaderboardAPI } from '../api/client'
import { useState, useEffect } from 'react'

const Leaderboard = () => {
  const [previousRanks, setPreviousRanks] = useState({})

  const { data, isLoading, error, isError } = useQuery({
    queryKey: ['topPlayers'],
    queryFn: () => leaderboardAPI.getTopPlayers(10),
    refetchInterval: 5000,
  })

  useEffect(() => {
    if (data?.top_players) {
      const newRanks = {}
      data.top_players.forEach(player => {
        newRanks[player.user_id] = player.rank
      })
      setPreviousRanks(newRanks)
    }
  }, [data])

  const getRankChange = (userId, currentRank) => {
    const prevRank = previousRanks[userId]
    if (!prevRank || prevRank === currentRank) return null
    return prevRank - currentRank // Positive means moved up
  }

  const getMedalEmoji = (rank) => {
    switch (rank) {
      case 1:
        return '🥇'
      case 2:
        return '🥈'
      case 3:
        return '🥉'
      default:
        return null
    }
  }

  if (isLoading) {
    return (
      <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-2xl p-8 shadow-2xl border border-purple-500/20">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-purple-500/20 rounded w-1/3"></div>
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-16 bg-purple-500/10 rounded"></div>
          ))}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="bg-red-500 bg-opacity-10 backdrop-blur-md rounded-2xl p-8 shadow-2xl border border-red-500/20">
        <h2 className="text-2xl font-bold text-red-400 mb-4">Error Loading Leaderboard</h2>
        <p className="text-red-300">{error.message}</p>
      </div>
    )
  }

  return (
    <div className="bg-white bg-opacity-10 backdrop-blur-md rounded-2xl p-8 shadow-2xl border border-purple-500/20">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-3xl font-bold text-white">Top Players</h2>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
          <span className="text-sm text-purple-300">Live</span>
        </div>
      </div>

      {/* Stats */}
      <div className="mb-6 text-sm text-purple-300">
        <p>Total Players: {data?.total_players?.toLocaleString() || 0}</p>
        <p className="text-xs mt-1">Updated: {new Date(data?.timestamp).toLocaleTimeString()}</p>
      </div>

      {/* Leaderboard Table */}
      <div className="space-y-2">
        {data?.top_players?.map((player, index) => {
          const rankChange = getRankChange(player.user_id, player.rank)
          const medal = getMedalEmoji(player.rank)

          return (
            <div
              key={player.user_id}
              className={`
                flex items-center justify-between p-4 rounded-xl
                ${player.rank <= 3 ? 'bg-gradient-to-r from-yellow-500/20 to-orange-500/20' : 'bg-purple-500/10'}
                hover:bg-purple-500/20 transition-all duration-300
                border border-purple-500/10 hover:border-purple-500/30
                transform hover:scale-[1.02]
              `}
            >
              {/* Rank and Medal */}
              <div className="flex items-center space-x-4 flex-1">
                <div className="flex items-center justify-center w-12 h-12 rounded-full bg-purple-600/30 text-white font-bold">
                  {medal || player.rank}
                </div>

                {/* Player Info */}
                <div className="flex-1">
                  <h3 className="text-white font-semibold text-lg">
                    {player.username}
                  </h3>
                  <p className="text-purple-300 text-sm">
                    {player.session_count} games played
                  </p>
                </div>

                {/* Score */}
                <div className="text-right">
                  <p className="text-2xl font-bold text-white">
                    {player.total_score.toLocaleString()}
                  </p>
                  <p className="text-xs text-purple-300">points</p>
                </div>

                {/* Rank Change Indicator */}
                {rankChange !== null && (
                  <div className="ml-4">
                    {rankChange > 0 ? (
                      <span className="text-green-400 text-sm flex items-center">
                        ↑ {rankChange}
                      </span>
                    ) : rankChange < 0 ? (
                      <span className="text-red-400 text-sm flex items-center">
                        ↓ {Math.abs(rankChange)}
                      </span>
                    ) : null}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Empty State */}
      {(!data?.top_players || data.top_players.length === 0) && (
        <div className="text-center py-12 text-purple-300">
          <p className="text-xl">No players yet!</p>
          <p className="text-sm mt-2">Be the first to submit a score.</p>
        </div>
      )}
    </div>
  )
}

export default Leaderboard
