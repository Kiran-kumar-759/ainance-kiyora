import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import './authPortal.css';

export type AuthPortalMode = 'login' | 'register';

interface AuthPortalPageProps {
  mode: AuthPortalMode;
  onNavigate: (view: string) => void;
  onSuccess?: () => void;
}

const MIN_PW = 8;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface FieldErrors {
  first?: string;
  last?: string;
  email?: string;
  password?: string;
}

export const AuthPortalPage: React.FC<AuthPortalPageProps> = ({
  mode,
  onNavigate,
  onSuccess,
}) => {
  const { login, register } = useAuth();
  const [displayMode, setDisplayMode] = useState<AuthPortalMode>(mode);
  const [isReady, setIsReady] = useState(false);
  const [isSwapping, setIsSwapping] = useState(false);

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [statusNote, setStatusNote] = useState<{
    kind: 'ok' | 'error';
    text: string;
  } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const swapTimerRef = useRef<number | null>(null);
  const firstRef = useRef<HTMLInputElement | null>(null);
  const emailRef = useRef<HTMLInputElement | null>(null);
  const passwordRef = useRef<HTMLInputElement | null>(null);
  const lastRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => setIsReady(true));
    });
    return () => window.cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    if (mode === displayMode) return;
    setIsSwapping(true);
    setFieldErrors({});
    if (swapTimerRef.current !== null) {
      window.clearTimeout(swapTimerRef.current);
    }
    swapTimerRef.current = window.setTimeout(() => {
      setDisplayMode(mode);
      setIsSwapping(false);
    }, 260);

    return () => {
      if (swapTimerRef.current !== null) {
        window.clearTimeout(swapTimerRef.current);
      }
    };
  }, [mode, displayMode]);

  useEffect(() => {
    if (
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(min-width: 861px)').matches
    ) {
      if (displayMode === 'register') {
        firstRef.current?.focus({ preventScroll: true });
      } else {
        emailRef.current?.focus({ preventScroll: true });
      }
    }
  }, [displayMode]);

  const clearFieldErr = (key: keyof FieldErrors) => {
    setFieldErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleLinkNav =
    (targetView: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      if (targetView === 'login' || targetView === 'register') {
        setStatusNote(null);
      }
      onNavigate(targetView);
    };

  const validate = (): { errors: FieldErrors; firstInvalidEl: HTMLInputElement | null } => {
    const errors: FieldErrors = {};
    let firstInvalidEl: HTMLInputElement | null = null;

    const mark = (
      key: keyof FieldErrors,
      msg: string,
      el: HTMLInputElement | null
    ) => {
      errors[key] = msg;
      if (!firstInvalidEl) firstInvalidEl = el;
    };

    if (displayMode === 'register') {
      if (!firstName.trim()) {
        mark('first', 'Enter your first name.', firstRef.current);
      }
      if (!lastName.trim()) {
        mark('last', 'Enter your last name.', lastRef.current);
      }
    }

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      mark('email', 'Enter your email address.', emailRef.current);
    } else if (!EMAIL_RE.test(trimmedEmail)) {
      mark(
        'email',
        'Enter a valid email address, like name@example.com.',
        emailRef.current
      );
    }

    if (!password) {
      mark('password', 'Enter your password.', passwordRef.current);
    } else if (displayMode === 'register' && password.length < MIN_PW) {
      mark('password', `Use at least ${MIN_PW} characters.`, passwordRef.current);
    }

    return { errors, firstInvalidEl };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusNote(null);

    const { errors, firstInvalidEl } = validate();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      firstInvalidEl?.focus();
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);
    try {
      const cleanEmail = email.trim();
      if (displayMode === 'register') {
        const fullName = `${firstName.trim()} ${lastName.trim()}`.trim();
        await register(fullName, cleanEmail, password);
        setPassword('');
        setStatusNote({
          kind: 'ok',
          text: `Account created for ${cleanEmail}. Check your inbox to verify, and sign in to continue.`,
        });
        onNavigate('login');
      } else {
        await login(cleanEmail, password);
        setPassword('');
        if (onSuccess) {
          onSuccess();
        } else {
          onNavigate('dashboard');
        }
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Something went wrong. Check your connection and try again.';
      setStatusNote({ kind: 'error', text: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fs-auth-root">
      <div className="fs-auth-bg" aria-hidden="true" />
      <main
        className={`fs-auth-shell${isReady ? ' ready' : ''}${isSwapping ? ' swap' : ''}`}
        data-view={mode}
      >
        <section className="fs-auth-vis" aria-label="FinSight AI">
          <svg
            className="fs-auth-art"
            viewBox="0 0 600 800"
            preserveAspectRatio="xMidYMid slice"
            aria-hidden="true"
          >
            <defs>
              <filter id="fs-leaf" x="0" y="0" width="100%" height="100%">
                <feTurbulence
                  type="fractalNoise"
                  baseFrequency=".008 .02"
                  numOctaves="6"
                  seed="11"
                />
                <feColorMatrix
                  type="matrix"
                  values="0 0 0 0 .02  2.4 0 0 0 -.35  0 0 0 0 .12  0 0 0 0 1"
                />
              </filter>
              <radialGradient id="fs-mask" cx=".5" cy=".7" r=".75">
                <stop offset="0" stopColor="#fff" />
                <stop offset="1" stopColor="#000" />
              </radialGradient>
              <mask id="fs-m">
                <rect width="600" height="800" fill="url(#fs-mask)" />
              </mask>
            </defs>
            <rect width="600" height="800" fill="#03180d" />
            <rect width="600" height="800" filter="url(#fs-leaf)" mask="url(#fs-m)" opacity=".95" />
          </svg>

          <div className="fs-auth-glow" />

          <div className="fs-auth-top">
            <a
              className="fs-auth-brand"
              href="/"
              aria-label="FinSight AI home"
              onClick={handleLinkNav('foundation')}
            >
              <i />
              <span>FinSight AI</span>
            </a>

            <a
              className="fs-auth-back"
              href="/"
              aria-label="Back to home"
              onClick={handleLinkNav('foundation')}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
            </a>
          </div>

          <div className="fs-auth-cap">
            {displayMode === 'register' ? (
              <>
                <h2>
                  In the world of
                  <br />
                  <em>financial clarity</em>
                </h2>
                <div className="fs-auth-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </>
            ) : (
              <>
                <h2>
                  Your financial future,
                  <br />
                  <em>starts with clarity.</em>
                </h2>
                <p>
                  One secure place to understand your money, track your spending, and make smarter
                  financial decisions.
                </p>
                <div className="fs-auth-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </>
            )}
          </div>
        </section>

        <section className="fs-auth-pane">
          <div className="fs-auth-card">
            {displayMode === 'register' ? (
              <>
                <h1>Create Account</h1>
                <p className="fs-auth-sub">Enter your details to create your FinSight AI account.</p>
              </>
            ) : (
              <>
                <h1>Welcome Back</h1>
                <p className="fs-auth-sub">Sign in to continue your financial journey.</p>
              </>
            )}

            <form onSubmit={handleSubmit} noValidate>
              {displayMode === 'register' && (
                <div className="fs-auth-row">
                  <div className="fs-auth-f">
                    <label htmlFor="fs-first">First Name</label>
                    <div className="fs-auth-in">
                      <input
                        ref={firstRef}
                        id="fs-first"
                        name="first"
                        type="text"
                        placeholder="Enter your first name"
                        autoComplete="given-name"
                        value={firstName}
                        onChange={(e) => {
                          setFirstName(e.target.value);
                          clearFieldErr('first');
                        }}
                        aria-invalid={Boolean(fieldErrors.first) || undefined}
                        aria-describedby="fs-first-e"
                      />
                    </div>
                    <p
                      className={`fs-auth-err${fieldErrors.first ? ' on' : ''}`}
                      id="fs-first-e"
                      role="alert"
                    >
                      {fieldErrors.first || ''}
                    </p>
                  </div>

                  <div className="fs-auth-f">
                    <label htmlFor="fs-last">Last Name</label>
                    <div className="fs-auth-in">
                      <input
                        ref={lastRef}
                        id="fs-last"
                        name="last"
                        type="text"
                        placeholder="Enter your last name"
                        autoComplete="family-name"
                        value={lastName}
                        onChange={(e) => {
                          setLastName(e.target.value);
                          clearFieldErr('last');
                        }}
                        aria-invalid={Boolean(fieldErrors.last) || undefined}
                        aria-describedby="fs-last-e"
                      />
                    </div>
                    <p
                      className={`fs-auth-err${fieldErrors.last ? ' on' : ''}`}
                      id="fs-last-e"
                      role="alert"
                    >
                      {fieldErrors.last || ''}
                    </p>
                  </div>
                </div>
              )}

              <div className="fs-auth-f">
                <label htmlFor="fs-email">Email Address</label>
                <div className="fs-auth-in">
                  <input
                    ref={emailRef}
                    id="fs-email"
                    name="email"
                    type="email"
                    placeholder="Enter your email address"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      clearFieldErr('email');
                    }}
                    aria-invalid={Boolean(fieldErrors.email) || undefined}
                    aria-describedby="fs-email-e"
                  />
                </div>
                <p
                  className={`fs-auth-err${fieldErrors.email ? ' on' : ''}`}
                  id="fs-email-e"
                  role="alert"
                >
                  {fieldErrors.email || ''}
                </p>
              </div>

              <div className="fs-auth-f">
                <div className="fs-auth-label-row">
                  <label htmlFor="fs-password">Password</label>
                  {displayMode === 'login' && (
                    <button
                      type="button"
                      className="fs-auth-forgot"
                      onClick={() => onNavigate('forgot-password')}
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="fs-auth-in">
                  <input
                    ref={passwordRef}
                    id="fs-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    className="pw"
                    placeholder={
                      displayMode === 'register'
                        ? `Create a password (min. ${MIN_PW} characters)`
                        : 'Enter your password'
                    }
                    autoComplete={displayMode === 'register' ? 'new-password' : 'current-password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      clearFieldErr('password');
                    }}
                    aria-invalid={Boolean(fieldErrors.password) || undefined}
                    aria-describedby="fs-password-e"
                  />
                  <button
                    type="button"
                    className="fs-auth-eye"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((prev) => !prev)}
                  >
                    {showPassword ? (
                      <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M3 3l18 18M10.6 6.1A10 10 0 0 1 12 6c6.5 0 10 6 10 6a17 17 0 0 1-3.2 3.9M6.6 6.7A17 17 0 0 0 2 12s3.5 6 10 6c1.6 0 3-.3 4.3-.9M9.9 9.9a3 3 0 0 0 4.2 4.2" />
                      </svg>
                    ) : (
                      <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
                <p
                  className={`fs-auth-err${fieldErrors.password ? ' on' : ''}`}
                  id="fs-password-e"
                  role="alert"
                >
                  {fieldErrors.password || ''}
                </p>
              </div>

              <button className="fs-auth-btn" type="submit" disabled={isSubmitting}>
                {isSubmitting && <span className="fs-auth-spin" aria-hidden="true" />}
                <span>
                  {isSubmitting
                    ? displayMode === 'login'
                      ? 'Signing in…'
                      : 'Creating account…'
                    : displayMode === 'login'
                    ? 'Sign In'
                    : 'Create Account'}
                </span>
              </button>

              {statusNote && (
                <div
                  className={`fs-auth-note ${statusNote.kind}`}
                  role={statusNote.kind === 'error' ? 'alert' : 'status'}
                  aria-live="polite"
                >
                  {statusNote.text}
                </div>
              )}
            </form>

            <p className="fs-auth-alt">
              {displayMode === 'register' ? 'Already have an account?' : 'Don’t have an account?'}
              <br />
              <a
                href={displayMode === 'register' ? '/login' : '/register'}
                onClick={handleLinkNav(displayMode === 'register' ? 'login' : 'register')}
              >
                {displayMode === 'register' ? 'Sign In' : 'Create Account'}
              </a>
            </p>
          </div>
        </section>
      </main>
    </div>
  );
};
