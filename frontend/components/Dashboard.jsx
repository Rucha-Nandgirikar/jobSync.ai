import { useEffect, useState } from 'react'
import axios from 'axios'

// Dynamic API URL - use container name for SSR, localhost for client-side
const getApiUrl = () => {
  if (typeof window === 'undefined') {
    // Server-side (SSR) - use container name
    return 'http://backend:8000'
  }
  // Client-side (browser) - use localhost
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
}

export default function Dashboard({ stats, user_id, onRefreshStats }) {
  const [applications, setApplications] = useState([])
  const [jobs, setJobs] = useState([])
  const [resumes, setResumes] = useState([])
  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [loading, setLoading] = useState(false)
  const [jobsLoading, setJobsLoading] = useState(false)
  const [crawling, setCrawling] = useState(false)
  const [crawlMessage, setCrawlMessage] = useState('')
  const [jobsPage, setJobsPage] = useState(1)
  const [jobsLimit, setJobsLimit] = useState(50)
  const [jobsPagination, setJobsPagination] = useState({})
  const [jobsTag, setJobsTag] = useState('all') // all | applied | remaining | skipped
  const [exporting, setExporting] = useState(false)

  const fetchResumes = async () => {
    try {
      const apiUrl = getApiUrl()
      const response = await axios.get(`${apiUrl}/api/generate/resumes`, {
        params: { user_id: user_id || 1 }
      })
      const list = response.data.data || []
      setResumes(list)
      if (!selectedResumeId && list.length) {
        setSelectedResumeId(String(list[0].id))
      }
    } catch (err) {
      console.error('Error fetching resumes:', err)
      setResumes([])
    }
  }

  const fetchJobs = async (page = jobsPage, limit = jobsLimit, tag = jobsTag) => {
    setJobsLoading(true)
    try {
      const apiUrl = getApiUrl()
      const response = await axios.get(`${apiUrl}/api/dashboard/jobs`, {
        params: { 
          user_id: user_id || 1, 
          page: page,
          limit: limit, 
          is_active: 'true',
          tag: tag
        }
      })
      setJobs(response.data.data || [])
      setJobsPagination(response.data.pagination || {})
    } catch (err) {
      console.error('Error fetching jobs:', err)
    } finally {
      setJobsLoading(false)
    }
  }

  const fetchApplications = async () => {
    setLoading(true)
    try {
      const apiUrl = getApiUrl()
      const response = await axios.get(`${apiUrl}/api/dashboard/applications`, {
        params: { user_id, limit: 10 }
      })
      setApplications(response.data.data || [])
    } catch (err) {
      console.error('Error fetching applications:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async (job) => {
    try {
      if (!selectedResumeId) {
        alert('Upload/select a resume first.')
        return
      }
      const apiUrl = getApiUrl()
      // MVP: mark as submitted immediately (stamps applied_at server-side)
      await axios.post(`${apiUrl}/api/dashboard/applications`, {
        user_id: user_id || 1,
        job_id: job.id,
        resume_id: parseInt(selectedResumeId, 10),
        status: 'submitted'
      })
      await fetchJobs()
      await fetchApplications()
      if (onRefreshStats) onRefreshStats()
    } catch (err) {
      console.error('Apply error:', err)
      alert(err.response?.data?.detail || err.message)
    }
  }

  const handleSkip = async (job) => {
    try {
      const apiUrl = getApiUrl()
      const reason = window.prompt('Reason (optional):', 'Not a fit') || ''
      await axios.post(`${apiUrl}/api/dashboard/jobs/${job.id}/flag`, {
        user_id: user_id || 1,
        flag: 'skipped',
        reason: reason.trim() || null
      })
      await fetchJobs()
    } catch (err) {
      console.error('Skip error:', err)
      alert(err.response?.data?.detail || err.message)
    }
  }

  const handleExport = async () => {
    try {
      setExporting(true)
      const apiUrl = getApiUrl()
      const url = `${apiUrl}/api/dashboard/applications/export?user_id=${user_id || 1}&format=xlsx`
      window.open(url, '_blank')
    } finally {
      setExporting(false)
    }
  }

  const handleCrawl = async () => {
    setCrawling(true)
    setCrawlMessage('Starting crawl...')
    try {
      const apiUrl = getApiUrl()
      const response = await axios.post(`${apiUrl}/api/crawl/trigger`)
      setCrawlMessage(`Success! ${response.data.message || 'Crawl started'}`)
      
      // Wait a bit, then refresh jobs
      setTimeout(() => {
        fetchJobs()
        fetchApplications()
        if (onRefreshStats) onRefreshStats()
      }, 3000)
      
      // Clear message after 5 seconds
      setTimeout(() => {
        setCrawlMessage('')
      }, 5000)
    } catch (err) {
      console.error('Crawl error:', err)
      setCrawlMessage(`Error: ${err.response?.data?.detail || err.message}`)
      setTimeout(() => {
        setCrawlMessage('')
      }, 5000)
    } finally {
      setCrawling(false)
    }
  }

  useEffect(() => {
    fetchApplications()
    fetchJobs()
    fetchResumes()
  }, [user_id])
  
  useEffect(() => {
    fetchJobs(jobsPage, jobsLimit, jobsTag)
  }, [jobsPage, jobsLimit, jobsTag])

  return (
    <div className="space-y-8">
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard label="Total" value={stats?.total_applications || 0} color="blue" />
        <StatCard label="Submitted" value={stats?.submitted || 0} color="green" />
        <StatCard label="Reviewed" value={stats?.reviewed || 0} color="yellow" />
        <StatCard label="Interviewed" value={stats?.interviewed || 0} color="purple" />
        <StatCard label="Offered" value={stats?.offered || 0} color="green" />
        <StatCard label="Rejected" value={stats?.rejected || 0} color="red" />
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Quick Actions</h2>
        {crawlMessage && (
          <div className={`mb-4 p-3 rounded ${crawlMessage.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
            {crawlMessage}
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button 
            onClick={handleCrawl}
            disabled={crawling}
            className={`px-4 py-2 rounded text-white font-medium ${
              crawling 
                ? 'bg-blue-400 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {crawling ? '⏳ Crawling...' : '🚀 Crawl Job Boards'}
          </button>
          <button className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
            📄 Upload Resume
          </button>
          <button className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700">
            ✉️ Generate Cover Letter
          </button>
        </div>
        <div className="mt-4 flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Default resume:</span>
            <select
              value={selectedResumeId}
              onChange={(e) => setSelectedResumeId(e.target.value)}
              className="border rounded px-2 py-1 text-sm"
              disabled={!resumes.length}
            >
              {!resumes.length ? (
                <option value="">No resumes (upload first)</option>
              ) : (
                resumes.map((r) => (
                  <option key={r.id} value={String(r.id)}>
                    {r.id} — {r.filename} ({r.role || 'role'})
                  </option>
                ))
              )}
            </select>
          </div>
          <button
            onClick={handleExport}
            disabled={exporting}
            className={`px-4 py-2 rounded text-white font-medium ${
              exporting ? 'bg-gray-400 cursor-not-allowed' : 'bg-gray-800 hover:bg-gray-900'
            }`}
          >
            {exporting ? 'Preparing...' : '⬇️ Export Applications (Excel)'}
          </button>
        </div>
      </div>

      {/* Available Jobs */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold">Available Jobs ({jobsPagination.total || jobs.length})</h2>
              <p className="text-sm text-gray-500 mt-1">Engineering roles from your target companies</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 mr-2">Filter:</span>
              <button
                onClick={() => { setJobsTag('all'); setJobsPage(1); }}
                className={`px-3 py-1 rounded-full text-sm border ${
                  jobsTag === 'all'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                All
              </button>
              <button
                onClick={() => { setJobsTag('remaining'); setJobsPage(1); }}
                className={`px-3 py-1 rounded-full text-sm border ${
                  jobsTag === 'remaining'
                    ? 'bg-green-600 text-white border-green-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Remaining
              </button>
              <button
                onClick={() => { setJobsTag('applied'); setJobsPage(1); }}
                className={`px-3 py-1 rounded-full text-sm border ${
                  jobsTag === 'applied'
                    ? 'bg-purple-600 text-white border-purple-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Applied
              </button>
              <button
                onClick={() => { setJobsTag('skipped'); setJobsPage(1); }}
                className={`px-3 py-1 rounded-full text-sm border ${
                  jobsTag === 'skipped'
                    ? 'bg-gray-800 text-white border-gray-800'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Skipped
              </button>
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Title</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Company</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Department</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Location</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Posted</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Action</th>
              </tr>
            </thead>
            <tbody>
              {jobsLoading ? (
                <tr>
                  <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                    Loading jobs...
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                    No jobs found yet. Click "Crawl Job Boards" to fetch engineering roles!
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="border-b hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-medium">
                        {job.title}
                      </a>
                      <div className="mt-1">
                        {job.user_flag ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-800">
                            Skipped
                          </span>
                        ) : job.application_count > 0 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                            Applied
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                            To apply
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">{job.company}</td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm">
                        {job.department || 'Engineering'}
                      </span>
                    </td>
                    <td className="px-6 py-4">{job.location || 'Remote'}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {job.posting_date ? new Date(job.posting_date).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="px-6 py-4">
                      {job.user_flag ? (
                        <span className="text-sm text-gray-500">Skipped</span>
                      ) : job.application_count > 0 ? (
                        <span className="text-sm text-gray-500">Applied</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleApply(job)}
                            disabled={!selectedResumeId}
                            className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700 disabled:opacity-60"
                          >
                            Mark Applied
                          </button>
                          <button
                            onClick={() => handleSkip(job)}
                            className="bg-gray-200 text-gray-800 px-3 py-1 rounded text-sm hover:bg-gray-300"
                          >
                            Skip
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination Controls */}
        {jobsPagination.total > 0 && (
          <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-700">
                Showing {Math.min((jobsPage - 1) * jobsLimit + 1, jobsPagination.total)} to {Math.min(jobsPage * jobsLimit, jobsPagination.total)} of {jobsPagination.total} jobs
              </span>
              
              <select 
                value={jobsLimit} 
                onChange={(e) => { setJobsLimit(Number(e.target.value)); setJobsPage(1); }}
                className="border border-gray-300 rounded px-3 py-1 text-sm"
              >
                <option value="20">20 per page</option>
                <option value="50">50 per page</option>
                <option value="100">100 per page</option>
                <option value="200">200 per page</option>
                <option value="500">All (500)</option>
              </select>
            </div>
            
            <div className="flex gap-2">
              <button
                onClick={() => setJobsPage(Math.max(1, jobsPage - 1))}
                disabled={jobsPage === 1}
                className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              
              <span className="px-4 py-2 text-sm font-medium">
                Page {jobsPage} of {jobsPagination.total_pages || 1}
              </span>
              
              <button
                onClick={() => setJobsPage(Math.min(jobsPagination.total_pages || 1, jobsPage + 1))}
                disabled={jobsPage >= (jobsPagination.total_pages || 1)}
                className="px-4 py-2 border border-gray-300 rounded text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Recent Applications */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b">
          <h2 className="text-xl font-bold">Recent Applications</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Job</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Company</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Location</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Status</th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Date</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="5" className="px-6 py-4 text-center text-gray-500">
                    Loading...
                  </td>
                </tr>
              ) : applications.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-6 py-4 text-center text-gray-500">
                    No applications yet. Start by uploading a resume and crawling job boards!
                  </td>
                </tr>
              ) : (
                applications.map((app) => (
                  <tr key={app.id} className="border-b hover:bg-gray-50">
                    <td className="px-6 py-4">{app.title}</td>
                    <td className="px-6 py-4">{app.company}</td>
                    <td className="px-6 py-4">{app.location}</td>
                    <td className="px-6 py-4">
                      <StatusBadge status={app.status} />
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {new Date(app.applied_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    purple: 'bg-purple-50 text-purple-600',
    red: 'bg-red-50 text-red-600',
  }

  return (
    <div className={`${colorClasses[color] || colorClasses.blue} rounded-lg p-4`}>
      <p className="text-sm font-medium">{label}</p>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  )
}

function StatusBadge({ status }) {
  const statusStyles = {
    submitted: 'bg-blue-100 text-blue-700',
    reviewed: 'bg-yellow-100 text-yellow-700',
    interviewed: 'bg-purple-100 text-purple-700',
    offered: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
    draft: 'bg-gray-100 text-gray-700',
  }

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusStyles[status] || statusStyles.draft}`}>
      {status?.charAt(0).toUpperCase() + status?.slice(1)}
    </span>
  )
}

