import { z } from 'zod';

/**
 * Form schemas — user experience only.
 *
 * AGENTS.md rule 2: these exist so a typo is caught before a round trip, not
 * so the frontend decides anything. They mirror what `MockApiClient` enforces;
 * when the two disagree the service layer wins, and from step 3 the real API
 * wins over both. Never add a rule here that has no server-side counterpart.
 */

export const signInSchema = z.object({
  email: z.string().min(1, 'Enter your email address.').email('That does not look like an email address.'),
  password: z.string().min(1, 'Enter your password.'),
});

export const signUpSchema = z.object({
  displayName: z.string().trim().min(2, 'Display names need at least two characters.'),
  email: z.string().min(1, 'Enter your email address.').email('That does not look like an email address.'),
  password: z.string().min(10, 'Passwords need at least ten characters.'),
});

export type SignInValues = z.infer<typeof signInSchema>;
export type SignUpValues = z.infer<typeof signUpSchema>;
