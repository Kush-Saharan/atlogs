import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Boxes,
  CalendarClock,
  ClipboardCheck,
  FileText,
  Home,
  LogOut,
  Users,
  PanelLeft,
  Plug,
  Wrench,
  Share2,
  SquareStack,
  type LucideIcon,
  ScrollText,
} from 'lucide-react'

import { useAuth } from '@/lib/session'
import { cn } from '@/lib/utils'
import { ShaderBackground } from '@/components/ShaderBackground'

interface NavItem {
  to: string
  label: string
  short: string
  icon: LucideIcon
}

const PRIMARY: NavItem[] = [
  { to: '/', label: 'Home', short: 'Home', icon: Home },
  { to: '/graph', label: 'Knowledge graph', short: 'Graph', icon: Share2 },
  { to: '/workflows', label: 'Workflows', short: 'Work', icon: SquareStack },
]

const SECONDARY: NavItem[] = [
  { to: '/logs', label: 'Logs', short: 'Logs', icon: FileText },
  { to: '/connectors', label: 'Connectors', short: 'Sources', icon: Plug },
  { to: '/assets', label: 'Assets', short: 'Assets', icon: Boxes },
  { to: '/review', label: 'Review queue', short: 'Review', icon: ClipboardCheck },
]

function Brand() {
  // Text wordmark (same script stack as favicon.svg) in the brand primary token.
  return (
    <div
      className="flex items-center select-none text-primary"
      style={{
        width: 122,
        height: 52,
        fontFamily: "'Segoe Script','Brush Script MT','Snell Roundhand',cursive",
        fontSize: 30,
        fontWeight: 600,
      }}
    >
      atlogs
    </div>
  )
}

function SideNavLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          'group relative flex items-center rounded-xl text-sm font-medium transition-colors',
          collapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2.5',
          isActive
            ? 'bg-secondary text-foreground'
            : 'text-muted-foreground hover:bg-secondary/70 hover:text-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={cn(
              'absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-full bg-primary transition-opacity',
              isActive ? 'opacity-100' : 'opacity-0',
            )}
            aria-hidden
          />
          <Icon
            className={cn('size-4.5 shrink-0', isActive && 'text-primary')}
            aria-hidden
          />
          {!collapsed && item.label}
        </>
      )}
    </NavLink>
  )
}

function BottomTab({ item }: { item: NavItem }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'flex flex-1 flex-col items-center justify-center gap-1 rounded-lg py-1.5 text-[11px] font-medium transition-colors',
          isActive ? 'text-primary' : 'text-muted-foreground',
        )
      }
    >
      <Icon className="size-5" aria-hidden />
      {item.short}
    </NavLink>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem('atlas.sidebar.collapsed') === '1'
  })
  useEffect(() => {
    localStorage.setItem('atlas.sidebar.collapsed', collapsed ? '1' : '0')
  }, [collapsed])

  return (
    <div
      className="min-h-svh"
      style={{ ['--sidebar-w' as string]: collapsed ? '4.5rem' : '16rem' }}
    >
      {/* Animated shader background — sits behind everything, ignores input */}
      <ShaderBackground />

      {/* Desktop sidebar — a frosted card-surface panel, collapsible to a rail */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 hidden flex-col gap-6 border-r border-border/60 bg-card/80 py-5 backdrop-blur-md transition-[width,padding] duration-200 ease-out md:flex',
          collapsed ? 'w-[4.5rem] px-2' : 'w-64 px-4',
        )}
      >
        <div
          className={cn(
            'flex items-center',
            collapsed ? 'justify-center' : 'justify-between px-2',
          )}
        >
          {!collapsed && <Brand />}
          <button
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <PanelLeft className="size-4.5" />
          </button>
        </div>
        <nav className="flex flex-col gap-1">
          {PRIMARY.map((item) => (
            <SideNavLink key={item.to} item={item} collapsed={collapsed} />
          ))}
        </nav>
        <div className="flex flex-col gap-1">
          {!collapsed && (
            <p className="px-3 pb-1 text-xs font-medium text-muted-foreground/70">
              Records
            </p>
          )}
          {SECONDARY.map((item) => (
            <SideNavLink key={item.to} item={item} collapsed={collapsed} />
          ))}
          {user.role !== 'engineer' && (
            <SideNavLink
              item={{ to: '/schedule', label: 'Schedule', short: 'Schedule', icon: CalendarClock }}
              collapsed={collapsed}
            />
          )}
          {user.role !== 'engineer' && (
            <SideNavLink
              item={{ to: '/audit', label: 'Audit', short: 'Audit', icon: ScrollText }}
              collapsed={collapsed}
            />
          )}
          {user.role !== 'engineer' && (
            <SideNavLink
              item={{ to: '/resources', label: 'Resources', short: 'Resources', icon: Wrench }}
              collapsed={collapsed}
            />
          )}
          {user.role === 'admin' && (
            <SideNavLink
              item={{ to: '/admin/users', label: 'Users', short: 'Users', icon: Users }}
              collapsed={collapsed}
            />
          )}
        </div>
        <div className="mt-auto flex flex-col gap-1 px-1">
          {!collapsed && (
            <p className="truncate px-2 text-xs text-muted-foreground" title={user.email}>
              {user.email} ({user.role})
            </p>
          )}
          <button
            onClick={logout}
            title="Sign out"
            className={cn(
              'flex items-center rounded-xl py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground',
              collapsed ? 'justify-center' : 'gap-3 px-3',
            )}
          >
            <LogOut className="size-4.5" aria-hidden />
            {!collapsed && 'Sign out'}
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center border-b border-border/70 bg-background/85 px-4 py-3 backdrop-blur md:hidden">
        <Brand />
        <button onClick={logout} aria-label="Sign out" className="ml-auto p-2 text-muted-foreground">
          <LogOut className="size-5" aria-hidden />
        </button>
      </header>

      {/* Main content — margin follows the sidebar width via the CSS var */}
      <main className="px-4 pb-24 pt-6 transition-[margin] duration-200 ease-out md:ml-[var(--sidebar-w)] md:px-8 md:pb-10 lg:px-12">
        <div className="mx-auto w-full max-w-6xl">{children}</div>
      </main>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex items-stretch gap-1 border-t border-border/70 bg-background/90 px-2 py-1.5 backdrop-blur md:hidden">
        {PRIMARY.map((item) => (
          <BottomTab key={item.to} item={item} />
        ))}
      </nav>
    </div>
  )
}
