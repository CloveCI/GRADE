import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
  useRouterState,
} from "@tanstack/react-router";

import appCss from "../styles.css?url";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { Toaster } from "@/components/ui/sonner";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          That route isn't part of the GRADE portal.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Back to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{error.message}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "GRADE · Autograder Portal" },
      {
        name: "description",
        content:
          "GRADE — Graduate Response Assessment & Document Evaluation. Upload answer keys and scanned student sheets, run OCR + hybrid RAG, and grade with Gemini.",
      },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

const ROUTE_TITLES: Array<[RegExp, string]> = [
  [/^\/$/, "Dashboard"],
  [/^\/metrics/, "Metrics"],
  [/^\/upload\/bundle/, "Upload bundle"],
  [/^\/keys\/new/, "New answer key"],
  [/^\/keys\/[^/]+$/, "Answer key"],
  [/^\/keys/, "Answer keys"],
  [/^\/sheets\/new/, "Upload sheet"],
  [/^\/sheets\/[^/]+$/, "Sheet detail"],
  [/^\/sheets/, "Sheets"],
  [/^\/evaluate/, "Evaluate"],
  [/^\/results\/[^/]+$/, "Result detail"],
  [/^\/results/, "Results"],
  [/^\/rag/, "RAG Explorer"],
];

function routeTitle(path: string) {
  for (const [re, t] of ROUTE_TITLES) if (re.test(path)) return t;
  return "GRADE";
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const path = useRouterState({ select: (s) => s.location.pathname });
  return (
    <QueryClientProvider client={queryClient}>
      <SidebarProvider>
        <div className="flex min-h-screen w-full bg-background text-foreground">
          <AppSidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/80 px-4 backdrop-blur">
              <SidebarTrigger />
              <div className="h-5 w-px bg-border" />
              <div className="text-sm font-medium tracking-wide text-foreground">
                {routeTitle(path)}
              </div>
              <div className="ml-auto text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                GRADE Autograder
              </div>
            </header>
            <main className="flex-1 p-6">
              <div className="mx-auto w-full max-w-7xl space-y-6">
                <Outlet />
              </div>
            </main>
          </div>
          <Toaster />
        </div>
      </SidebarProvider>
    </QueryClientProvider>
  );
}
