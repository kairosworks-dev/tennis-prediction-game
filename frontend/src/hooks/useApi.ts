import { useContext } from 'react';
import { ApiContext } from './apiContext';
import type { ApiClient } from '../services';

/** The only way a component reaches the service layer. */
export function useApi(): ApiClient {
  const client = useContext(ApiContext);
  if (client === null) {
    throw new Error('useApi() called outside an <ApiProvider>');
  }
  return client;
}
