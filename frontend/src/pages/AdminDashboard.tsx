import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

type SystemHealth = {
  status: string;
  pipeline: string;
  document_count: number;
  storage_used: string;
  uptime: string;
};

type PhoenixMetrics = {
  query_latency_ms: number;
  retrieval_score: number;
  total_queries: number;
  phoenix_integration: string;
};

export default function AdminDashboard() {
  const { token, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [metrics, setMetrics] = useState<PhoenixMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    const fetchAdminData = async () => {
      try {
        const [healthRes, metricsRes] = await Promise.all([
          fetch('/api/admin/health', { headers: { Authorization: `Bearer ${token}` } }),
          fetch('/api/admin/metrics', { headers: { Authorization: `Bearer ${token}` } })
        ]);

        if (healthRes.ok && metricsRes.ok) {
          setHealth(await healthRes.json());
          setMetrics(await metricsRes.json());
        } else if (healthRes.status === 401 || metricsRes.status === 401) {
          logout();
          navigate('/login');
        }
      } catch (err) {
        console.error("Failed to fetch admin data", err);
      } finally {
        setLoading(false);
      }
    };

    fetchAdminData();
  }, [token, isAuthenticated, navigate, logout]);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  if (loading) {
    return <div className="page-shell"><main className="content"><p>Loading dashboard...</p></main></div>;
  }

  return (
    <div className="page-shell">
      <nav className="top-nav">
        <div className="top-nav-inner">
          <span className="brand" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
            The Intelligent Layer
          </span>
          <div className="top-links">
            <span className="active">Admin Dashboard</span>
          </div>
          <button className="action-pill" type="button" onClick={handleLogout}>Sign Out</button>
        </div>
      </nav>

      <main className="content">
        <section className="hero" style={{ paddingBottom: '2rem' }}>
          <span className="eyebrow">Administration</span>
          <h1>System Overview</h1>
        </section>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
          
          <section className="results" style={{ margin: 0 }}>
            <h2>System Health</h2>
            {health ? (
              <ul style={{ listStyle: 'none', padding: 0 }}>
                <li style={{ padding: '0.8rem 0', borderBottom: '1px solid #333' }}><strong>Status:</strong> {health.status}</li>
                <li style={{ padding: '0.8rem 0', borderBottom: '1px solid #333' }}><strong>Pipeline:</strong> {health.pipeline}</li>
                <li style={{ padding: '0.8rem 0', borderBottom: '1px solid #333' }}><strong>Documents:</strong> {health.document_count}</li>
                <li style={{ padding: '0.8rem 0', borderBottom: '1px solid #333' }}><strong>Storage:</strong> {health.storage_used}</li>
                <li style={{ padding: '0.8rem 0' }}><strong>Uptime:</strong> {health.uptime}</li>
              </ul>
            ) : (
              <p>Unavailable</p>
            )}
          </section>

          <section className="results" style={{ margin: 0 }}>
            <h2>Phoenix Metrics (Stub)</h2>
            {metrics ? (
              <ul style={{ listStyle: 'none', padding: 0 }}>
                <li style={{ padding: '0.8rem 0', borderBottom: '1px solid #333' }}><strong>Query Latency:</strong> {metrics.query_latency_ms}ms</li>
                <li style={{ padding: '0.8rem 0', borderBottom: '1px solid #333' }}><strong>Retrieval Score:</strong> {metrics.retrieval_score}</li>
                <li style={{ padding: '0.8rem 0', borderBottom: '1px solid #333' }}><strong>Total Queries:</strong> {metrics.total_queries}</li>
                <li style={{ padding: '0.8rem 0' }}><strong>Integration:</strong> {metrics.phoenix_integration}</li>
              </ul>
            ) : (
              <p>Unavailable</p>
            )}
          </section>

          <section className="results" style={{ margin: 0, gridColumn: '1 / -1' }}>
            <h2>Document Management</h2>
            <p style={{ color: '#aaa', marginBottom: '1rem' }}>Upload or remove documents from the RAG corpus. (Future implementation)</p>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button className="action-pill" disabled style={{ opacity: 0.5 }}>Upload Document</button>
              <button className="action-pill" disabled style={{ opacity: 0.5, background: '#444' }}>Sync Corpus</button>
            </div>
          </section>

        </div>
      </main>
      
      <footer className="footer">
        <span>The Intelligent Layer</span>
        <small>Secured via RAG Intelligence</small>
      </footer>
    </div>
  );
}
