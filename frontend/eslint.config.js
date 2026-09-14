import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

/**
 * AGENTS.md hard rule 1: no HTTP calls outside the frontend service layer.
 *
 * Every backend interaction goes through `src/services/`. Nothing else may
 * reach the network directly. Do not disable these rules and do not add
 * per-file exceptions — if a component needs data, the service layer grows a
 * method for it.
 */
const NETWORK_GLOBALS = ['fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'navigator'];

const HTTP_LIBRARIES = [
  'axios', 'ky', 'got', 'superagent', 'node-fetch', 'cross-fetch',
  'isomorphic-fetch', 'undici', 'redaxios', 'wretch',
];

const networkBan = {
  'no-restricted-globals': [
    'error',
    ...NETWORK_GLOBALS.map((name) => ({
      name,
      message: `Reach the backend through src/services/ instead of ${name}. See AGENTS.md hard rule 1.`,
    })),
  ],
  'no-restricted-imports': [
    'error',
    {
      paths: HTTP_LIBRARIES.map((name) => ({
        name,
        message: 'Reach the backend through src/services/ instead of an HTTP client. See AGENTS.md hard rule 1.',
      })),
      patterns: [
        {
          group: ['**/services/mock/**', '**/services/http/**'],
          message:
            'Import the ApiClient from src/services, never a concrete implementation. Selection is by environment variable.',
        },
      ],
    },
  ],
  // `no-restricted-globals` only catches the bare identifier.
  'no-restricted-syntax': [
    'error',
    {
      selector:
        "MemberExpression[object.name=/^(window|globalThis|self)$/][property.name=/^(fetch|XMLHttpRequest|WebSocket|EventSource)$/]",
      message: 'Reach the backend through src/services/. See AGENTS.md hard rule 1.',
    },
  ],
};

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'node_modules'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        project: ['./tsconfig.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // AGENTS.md: no `any`, no implicit return types on service methods.
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-module-boundary-types': 'error',
      '@typescript-eslint/consistent-type-imports': 'error',
      // `const { id: _ignored, ...rest }` is how a field is dropped from a request.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', ignoreRestSiblings: true },
      ],
      // Numbers interpolate unambiguously; forcing String() around every count
      // adds noise without adding safety.
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }],
    },
  },
  {
    // The ban applies everywhere except the service layer itself.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/services/**'],
    rules: networkBan,
  },
  {
    // Inside the service layer, `fetch` is the point — but only in http/.
    files: ['src/services/**/*.ts'],
    ignores: ['src/services/http/**'],
    rules: {
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Only src/services/http/ talks to the network.' },
      ],
    },
  },
);
