import type { ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate } from 'react-router-dom';
import { useLogin } from '../hooks/queries';
import { Logo, Problem } from '../components/ui';
import { signInSchema, type SignInValues } from './authForms';

const FIELD =
  'mt-2 h-13 w-full rounded border border-line-strong bg-card px-3.5 text-base text-ink placeholder:text-faint';

export function SignInPage(): ReactNode {
  const navigate = useNavigate();
  const login = useLogin();
  const form = useForm<SignInValues>({
    resolver: zodResolver(signInSchema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = form.handleSubmit((values) => {
    login.mutate(values, { onSuccess: () => { navigate('/games'); } });
  });

  return (
    <div className="phone-shell px-6 pt-6">
      <Link to="/">
        <Logo />
      </Link>
      <h1 className="mt-8 font-display text-4xl leading-none">Welcome back</h1>

      <form onSubmit={(event) => void onSubmit(event)} className="mt-7 flex flex-col gap-5" noValidate>
        <div>
          <label htmlFor="email" className="text-[13px] font-semibold">
            Email
          </label>
          <input id="email" type="email" autoComplete="email" className={FIELD} {...form.register('email')} />
          {form.formState.errors.email && (
            <p className="mt-1.5 text-[13px] text-clay-dark">{form.formState.errors.email.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="text-[13px] font-semibold">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className={FIELD}
            {...form.register('password')}
          />
          {form.formState.errors.password && (
            <p className="mt-1.5 text-[13px] text-clay-dark">{form.formState.errors.password.message}</p>
          )}
        </div>

        <Problem error={login.error} />

        <button
          type="submit"
          disabled={login.isPending}
          className="h-13 rounded bg-clay text-base font-semibold text-card disabled:opacity-60"
        >
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="text-center text-sm text-muted">
          No account yet?{' '}
          <Link to="/sign-up" className="font-semibold text-clay">
            Create one
          </Link>
        </p>
      </form>
    </div>
  );
}
