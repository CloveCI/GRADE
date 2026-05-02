import { Outlet, useLocation } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { Separator } from "@/components/ui/separator";

const routeTitles: Record<string, string> = {
  "/": "Dashboard",
  "/keys": "Keys",
  "/sheets": "Sheets",
  "/evaluate": "Evaluate",
  "/results": "Results",
  "/metrics": "Metrics",
  "/rag": "RAG Explorer",
};

function getTitle(pathname: string) {
  if (routeTitles[pathname]) return routeTitles[pathname];
  const base = "/" + pathname.split("/")[1];
  return routeTitles[base] ?? "GRADE";
}

export default function AppLayout() {
  const { pathname } = useLocation();
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <div className="flex flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
            <SidebarTrigger />
            <Separator orientation="vertical" className="h-5" />
            <div className="flex flex-col leading-tight">
              <span className="text-xs uppercase tracking-wider text-muted-foreground">GRADE</span>
              <h1 className="text-sm font-semibold text-foreground">{getTitle(pathname)}</h1>
            </div>
          </header>
          <main className="flex-1 p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}