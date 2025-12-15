import Link from 'next/link'

export default function Header() {
  return (
    <header className="bg-white shadow">
      <nav className="container mx-auto px-4 py-4 flex justify-between items-center">
        <div className="flex items-center gap-8">
          <Link href="/">
            <div className="text-2xl font-bold text-blue-600">🔍 JobScout</div>
          </Link>
          <div className="hidden md:flex gap-6">
            <Link href="/dashboard" className="text-gray-600 hover:text-blue-600">
              Dashboard
            </Link>
            <Link href="/applications" className="text-gray-600 hover:text-blue-600">
              Applications
            </Link>
            <Link href="/resumes" className="text-gray-600 hover:text-blue-600">
              Resumes
            </Link>
            <Link href="/jobs" className="text-gray-600 hover:text-blue-600">
              Jobs
            </Link>
          </div>
        </div>
        <button className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          Settings
        </button>
      </nav>
    </header>
  )
}


