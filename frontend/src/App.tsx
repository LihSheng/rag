import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline } from '@mui/material';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { AuthProvider, useAuth } from './context/AuthContext';
import Search from './pages/Search';
import Login from './pages/Login';
import AdminDashboard from './pages/AdminDashboard';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#2D66F6' },
    secondary: { main: '#8B95A7' },
    success: { main: '#18A572' },
    warning: { main: '#D98E04' },
    error: { main: '#C23B3B' },
    background: {
      default: '#F6F7F9',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#0E1116',
      secondary: '#8B95A7',
    },
  },
  shape: {
    borderRadius: 10,
  },
  typography: {
    fontFamily: '"Instrument Sans", sans-serif',
    h1: { fontFamily: '"Satoshi", sans-serif', fontWeight: 700 },
    h2: { fontFamily: '"Satoshi", sans-serif', fontWeight: 700 },
    h3: { fontFamily: '"Satoshi", sans-serif', fontWeight: 700 },
    button: { fontFamily: '"Satoshi", sans-serif', fontWeight: 700, textTransform: 'none' },
    overline: { fontFamily: '"IBM Plex Mono", monospace', letterSpacing: '0.08em', fontSize: '0.75rem' },
    caption: { fontFamily: '"IBM Plex Mono", monospace' },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          border: '1px solid #DFE3EA',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          paddingInline: 16,
          minHeight: 40,
        },
      },
    },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to='/login' replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path='/' element={<Search />} />
            <Route path='/login' element={<Login />} />
            <Route
              path='/admin/*'
              element={(
                <ProtectedRoute>
                  <AdminDashboard />
                </ProtectedRoute>
              )}
            />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
