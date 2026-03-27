import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Box, Button, Container, Paper, Stack, TextField, Typography } from '@mui/material';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [is_loading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (event: FormEvent) => {
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
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', p: 3 }}>
      <Container maxWidth='sm'>
        <Paper sx={{ p: 3, borderRadius: '14px', boxShadow: '0 12px 32px rgba(14,17,22,0.08)' }}>
          <Typography variant='overline' color='text.secondary'>Operator Access</Typography>
          <Typography variant='h4' sx={{ mt: 0.5 }}>Admin Login</Typography>
          {error && <Alert severity='error' sx={{ mt: 1.5 }}>{error}</Alert>}

          <Box component='form' onSubmit={handleLogin} sx={{ mt: 2 }}>
            <Stack spacing={1.5}>
              <TextField
                label='Username'
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                size='small'
              />
              <TextField
                label='Password'
                type='password'
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                size='small'
              />
              <Button type='submit' variant='contained' disabled={is_loading}>
                {is_loading ? 'Authenticating...' : 'Sign In'}
              </Button>
              <Button type='button' variant='outlined' onClick={() => navigate('/')}>
                Back to Search
              </Button>
            </Stack>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
