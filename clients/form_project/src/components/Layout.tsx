import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, LogOut, User } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, logout } = useAuth();
  const isAdmin = location.pathname.startsWith('/admin');

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-brand-blue text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <BookOpen className="w-6 h-6" />
            <span className="font-semibold text-lg">Onsite Training Assessment System</span>
          </div>
          {isAdmin && isAuthenticated && (
            <nav className="flex items-center space-x-4">
              <Link to="/admin" className="text-white hover:text-blue-200 px-3 py-2 rounded-md text-sm font-medium">
                Dashboard
              </Link>
              <div className="flex items-center gap-3 border-l border-blue-400/40 pl-4">
                <div className="flex items-center gap-1.5 text-blue-100 text-sm">
                  <User className="w-4 h-4" />
                  <span>{user?.username}</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 text-white text-sm px-3 py-1.5 rounded-lg transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </div>
            </nav>
          )}
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      <footer className="bg-white border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-center">
          <p className="text-sm text-gray-500">&copy; {new Date().getFullYear()} Onsite Training Assessment System</p>
        </div>
      </footer>
    </div>
  );
}
