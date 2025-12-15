import Head from 'next/head'
import { useEffect, useState } from 'react'
import axios from 'axios'
import Dashboard from '../components/Dashboard'
import Header from '../components/Header'

// Dynamic API URL - use container name for SSR, localhost for client-side
const getApiUrl = () => {
  if (typeof window === 'undefined') {
    // Server-side (SSR) - use container name
    return 'http://backend:8000'
  }
  // Client-side (browser) - use localhost
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
}

export default function Home() {
  const [user_id, setUserId] = useState(1) // TODO: Replace with actual auth
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchStats = async () => {
    try {
      const apiUrl = getApiUrl()
      const response = await axios.get(`${apiUrl}/api/dashboard/stats`, {
        params: { user_id }
      })
      setStats(response.data.data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
    // Light polling so extension-driven updates show up without refresh.
    const id = setInterval(() => {
      fetchStats()
    }, 15000)
    return () => clearInterval(id)
  }, [user_id])

  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>Job Scout AI - Application Tracker</title>
        <meta name="description" content="AI-powered job discovery and application tracker" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <Header />

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900">Job Scout AI</h1>
          <p className="text-gray-600 mt-2">Your AI-powered job application companion</p>
        </div>

        {loading && <p className="text-center text-gray-600">Loading...</p>}
        {error && <p className="text-center text-red-600">Error: {error}</p>}
        {stats && <Dashboard stats={stats} user_id={user_id} onRefreshStats={fetchStats} />}
      </main>
    </div>
  )
}

