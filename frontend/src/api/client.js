import axios from 'axios'

// Use relative URL when running in Docker (via Vite proxy) or absolute URL for local dev
// Vite proxy handles /api requests when VITE_API_URL is not set or empty
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false, // Set to true if using cookies/auth
})

// API functions
export const leaderboardAPI = {
  // Get top players
  getTopPlayers: async (limit = 10) => {
    const response = await apiClient.get(`/api/leaderboard/top?limit=${limit}`)
    return response.data
  },

  // Get player rank
  getPlayerRank: async (userId) => {
    const response = await apiClient.get(`/api/leaderboard/rank/${userId}`)
    return response.data
  },

  // Submit score
  submitScore: async (userId, score) => {
    const response = await apiClient.post('/api/scores', {
      user_id: userId,
      score: score,
    })
    return response.data
  },

  // Health check
  healthCheck: async () => {
    const response = await apiClient.get('/api/leaderboard/health')
    return response.data
  },
}

export default apiClient
