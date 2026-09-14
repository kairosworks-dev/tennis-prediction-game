import type { ApiClient } from './apiClient';
import { MockApiClient } from './mock/MockApiClient';

export type { ApiClient } from './apiClient';
export * from './types';
export { ApiError, isApiError, type ProblemDetail } from './errors';

/** Which implementation the app runs against. Set by `VITE_API_CLIENT`. */
export type ApiClientKind = 'mock' | 'http';

function configuredKind(): ApiClientKind {
  const raw: unknown = import.meta.env.VITE_API_CLIENT;
  return raw === 'http' ? 'http' : 'mock';
}

/**
 * The one place an implementation is chosen (spec 7.2).
 *
 * Everything else in the application depends on the `ApiClient` interface and
 * never on a concrete class, which is what makes step 3 a change of
 * environment variable rather than a change of code.
 */
export function createApiClient(kind: ApiClientKind = configuredKind()): ApiClient {
  if (kind === 'http') {
    throw new Error(
      'HttpApiClient arrives in step 3, once openapi.yaml exists and the backend implements it. ' +
        'Set VITE_API_CLIENT=mock until then.',
    );
  }
  return new MockApiClient();
}
