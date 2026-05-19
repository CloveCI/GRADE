import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import AppLayout from "./layouts/AppLayout";
import Index from "./pages/Index.tsx";
import Keys from "./pages/Keys.tsx";
import KeyNew from "./pages/KeyNew.tsx";
import Sheets from "./pages/Sheets.tsx";
import SheetNew from "./pages/SheetNew.tsx";
import Evaluate from "./pages/Evaluate.tsx";
import Results from "./pages/Results.tsx";
import Metrics from "./pages/Metrics.tsx";
import RagExplorer from "./pages/RagExplorer.tsx";
import UploadBundle from "./pages/UploadBundle.tsx";
import NotFound from "./pages/NotFound.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Index />} />
            <Route path="/upload/bundle" element={<UploadBundle />} />
            <Route path="/keys" element={<Keys />} />
            <Route path="/keys/new" element={<KeyNew />} />
            <Route path="/keys/:examId" element={<Keys />} />
            <Route path="/sheets" element={<Sheets />} />
            <Route path="/sheets/new" element={<SheetNew />} />
            <Route path="/sheets/:sheetId" element={<Sheets />} />
            <Route path="/evaluate" element={<Evaluate />} />
            <Route path="/evaluate/:sheetId" element={<Evaluate />} />
            <Route path="/results" element={<Results />} />
            <Route path="/results/:resultId" element={<Results />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/rag" element={<RagExplorer />} />
          </Route>
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
