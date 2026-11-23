import { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { auth } from '../lib/api';

/** GitHub sign-in lands here with the session token in the URL fragment (never sent to a server). */
export default function AuthCallback() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token');
  useEffect(() => {
    if (token) {
      auth.set(token);
      window.history.replaceState(null, '', '/auth/callback'); // drop the token from history
    }
  }, [token]);
  return <Navigate to={token ? '/dashboard' : '/login?error=Sign-in%20failed.%20Please%20try%20again.'} replace />;
}
