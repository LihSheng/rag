import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
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
    <div className='login-shell'>
      <main className='login-main'>
        <section className='login-card'>
          <p className='query-kicker'>Operator Access</p>
          <h2>Admin Login</h2>
          {error && <div className="error-box">{error}</div>}

          <form onSubmit={handleLogin} className='login-form'>
            <label>
              <span>Username</span>
              <input
                type='text'
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </label>

            <label>
              <span>Password</span>
              <input
                type='password'
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>

            <button type='submit' disabled={isLoading} className='action-pill login-submit'>
              {isLoading ? 'Authenticating...' : 'Sign In'}
            </button>
          </form>

          <button type='button' className='login-back' onClick={() => navigate('/')}>
            Back to Search
          </button>
        </section>
      </main>
    </div>
  );
}
