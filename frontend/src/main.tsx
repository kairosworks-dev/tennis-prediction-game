import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { ApiProvider } from './hooks/ApiProvider';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The mock has artificial latency; retrying a rejected validation would
      // only make a wrong answer take longer to report.
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

const root = document.getElementById('root');
if (root === null) {
  throw new Error('no #root element to mount into');
}

createRoot(root).render(
  <StrictMode>
    <ApiProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ApiProvider>
  </StrictMode>,
);
