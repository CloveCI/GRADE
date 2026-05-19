import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  KeyRound,
  FileScan,
  PlayCircle,
  ClipboardList,
  BarChart3,
  Search,
  GraduationCap,
  Package,
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

const primaryNav = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Metrics", url: "/metrics", icon: BarChart3 },
];

const portalNav = [
  { title: "Upload bundle", url: "/upload/bundle", icon: Package },
  { title: "Keys", url: "/keys", icon: KeyRound },
  { title: "Sheets", url: "/sheets", icon: FileScan },
  { title: "Evaluate", url: "/evaluate", icon: PlayCircle },
  { title: "Results", url: "/results", icon: ClipboardList },
];

const toolsNav = [{ title: "RAG Explorer", url: "/rag", icon: Search }];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const { pathname } = useLocation();

  const isActive = (path: string) =>
    path === "/" ? pathname === "/" : pathname === path || pathname.startsWith(path + "/");

  const renderItem = (item: { title: string; url: string; icon: typeof KeyRound }) => (
    <SidebarMenuItem key={item.title}>
      <SidebarMenuButton asChild isActive={isActive(item.url)} tooltip={item.title}>
        <NavLink to={item.url} end={item.url === "/"} className="flex items-center gap-2">
          <item.icon className="h-4 w-4 shrink-0" />
          {!collapsed && <span>{item.title}</span>}
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
            <GraduationCap className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold tracking-tight text-sidebar-foreground">GRADE</span>
              <span className="text-[10px] uppercase tracking-wider text-sidebar-foreground/60">
                Autograder
              </span>
            </div>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Overview</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{primaryNav.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Portals</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{portalNav.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Tools</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{toolsNav.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}