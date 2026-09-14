import { describe, expect, it } from 'vitest';
import { signInSchema, signUpSchema } from './authForms';

/**
 * These schemas exist for user experience only (AGENTS.md rule 2). What they
 * are tested for is that they mirror what the service layer enforces — never
 * that they decide anything.
 */
describe('sign-in schema', () => {
  it('accepts an address and a password', () => {
    expect(signInSchema.safeParse({ email: 'you@example.com', password: 'x' }).success).toBe(true);
  });

  it.each(['', 'not-an-address', 'missing@'])('rejects %o as an email', (email) => {
    expect(signInSchema.safeParse({ email, password: 'x' }).success).toBe(false);
  });

  it('rejects an empty password', () => {
    expect(signInSchema.safeParse({ email: 'you@example.com', password: '' }).success).toBe(false);
  });
});

describe('sign-up schema', () => {
  const valid = { displayName: 'Mattia', email: 'you@example.com', password: 'a-long-enough-one' };

  it('accepts a complete form', () => {
    expect(signUpSchema.safeParse(valid).success).toBe(true);
  });

  it('mirrors the ten-character minimum the service layer enforces', () => {
    const result = signUpSchema.safeParse({ ...valid, password: 'nineChars' });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toMatch(/ten characters/i);
  });

  it('mirrors the two-character display name minimum', () => {
    expect(signUpSchema.safeParse({ ...valid, displayName: 'M' }).success).toBe(false);
  });

  it('trims a display name before measuring it', () => {
    expect(signUpSchema.safeParse({ ...valid, displayName: '  M  ' }).success).toBe(false);
  });
});
