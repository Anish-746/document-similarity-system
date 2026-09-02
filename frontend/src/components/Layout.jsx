import { Outlet, NavLink } from 'react-router-dom';
import { Fingerprint, LayoutDashboard, ListTree } from 'lucide-react';

export default function Layout() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 glass-panel border-x-0 border-t-0 rounded-none rounded-b-2xl bg-slate-900/60 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            
            {/* Logo */}
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-linear-to-tr from-neon-blue to-neon-purple shadow-[0_0_15px_rgba(139,92,246,0.3)]">
                <Fingerprint className="text-white w-6 h-6" />
              </div>
              <span className="text-xl font-bold tracking-tight text-white ml-2">
                Simila<span className="text-gradient">ry</span>
              </span>
            </div>

            {/* Navigation Links */}
            <div className="flex items-center gap-6">
              <NavLink
                to="/"
                className={({ isActive }) =>
                  `flex items-center gap-2 text-sm font-medium transition-colors ${
                    isActive ? 'text-white' : 'text-slate-400 hover:text-slate-200'
                  }`
                }
              >
                <LayoutDashboard className="w-4 h-4" />
                Dashboard
              </NavLink>
              
              <NavLink
                to="/pairs"
                className={({ isActive }) =>
                  `flex items-center gap-2 text-sm font-medium transition-colors ${
                    isActive ? 'text-white' : 'text-slate-400 hover:text-slate-200'
                  }`
                }
              >
                <ListTree className="w-4 h-4" />
                Results
              </NavLink>
            </div>
            
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <Outlet />
      </main>
    </div>
  );
}
