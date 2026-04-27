/**
 * Sidebar Navigation Component
 */
import { NavLink } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useBusinessStore } from '@/store/businessStore'
import {
  LayoutDashboard,
  Calendar,
  Users,
  Scissors,
  Clock,
  CalendarClock,
  LogOut,
  Store,
  MessageCircle,
} from 'lucide-react'
import { cn } from '@/utils/cn'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Calendario', href: '/calendar', icon: Calendar },
  { name: 'Citas', href: '/appointments', icon: Clock },
  { name: 'Clientes', href: '/customers', icon: Users },
  { name: 'Servicios', href: '/services', icon: Scissors },
  { name: 'Horarios', href: '/schedule', icon: CalendarClock },
  { name: 'Telegram', href: '/telegram', icon: MessageCircle },
]

export default function Sidebar({ onItemClick }: { onItemClick?: () => void }) {
  const { user, logout } = useAuthStore()
  const { currentBusiness } = useBusinessStore()

  const handleLogout = async () => {
    await logout()
    window.location.href = '/login'
  }

  return (
    <div className="flex flex-col h-full w-full bg-card text-card-foreground">
      {/* Logo */}
      <div className="flex items-center h-16 px-6 border-b border-border/40">
        <div className="p-2 bg-primary/10 rounded-lg mr-3">
          <Store className="w-6 h-6 text-primary" />
        </div>
        <span className="text-lg font-bold tracking-tight">SmartBooking</span>
      </div>

      {/* Business Selector */}
      {currentBusiness && (
        <div className="px-4 py-4 mx-2 mt-2 bg-muted/30 rounded-lg border border-border/20">
          <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Negocio actual</div>
          <div className="mt-1 font-medium truncate text-sm">{currentBusiness.name}</div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            onClick={onItemClick}
            className={({ isActive }) =>
              cn(
                'flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 group',
                isActive
                  ? 'bg-primary/10 text-primary shadow-sm'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              )
            }
          >
            <item.icon className={cn("w-5 h-5 mr-3 transition-colors", ({ isActive }: { isActive: boolean }) => isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground')} />
            {item.name}
          </NavLink>
        ))}
      </nav>

      {/* User Section */}
      <div className="p-4 border-t border-border/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 bg-primary/20 text-primary rounded-full flex items-center justify-center ring-2 ring-background">
              <span className="text-sm font-bold">
                {user?.name?.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.name}</p>
              <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
