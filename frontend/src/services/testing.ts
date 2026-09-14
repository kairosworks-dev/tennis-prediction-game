import { MockApiClient, type MockApiClientOptions } from './mock/MockApiClient';
import type { ApiClient } from './apiClient';

/**
 * The test seam for anything outside the service layer.
 *
 * A component test needs a real client to render against, but AGENTS.md hard
 * rule 1 says nothing outside `src/services/` imports a concrete
 * implementation — and the ESLint rule enforces it. So the seam is exported
 * from here rather than carved as a hole in the rule for test files.
 *
 * Latency is off by default; pass `signedIn` and `asAdmin` to choose who is
 * looking at the page.
 */
export function createTestApiClient(options: MockApiClientOptions = {}): ApiClient {
  return new MockApiClient({ latencyMs: 0, ...options });
}
