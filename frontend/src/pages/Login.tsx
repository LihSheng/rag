import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        throw new Error('Login failed. Please check credentials.');
      }

      const data = await response.json();
      login(data.access_token);
      navigate('/admin');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="page-shell" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <main className="content" style={{ maxWidth: '400px', width: '100%', marginTop: '50px' }}>
        <section className="results" style={{ padding: '2rem', background: '#1c1c1c', borderRadius: '12px', color: '#ffffff' }}>
          <h2 style={{ color: '#ffffff', margin: '0 0 1rem 0' }}>Admin Login</h2>
          {error && <div className="error-box">{error}</div>}
          
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
            <div>
              <label>Username</label>
              <input 
                type="text" 
                value={username} 
                onChange={e => setUsername(e.target.value)} 
                style={{ width: '100%', padding: '0.8rem', marginTop: '0.5rem', background: '#2a2a2a', border: '1px solid #333', color: '#fff', borderRadius: '4px' }}
                required 
              />
            </div>
            <div>
              <label>Password</label>
              <input 
                type="password" 
                value={password} 
                onChange={e => setPassword(e.target.value)} 
                style={{ width: '100%', padding: '0.8rem', marginTop: '0.5rem', background: '#2a2a2a', border: '1px solid #333', color: '#fff', borderRadius: '4px' }}
                required 
              />
            </div>
            <button type="submit" disabled={isLoading} className="action-pill" style={{ marginTop: '1rem', width: '100%', justifyContent: 'center', background: '#3b82f6', color: '#fff' }}>
              {isLoading ? 'Authenticating...' : 'Sign In'}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
