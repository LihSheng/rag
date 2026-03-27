import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

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

type DocumentItem = {
  id: string;
  name: string;
  path: string;
  checksum: string;
};

type RAGConfig = {
  pipeline: string;
  top_k: number;
  hybrid_enabled: boolean;
};

type AdminModule = 'overview' | 'documents' | 'phoenix' | 'config';

type NoticeTone = 'success' | 'error' | 'info';

type NoticeState = {
  tone: NoticeTone;
  message: string;
} | null;

export default function AdminDashboard() {
  const { token, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [metrics, setMetrics] = useState<PhoenixMetrics | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [config, setConfig] = useState<RAGConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [active_module, setActiveModule] = useState<AdminModule>('overview');
  const [is_nav_compact, setIsNavCompact] = useState(false);
  const [is_syncing, setIsSyncing] = useState(false);
  const [is_uploading, setIsUploading] = useState(false);
  const [notice, setNotice] = useState<NoticeState>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    const fetchAdminData = async () => {
      try {
        const [health_res, metrics_res, docs_res, config_res] = await Promise.all([
          fetch('/api/admin/health', { headers: { Authorization: `Bearer ${token}` } }),
          fetch('/api/admin/metrics', { headers: { Authorization: `Bearer ${token}` } }),
          fetch('/api/admin/documents', { headers: { Authorization: `Bearer ${token}` } }),
          fetch('/api/admin/config', { headers: { Authorization: `Bearer ${token}` } }),
        ]);

        if (health_res.ok && metrics_res.ok && docs_res.ok && config_res.ok) {
          setHealth(await health_res.json());
          setMetrics(await metrics_res.json());
          setDocuments(await docs_res.json());
          setConfig(await config_res.json());
        } else if (health_res.status === 401 || metrics_res.status === 401) {
          logout();
          navigate('/login');
          return;
        } else {
          setNotice({ tone: 'error', message: 'Unable to load some admin data. Check API health and try refresh.' });
        }
      } catch {
        setNotice({ tone: 'error', message: 'Admin data request failed. Check backend and network connectivity.' });
      } finally {
        setLoading(false);
      }
    };

    fetchAdminData();
  }, [token, isAuthenticated, navigate, logout]);

  const refreshDocuments = async () => {
    const response = await fetch('/api/admin/documents', { headers: { Authorization: `Bearer ${token}` } });
    if (response.ok) {
      setDocuments(await response.json());
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const handleSync = async () => {
    setIsSyncing(true);
    setNotice(null);
    try {
      const response = await fetch('/api/admin/documents/sync', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error('sync_failed');
      }

      await refreshDocuments();
      setNotice({ tone: 'success', message: 'Directory sync completed and document list refreshed.' });
    } catch {
      setNotice({ tone: 'error', message: 'Sync failed. Check corpus directory and backend logs.' });
    } finally {
      setIsSyncing(false);
    }
  };

  const handleFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) {
      return;
    }

    setIsUploading(true);
    setNotice(null);

    const form_data = new FormData();
    form_data.append('file', event.target.files[0]);

    try {
      const response = await fetch('/api/admin/documents/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form_data,
      });

      if (!response.ok) {
        throw new Error('upload_failed');
      }

      await refreshDocuments();
      setNotice({ tone: 'success', message: 'File uploaded and queued for indexing.' });
    } catch {
      setNotice({ tone: 'error', message: 'Upload failed. Validate file type and retry.' });
    } finally {
      setIsUploading(false);
      event.target.value = '';
    }
  };

  const handleConfigSave = async (event: FormEvent) => {
    event.preventDefault();
    if (!config) {
      return;
    }

    setNotice(null);

    try {
      const response = await fetch('/api/admin/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        throw new Error('save_failed');
      }

      setNotice({ tone: 'success', message: 'Configuration saved successfully.' });
    } catch {
      setNotice({ tone: 'error', message: 'Configuration save failed. Check values and retry.' });
    }
  };

  if (loading) {
    return (
      <div className='page-shell'>
        <main className='query-layout'>
          <section className='chat-panel'>
            <article className='message assistant-message loading-message'>
              <span className='message-label'>Admin</span>
              <p>Loading dashboard state...</p>
            </article>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className='admin-shell'>
      <aside className={`admin-nav ${is_nav_compact ? 'compact' : ''}`}>
        <div className='admin-nav-head'>
          {!is_nav_compact && <span className='admin-nav-brand'>RAG Operator</span>}
          <button
            type='button'
            className='admin-nav-toggle'
            onClick={() => setIsNavCompact((prev) => !prev)}
            aria-label='Toggle sidebar'
          >
            <span className='material-symbols-outlined'>{is_nav_compact ? 'menu' : 'menu_open'}</span>
          </button>
        </div>

        <nav className='admin-nav-list'>
          <SidebarItem
            icon='space_dashboard'
            label='Overview'
            isOpen={!is_nav_compact}
            isActive={active_module === 'overview'}
            onClick={() => setActiveModule('overview')}
          />
          <SidebarItem
            icon='folder_open'
            label='Documents'
            isOpen={!is_nav_compact}
            isActive={active_module === 'documents'}
            onClick={() => setActiveModule('documents')}
          />
          <SidebarItem
            icon='monitoring'
            label='Metrics'
            isOpen={!is_nav_compact}
            isActive={active_module === 'phoenix'}
            onClick={() => setActiveModule('phoenix')}
          />
          <SidebarItem
            icon='tune'
            label='Config'
            isOpen={!is_nav_compact}
            isActive={active_module === 'config'}
            onClick={() => setActiveModule('config')}
          />
        </nav>

        <div className='admin-nav-foot'>
          <SidebarItem icon='logout' label='Sign Out' isOpen={!is_nav_compact} isActive={false} onClick={handleLogout} />
        </div>
      </aside>

      <section className='admin-main'>
        <header className='admin-topbar'>
          <div>
            <p className='query-kicker'>Phase 2 Control Plane</p>
            <h2>{moduleTitle(active_module)}</h2>
          </div>
          <button className='action-pill' type='button' onClick={() => navigate('/')}>Back to Search</button>
        </header>

        {notice && <Notice tone={notice.tone} message={notice.message} />}

        <main className='admin-content'>
          {active_module === 'overview' && (
            <section className='admin-grid'>
              <MetricCard title='System Status' value={health?.status.toUpperCase() || 'UNKNOWN'} status={health?.status === 'ok' ? 'success' : 'error'} />
              <MetricCard title='Active Pipeline' value={health?.pipeline || '--'} />
              <MetricCard title='Document Count' value={String(health?.document_count ?? 0)} />
              <MetricCard title='Storage Used' value={health?.storage_used || '--'} />
              <MetricCard title='System Uptime' value={health?.uptime || '--'} />
            </section>
          )}

          {active_module === 'documents' && (
            <section className='admin-card'>
              <div className='admin-card-head'>
                <h3>Corpus Management</h3>
                <div className='admin-actions'>
                  <label className='admin-button primary'>
                    {is_uploading ? 'Uploading...' : 'Upload File'}
                    <input type='file' onChange={handleFileUpload} disabled={is_uploading} hidden />
                  </label>
                  <button className='admin-button' type='button' onClick={handleSync} disabled={is_syncing}>
                    {is_syncing ? 'Syncing...' : 'Sync Directory'}
                  </button>
                </div>
              </div>

              {documents.length === 0 ? (
                <div className='admin-empty'>No documents found in this pipeline collection.</div>
              ) : (
                <div className='admin-table-wrap'>
                  <table className='admin-table'>
                    <thead>
                      <tr>
                        <th>Filename</th>
                        <th>Path</th>
                        <th>Checksum</th>
                        <th>ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => (
                        <tr key={doc.id}>
                          <td>{doc.name}</td>
                          <td className='mono'>{doc.path}</td>
                          <td className='mono'>{doc.checksum.slice(0, 8)}...</td>
                          <td className='mono'>{doc.id.slice(0, 8)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {active_module === 'phoenix' && (
            <section className='admin-card'>
              <div className='admin-grid three'>
                <MetricCard title='Avg Latency' value={`${metrics?.query_latency_ms ?? 0} ms`} />
                <MetricCard title='Retrieval Score' value={`${metrics?.retrieval_score ?? 0}`} />
                <MetricCard title='Total Traces' value={`${metrics?.total_queries ?? 0}`} />
              </div>
              <p className='admin-footnote'>Phoenix integration status: {metrics?.phoenix_integration || 'pending'}</p>
            </section>
          )}

          {active_module === 'config' && (
            <section className='admin-card'>
              <form className='admin-form' onSubmit={handleConfigSave}>
                <label>
                  <span>Active Pipeline</span>
                  <select
                    value={config?.pipeline || 'manual'}
                    onChange={(event) =>
                      setConfig((prev) => (prev ? { ...prev, pipeline: event.target.value } : null))
                    }
                  >
                    <option value='manual'>Manual Python</option>
                    <option value='langchain'>LangChain Framework</option>
                  </select>
                </label>

                <label>
                  <span>Top K Documents</span>
                  <input
                    type='number'
                    min={1}
                    value={config?.top_k || 5}
                    onChange={(event) =>
                      setConfig((prev) =>
                        prev ? { ...prev, top_k: Number.parseInt(event.target.value || '1', 10) } : null,
                      )
                    }
                  />
                </label>

                <fieldset>
                  <legend>Hybrid Search (RRF)</legend>
                  <label className='inline'>
                    <input
                      type='radio'
                      name='hybrid'
                      checked={config?.hybrid_enabled === true}
                      onChange={() => setConfig((prev) => (prev ? { ...prev, hybrid_enabled: true } : null))}
                    />
                    Enable
                  </label>
                  <label className='inline'>
                    <input
                      type='radio'
                      name='hybrid'
                      checked={config?.hybrid_enabled === false}
                      onChange={() => setConfig((prev) => (prev ? { ...prev, hybrid_enabled: false } : null))}
                    />
                    Disable
                  </label>
                </fieldset>

                <div className='admin-form-foot'>
                  <button type='submit' className='admin-button primary'>Save Configuration</button>
                </div>
              </form>
            </section>
          )}
        </main>
      </section>
    </div>
  );
}

function moduleTitle(module: AdminModule) {
  if (module === 'overview') {
    return 'System Overview';
  }

  if (module === 'documents') {
    return 'Document Management';
  }

  if (module === 'phoenix') {
    return 'Tracing and Metrics';
  }

  return 'Pipeline Configuration';
}

function SidebarItem({
  icon,
  label,
  isOpen,
  isActive,
  onClick,
}: {
  icon: string;
  label: string;
  isOpen: boolean;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type='button'
      onClick={onClick}
      className={`admin-nav-item ${isActive ? 'active' : ''}`}
      title={label}
      aria-label={label}
    >
      <span className='material-symbols-outlined'>{icon}</span>
      {isOpen && <span>{label}</span>}
    </button>
  );
}

function MetricCard({
  title,
  value,
  status,
}: {
  title: string;
  value: string;
  status?: 'success' | 'error';
}) {
  return (
    <article className='admin-metric-card'>
      <p>{title}</p>
      <strong className={status ? `tone-${status}` : ''}>{value}</strong>
    </article>
  );
}

function Notice({ tone, message }: { tone: NoticeTone; message: string }) {
  return <div className={`admin-notice ${tone}`}>{message}</div>;
}
