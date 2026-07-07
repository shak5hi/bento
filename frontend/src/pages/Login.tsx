import { useState } from 'react';
import { Link } from 'react-router-dom';
import './Login.css';

// Import all compartment SVG assets for the collage
import zoom1Img from '../assets/compartmentzoom1.svg';
import zoom2Img from '../assets/compartmentzoom2.svg';
import zoom3Img from '../assets/Compartment3.svg';
import zoom4Img from '../assets/compartmentzoom4.svg';
import zoom5Img from '../assets/Compartment5.svg';

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log(isLogin ? "Logging in..." : "Registering...", { email, password });
    // Authentication logic would go here
  };

  return (
    <div className="login-container">
      {/* LEFT SIDE: Auth Form */}
      <div className="login-left">
        <div className="login-form-wrapper">
          <Link to="/" className="back-link">
            ← Back to Home
          </Link>
          
          <div className="login-header">
            <h1 className="login-title">
              {isLogin ? 'Welcome back.' : 'Create an account.'}
            </h1>
            <p className="login-subtitle">
              {isLogin 
                ? 'Sign in to access your engineering home.' 
                : 'Join Bento and start building clarity into your workspace.'}
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="input-group">
              <label htmlFor="email">Email address</label>
              <input 
                type="email" 
                id="email" 
                placeholder="you@company.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            
            <div className="input-group">
              <label htmlFor="password">Password</label>
              <input 
                type="password" 
                id="password" 
                placeholder="••••••••" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {isLogin && (
              <div className="forgot-password">
                <a href="#">Forgot your password?</a>
              </div>
            )}

            <button type="submit" className="submit-btn">
              {isLogin ? 'Sign In' : 'Sign Up'}
            </button>
          </form>

          <div className="auth-toggle">
            {isLogin ? "Don't have an account? " : "Already have an account? "}
            <button onClick={() => setIsLogin(!isLogin)} className="toggle-btn">
              {isLogin ? 'Sign up' : 'Sign in'}
            </button>
          </div>
        </div>
      </div>

      {/* RIGHT SIDE: Orange Background + SVG Collage */}
      <div className="login-right">
        <div className="collage-container">
          <img src={zoom3Img} className="collage-img img-center" alt="Bento Compartment" />
          <img src={zoom1Img} className="collage-img img-top-left" alt="Bento Compartment" />
          <img src={zoom2Img} className="collage-img img-top-right" alt="Bento Compartment" />
          <img src={zoom4Img} className="collage-img img-bottom-left" alt="Bento Compartment" />
          <img src={zoom5Img} className="collage-img img-bottom-right" alt="Bento Compartment" />
        </div>
      </div>
    </div>
  );
}
