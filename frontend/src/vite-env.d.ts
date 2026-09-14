/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_CLIENT?: 'mock' | 'http';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
