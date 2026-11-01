import { Navigate } from 'react-router-dom';
import { auth } from '../lib/api';

export function RequireAuth({ children }: { children: React.ReactElement }) {
  return auth.token ? children : <Navigate to="/login" replace />;
}
