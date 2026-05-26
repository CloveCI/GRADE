import { Link, useRouterState } from "@tanstack/react-router";
import {
  GraduationCap,
  LayoutDashboard,
  BarChart3,
  Package,
  KeyRound,
  FileScan,
  PlayCircle,
  ClipboardCheck,
  Database,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

type NavItem = { title: string; url: string; icon: typeof GraduationCap };

const OVERVIEW: NavItem[] = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Metrics", url: "/metrics", icon: BarChart3 },
];

const PORTALS: NavItem[] = [
  { title: "Upload bundle", url: "/upload/bundle", icon: Package },
  { title: "Answer keys", url: "/keys", icon: KeyRound },
  { title: "Sheets", url: "/sheets", icon: FileScan },
  { title: "Evaluate", url: "/evaluate", icon: PlayCircle },
  { title: "Results", url: "/results", icon: ClipboardCheck },
];

const TOOLS: NavItem[] = [{ title: "RAG Explorer", url: "/rag", icon: Database }];

function NavSection({ label, items, currentPath }: { label: string; items: NavItem[]; currentPath: string }) {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => {
            const active =
              item.url === "/"
                ? currentPath === "/"
                : currentPath === item.url || currentPath.startsWith(item.url + "/");
            return (
              <SidebarMenuItem key={item.url}>
                <SidebarMenuButton asChild isActive={active} tooltip={item.title}>
                  <Link to={item.url} className="flex items-center gap-2">
                    <item.icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span>{item.title}</span>}
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const currentPath = useRouterState({ select: (s) => s.location.pathname });

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-3 px-2 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 ring-1 ring-primary/40">
            <GraduationCap className="h-5 w-5 text-primary" />
          </div>
          {!collapsed && (
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold tracking-wide text-foreground">GRADE</span>
              <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Autograder
              </span>
            </div>
          )}
        </div>
      </SidebarHeader>
      <SidebarContent>
        <NavSection label="Overview" items={OVERVIEW} currentPath={currentPath} />
        <NavSection label="Portals" items={PORTALS} currentPath={currentPath} />
        <NavSection label="Tools" items={TOOLS} currentPath={currentPath} />
      </SidebarContent>
    </Sidebar>
  );
}
