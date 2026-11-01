import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
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
