import type { ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate } from 'react-router-dom';
import { useRegister } from '../hooks/queries';
import { Logo, Problem } from '../components/ui';
import { signUpSchema, type SignUpValues } from './authForms';

const FIELD =
  'mt-2 h-13 w-full rounded border border-line-strong bg-card px-3.5 text-base text-ink placeholder:text-faint';

export function SignUpPage(): ReactNode {
  const navigate = useNavigate();
  const register = useRegister();
  const form = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { displayName: '', email: '', password: '' },
  });

  const onSubmit = form.handleSubmit((values) => {
    register.mutate(values, { onSuccess: () => { navigate('/games'); } });
  });

  return (
    <div className="phone-shell px-6 pt-6">
      <Link to="/">
        <Logo />
      </Link>
      <h1 className="mt-8 font-display text-4xl leading-[1.05]">Create your account</h1>

      <form onSubmit={(event) => void onSubmit(event)} className="mt-7 flex flex-col gap-5" noValidate>
        <div>
          <label htmlFor="displayName" className="text-[13px] font-semibold">
            Display name
          </label>
          <p className="mt-0.5 text-xs text-muted">How you appear on the leaderboard.</p>
          <input id="displayName" className={FIELD} autoComplete="nickname" {...form.register('displayName')} />
          {form.formState.errors.displayName && (
            <p className="mt-1.5 text-[13px] text-clay-dark">{form.formState.errors.displayName.message}</p>
          )}
        </div>

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
            autoComplete="new-password"
            className={FIELD}
            {...form.register('password')}
          />
          {form.formState.errors.password && (
            <p className="mt-1.5 text-[13px] text-clay-dark">{form.formState.errors.password.message}</p>
          )}
        </div>

        <Problem error={register.error} />

        <button
          type="submit"
          disabled={register.isPending}
          className="h-13 rounded bg-clay text-base font-semibold text-card disabled:opacity-60"
        >
          {register.isPending ? 'Creating…' : 'Create account'}
        </button>

        <p className="text-center text-sm text-muted">
          Already have an account?{' '}
          <Link to="/sign-in" className="font-semibold text-clay">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
