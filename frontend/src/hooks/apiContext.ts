import { createContext } from 'react';
import type { ApiClient } from '../services';

/** Lives apart from the provider so hot reload keeps working. */
export const ApiContext = createContext<ApiClient | null>(null);
