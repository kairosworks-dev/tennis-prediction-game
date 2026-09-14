import { useMemo, type ReactNode } from 'react';
import { createApiClient, type ApiClient } from '../services';
import { ApiContext } from './apiContext';

/**
 * The one place a concrete implementation is chosen at runtime.
 *
 * Components consume `useApi()`, never `MockApiClient` or `HttpApiClient`, so
 * swapping them is an environment variable (AGENTS.md hard rule 1, spec 7.2).
 * Tests pass their own client in.
 */
export function ApiProvider({ client, children }: { client?: ApiClient; children: ReactNode }): ReactNode {
  const value = useMemo(() => client ?? createApiClient(), [client]);
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>;
}
