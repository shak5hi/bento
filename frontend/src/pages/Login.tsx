import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError, api, auth } from '../lib/api';
import './Login.css';

import zoom1Img from '../assets/compartmentzoom1.svg';
import zoom2Img from '../assets/compartmentzoom2.svg';
import zoom4Img from '../assets/compartmentzoom4.svg';

type Mode = 'login' | 'register';

export default function Login() {
  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(params.get('error'));
  const [busy, setBusy] = useState(false);
  const [githubEnabled, setGithubEnabled] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api<{ github: boolean }>('/auth/providers').then((p) => setGithubEnabled(p.github)).catch(() => {});
  }, []);
  const isLogin = mode === 'login';

  const switchMode = () => {
    setMode(isLogin ? 'register' : 'login');
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = isLogin ? { email, password } : { email, password, name: name || undefined };
      const res = await api<{ token: string }>(`/auth/${isLogin ? 'login' : 'register'}`, { method: 'POST', body });
      auth.set(res.token);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <section className="auth-panel">
        <header className="auth-top">
          <Link to="/" className="auth-mark" aria-label="Bento home">
            <span className="mark">B</span>
            <span>Bento</span>
          </Link>
          <Link to="/" className="auth-back">Back to site</Link>
        </header>

        <div className="auth-body">
          <p className="eyebrow">{isLogin ? 'Sign in' : 'Create account'}</p>
          <h1 className="auth-title">
            {isLogin ? <>Welcome <b>back.</b></> : <>Your engineering <b>home.</b></>}
          </h1>
          <p className="auth-lede">
            {isLogin
              ? 'Pickle has been watching your projects while you were away.'
              : 'Connect your projects once. Bento tells you what deserves your attention, every day.'}
          </p>

          {githubEnabled && (
            <>
              <a className="auth-github" href="/api/auth/github/login">
                <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true">
                  <path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                </svg>
                Continue with GitHub
              </a>
              <p className="auth-or"><span>or use email</span></p>
            </>
          )}

          <form className="auth-form" onSubmit={handleSubmit} noValidate={false}>
            {!isLogin && (
              <label className="field">
                <span>Name</span>
                <input type="text" autoComplete="name" placeholder="Ada Lovelace" value={name} onChange={(e) => setName(e.target.value)} />
              </label>
            )}
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label className="field">
              <span className="field-row">
                Password
                <button type="button" className="field-toggle" onClick={() => setShowPassword((v) => !v)}>
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </span>
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                placeholder={isLogin ? 'Your password' : 'At least 8 characters'}
                minLength={isLogin ? undefined : 8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>

            {error && <p className="auth-error" role="alert">{error}</p>}

            <button type="submit" className="auth-submit" disabled={busy}>
              {busy ? (isLogin ? 'Signing in…' : 'Creating account…') : isLogin ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="auth-switch">
            {isLogin ? 'New to Bento?' : 'Already have an account?'}{' '}
            <button type="button" onClick={switchMode}>{isLogin ? 'Create an account' : 'Sign in'}</button>
          </p>
        </div>

        <footer className="auth-foot">© {new Date().getFullYear()} Bento</footer>
      </section>

      <aside className="auth-art" aria-hidden="true">
        <div className="auth-collage">
          <img src={zoom1Img} className="collage-img c1" alt="" />
          <img src={zoom2Img} className="collage-img c2" alt="" />
          <img src={zoom4Img} className="collage-img c3" alt="" />
        </div>
        <figure className="auth-quote">
          <blockquote>“Open one place. Know exactly what to do next.”</blockquote>
          <figcaption>Pickle, your engineering assistant</figcaption>
        </figure>
      </aside>
    </div>
  );
}
