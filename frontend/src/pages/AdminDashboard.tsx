import { FormEvent, ReactNode, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Drawer,
  FormControl,
  FormControlLabel,
  FormLabel,
  Grid,
  IconButton,
  InputLabel,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Toolbar,
  Typography,
  useMediaQuery,
} from '@mui/material';
import DashboardOutlinedIcon from '@mui/icons-material/DashboardOutlined';
import FolderOpenOutlinedIcon from '@mui/icons-material/FolderOpenOutlined';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined';
import MenuOutlinedIcon from '@mui/icons-material/MenuOutlined';
import MenuOpenOutlinedIcon from '@mui/icons-material/MenuOpenOutlined';
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

type DatasetItem = {
  name: string;
  vectors_count: number | Record<string, unknown> | null;
  points_count: number | Record<string, unknown> | null;
  is_active: boolean;
};

type QdrantCollectionsResponse = {
  alias: string;
  active_collection: string | null;
  collections: DatasetItem[];
};

type OperationItem = {
  id: number;
  action: string;
  target: string;
  actor: string;
  status: string;
  detail: string | null;
  created_at: string;
};

type RAGConfig = {
  pipeline: string;
  top_k: number;
  hybrid_enabled: boolean;
};

type AdminModule = 'overview' | 'datasets' | 'phoenix' | 'config';

type NoticeTone = 'success' | 'error' | 'info';

type NoticeState = {
  tone: NoticeTone;
  message: string;
} | null;

const SIDEBAR_WIDTH = 250;
const SIDEBAR_COMPACT_WIDTH = 72;

export default function AdminDashboard() {
  const { token, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const is_mobile = useMediaQuery('(max-width:768px)');

  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [metrics, setMetrics] = useState<PhoenixMetrics | null>(null);
  const [config, setConfig] = useState<RAGConfig | null>(null);
  const [datasets_payload, setDatasetsPayload] = useState<QdrantCollectionsResponse | null>(null);
  const [operations, setOperations] = useState<OperationItem[]>([]);
  const [new_collection_name, setNewCollectionName] = useState('');
  const [new_vector_size, setNewVectorSize] = useState(384);
  const [ingest_collection_name, setIngestCollectionName] = useState('');
  const [ingest_file, setIngestFile] = useState<File | null>(null);
  const [is_ingesting, setIsIngesting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [active_module, setActiveModule] = useState<AdminModule>('overview');
  const [is_nav_compact, setIsNavCompact] = useState(false);
  const [is_mobile_nav_open, setIsMobileNavOpen] = useState(false);
  const [notice, setNotice] = useState<NoticeState>(null);

  const auth_headers = { Authorization: `Bearer ${token}` };

  const refreshDatasets = async () => {
    const [collections_res, operations_res] = await Promise.all([
      fetch('/api/admin/qdrant/collections', { headers: auth_headers }),
      fetch('/api/admin/qdrant/operations', { headers: auth_headers }),
    ]);

    if (collections_res.ok) {
      setDatasetsPayload(await collections_res.json());
    }
    if (operations_res.ok) {
      setOperations(await operations_res.json());
    }
  };

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    const fetchAdminData = async () => {
      try {
        const [health_res, metrics_res, config_res] = await Promise.all([
          fetch('/api/admin/health', { headers: auth_headers }),
          fetch('/api/admin/metrics', { headers: auth_headers }),
          fetch('/api/admin/config', { headers: auth_headers }),
        ]);

        if (health_res.ok && metrics_res.ok && config_res.ok) {
          setHealth(await health_res.json());
          setMetrics(await metrics_res.json());
          setConfig(await config_res.json());
          await refreshDatasets();
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

  useEffect(() => {
    if (is_mobile) {
      setIsMobileNavOpen(false);
    }
  }, [is_mobile, active_module]);

  useEffect(() => {
    const collections = datasets_payload?.collections || [];
    if (collections.length === 0) {
      setIngestCollectionName('');
      return;
    }
    if (!collections.some((item) => item.name === ingest_collection_name)) {
      setIngestCollectionName(collections[0].name);
    }
  }, [datasets_payload, ingest_collection_name]);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const handleCreateCollection = async (event: FormEvent) => {
    event.preventDefault();
    const collection_name = new_collection_name.trim();
    if (!collection_name) {
      setNotice({ tone: 'error', message: 'Collection name is required.' });
      return;
    }

    try {
      const response = await fetch('/api/admin/qdrant/collections', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...auth_headers,
        },
        body: JSON.stringify({ name: collection_name, vector_size: new_vector_size, distance: 'cosine' }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Create collection failed.');
      }

      setNewCollectionName('');
      await refreshDatasets();
      setNotice({ tone: 'success', message: `Collection ${collection_name} created.` });
    } catch (error) {
      setNotice({ tone: 'error', message: error instanceof Error ? error.message : 'Create collection failed.' });
    }
  };

  const handleActivateCollection = async (name: string) => {
    try {
      const response = await fetch(`/api/admin/qdrant/collections/${encodeURIComponent(name)}/activate`, {
        method: 'POST',
        headers: auth_headers,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Activate failed.');
      }
      await refreshDatasets();
      setNotice({ tone: 'success', message: `${name} is now active.` });
    } catch (error) {
      setNotice({ tone: 'error', message: error instanceof Error ? error.message : 'Activate failed.' });
    }
  };

  const handleDeleteCollection = async (name: string, is_active: boolean) => {
    if (is_active) {
      setNotice({ tone: 'error', message: 'Cannot delete active collection. Activate another first.' });
      return;
    }

    const confirmed = window.confirm(`Delete collection ${name}? This cannot be undone.`);
    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/qdrant/collections/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: auth_headers,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Delete failed.');
      }
      await refreshDatasets();
      setNotice({ tone: 'success', message: `${name} deleted.` });
    } catch (error) {
      setNotice({ tone: 'error', message: error instanceof Error ? error.message : 'Delete failed.' });
    }
  };

  const handleIngestFile = async (event: FormEvent) => {
    event.preventDefault();
    if (!ingest_collection_name) {
      setNotice({ tone: 'error', message: 'Select a dataset first.' });
      return;
    }
    if (!ingest_file) {
      setNotice({ tone: 'error', message: 'Choose a file to ingest.' });
      return;
    }

    setIsIngesting(true);
    try {
      const form_data = new FormData();
      form_data.append('file', ingest_file);
      const response = await fetch(`/api/admin/qdrant/collections/${encodeURIComponent(ingest_collection_name)}/ingest`, {
        method: 'POST',
        headers: auth_headers,
        body: form_data,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || 'Ingest request failed.');
      }

      setNotice({ tone: 'success', message: `Ingest queued for ${ingest_file.name} -> ${ingest_collection_name}.` });
      setIngestFile(null);
      await refreshDatasets();
      for (let attempt = 0; attempt < 4; attempt += 1) {
        await waitMs(1500);
        await refreshDatasets();
      }
    } catch (error) {
      setNotice({ tone: 'error', message: error instanceof Error ? error.message : 'Ingest request failed.' });
    } finally {
      setIsIngesting(false);
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
          ...auth_headers,
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

  const nav_open = !is_nav_compact || is_mobile;
  const drawer_width = nav_open ? SIDEBAR_WIDTH : SIDEBAR_COMPACT_WIDTH;

  if (loading) {
    return (
      <Box className='page-shell'>
        <main className='query-layout'>
          <Box className='chat-panel'>
            <Box className='message assistant-message loading-message'>
              <Typography variant='caption' color='text.secondary'>Admin</Typography>
              <Typography>Loading dashboard state...</Typography>
            </Box>
          </Box>
        </main>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#F6F7F9' }}>
      <Drawer
        variant={is_mobile ? 'temporary' : 'permanent'}
        open={is_mobile ? is_mobile_nav_open : true}
        onClose={() => setIsMobileNavOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          width: drawer_width,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawer_width,
            boxSizing: 'border-box',
            borderRight: '1px solid #DFE3EA',
            backgroundColor: '#f1f4f8',
            transition: 'width 160ms ease',
            overflowX: 'hidden',
          },
        }}
      >
        <Box className='admin-nav-head'>
          {nav_open && <Typography className='admin-nav-brand'>RAG Operator</Typography>}
          <IconButton
            className='admin-nav-toggle'
            onClick={() => {
              if (is_mobile) {
                setIsMobileNavOpen((prev) => !prev);
              } else {
                setIsNavCompact((prev) => !prev);
              }
            }}
            aria-label='Toggle sidebar'
            size='small'
          >
            {is_nav_compact && !is_mobile ? <MenuOutlinedIcon fontSize='small' /> : <MenuOpenOutlinedIcon fontSize='small' />}
          </IconButton>
        </Box>

        <List className='admin-nav-list' disablePadding>
          <SidebarItem icon={<DashboardOutlinedIcon fontSize='small' />} label='Overview' isOpen={nav_open} isActive={active_module === 'overview'} onClick={() => setActiveModule('overview')} />
          <SidebarItem icon={<FolderOpenOutlinedIcon fontSize='small' />} label='Datasets' isOpen={nav_open} isActive={active_module === 'datasets'} onClick={() => setActiveModule('datasets')} />
          <SidebarItem icon={<InsightsOutlinedIcon fontSize='small' />} label='Metrics' isOpen={nav_open} isActive={active_module === 'phoenix'} onClick={() => setActiveModule('phoenix')} />
          <SidebarItem icon={<TuneOutlinedIcon fontSize='small' />} label='Config' isOpen={nav_open} isActive={active_module === 'config'} onClick={() => setActiveModule('config')} />
        </List>

        <Box className='admin-nav-foot'>
          <SidebarItem icon={<LogoutOutlinedIcon fontSize='small' />} label='Sign Out' isOpen={nav_open} isActive={false} onClick={handleLogout} />
        </Box>
      </Drawer>

      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <AppBar position='sticky' color='transparent' elevation={0} sx={{ borderBottom: '1px solid #DFE3EA', backgroundColor: 'rgba(255,255,255,0.92)' }}>
          <Toolbar sx={{ justifyContent: 'space-between', gap: 1.5, minHeight: '72px !important', px: { xs: 1.5, md: 2.25 } }}>
            <Box>
              <Typography variant='overline' color='text.secondary'>Phase 2 Control Plane</Typography>
              <Typography variant='h5'>{moduleTitle(active_module)}</Typography>
            </Box>
            <Stack direction='row' spacing={1}>
              {is_mobile && <Button variant='outlined' onClick={() => setIsMobileNavOpen(true)}>Menu</Button>}
              <Button variant='outlined' onClick={() => refreshDatasets()}>Refresh</Button>
              <Button variant='contained' onClick={() => navigate('/')}>Back to Search</Button>
            </Stack>
          </Toolbar>
        </AppBar>

        <Box sx={{ p: { xs: 1.5, md: 2.25 } }}>
          {notice && <Notice tone={notice.tone} message={notice.message} />}

          {active_module === 'overview' && (
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 12, sm: 6 }}><MetricCard title='System Status' value={health?.status.toUpperCase() || 'UNKNOWN'} status={health?.status === 'ok' ? 'success' : 'error'} /></Grid>
              <Grid size={{ xs: 12, sm: 6 }}><MetricCard title='Active Pipeline' value={health?.pipeline || '--'} /></Grid>
              <Grid size={{ xs: 12, sm: 6 }}><MetricCard title='Documents Indexed' value={String(health?.document_count ?? 0)} /></Grid>
              <Grid size={{ xs: 12, sm: 6 }}><MetricCard title='Storage Used' value={health?.storage_used || '--'} /></Grid>
              <Grid size={{ xs: 12, sm: 6 }}><MetricCard title='System Uptime' value={health?.uptime || '--'} /></Grid>
              <Grid size={{ xs: 12, sm: 6 }}><MetricCard title='Active Dataset' value={datasets_payload?.active_collection || 'None'} /></Grid>
            </Grid>
          )}

          {active_module === 'datasets' && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Card>
                <CardContent>
                  <Stack component='form' direction={{ xs: 'column', md: 'row' }} spacing={1.25} onSubmit={handleCreateCollection}>
                    <TextField size='small' label='New collection name' value={new_collection_name} onChange={(event) => setNewCollectionName(event.target.value)} fullWidth />
                    <TextField size='small' label='Vector size' type='number' inputProps={{ min: 8 }} value={new_vector_size} onChange={(event) => setNewVectorSize(Number.parseInt(event.target.value || '384', 10))} sx={{ width: { xs: '100%', md: 160 } }} />
                    <Button type='submit' variant='contained'>Create Dataset</Button>
                  </Stack>
                </CardContent>
              </Card>

              <Card>
                <CardContent>
                  <Typography variant='subtitle2' color='text.secondary'>Alias: {datasets_payload?.alias || 'rag_active'}</Typography>
                  <Typography variant='h6' sx={{ mt: 0.5 }}>Active: {datasets_payload?.active_collection || 'None'}</Typography>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Stack component='form' direction={{ xs: 'column', md: 'row' }} spacing={1.25} onSubmit={handleIngestFile}>
                    <FormControl size='small' fullWidth>
                      <InputLabel id='ingest-collection-label'>Target dataset</InputLabel>
                      <Select
                        labelId='ingest-collection-label'
                        label='Target dataset'
                        value={ingest_collection_name}
                        onChange={(event) => setIngestCollectionName(event.target.value)}
                      >
                        {(datasets_payload?.collections || []).map((item) => (
                          <MenuItem key={item.name} value={item.name}>{item.name}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <Button variant='outlined' component='label'>
                      {ingest_file ? ingest_file.name : 'Choose file'}
                      <input
                        type='file'
                        hidden
                        accept='.md,.markdown,.pdf,.txt,.docx'
                        onChange={(event) => setIngestFile(event.target.files?.[0] || null)}
                      />
                    </Button>
                    <Button type='submit' variant='contained' disabled={is_ingesting || !ingest_collection_name || !ingest_file}>
                      {is_ingesting ? 'Queuing...' : 'Add Data'}
                    </Button>
                  </Stack>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <TableContainer>
                    <Table size='small'>
                      <TableHead>
                        <TableRow>
                          <TableCell>Name</TableCell>
                          <TableCell>Vectors</TableCell>
                          <TableCell>Points</TableCell>
                          <TableCell>State</TableCell>
                          <TableCell>Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {(datasets_payload?.collections || []).map((item) => (
                          <TableRow key={item.name}>
                            <TableCell>{item.name}</TableCell>
                            <TableCell>{coerceCount(item.vectors_count)}</TableCell>
                            <TableCell>{coerceCount(item.points_count)}</TableCell>
                            <TableCell>{item.is_active ? <Chip label='Active' color='success' size='small' /> : <Chip label='Inactive' size='small' />}</TableCell>
                            <TableCell>
                              <Stack direction='row' spacing={1}>
                                <Button size='small' variant='outlined' onClick={() => handleActivateCollection(item.name)} disabled={item.is_active}>Activate</Button>
                                <Button size='small' variant='outlined' color='error' onClick={() => handleDeleteCollection(item.name, item.is_active)} disabled={item.is_active}>Delete</Button>
                              </Stack>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
              <Card>
                <CardContent>
                  <Typography variant='h6'>Recent Operations</Typography>
                  <TableContainer sx={{ mt: 1 }}>
                    <Table size='small'>
                      <TableHead>
                        <TableRow>
                          <TableCell>Time</TableCell>
                          <TableCell>Action</TableCell>
                          <TableCell>Target</TableCell>
                          <TableCell>Actor</TableCell>
                          <TableCell>Status</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {operations.slice(0, 20).map((item) => (
                          <TableRow key={item.id}>
                            <TableCell><Typography variant='caption'>{new Date(item.created_at).toLocaleString()}</Typography></TableCell>
                            <TableCell>{item.action}</TableCell>
                            <TableCell>{item.target}</TableCell>
                            <TableCell>{item.actor}</TableCell>
                            <TableCell>{item.status}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Stack>
          )}
          {active_module === 'phoenix' && (
            <Card sx={{ mt: 1 }}>
              <CardContent>
                <Grid container spacing={1.5}>
                  <Grid size={{ xs: 12, md: 4 }}><MetricCard title='Avg Latency' value={`${metrics?.query_latency_ms ?? 0} ms`} /></Grid>
                  <Grid size={{ xs: 12, md: 4 }}><MetricCard title='Retrieval Score' value={`${metrics?.retrieval_score ?? 0}`} /></Grid>
                  <Grid size={{ xs: 12, md: 4 }}><MetricCard title='Total Traces' value={`${metrics?.total_queries ?? 0}`} /></Grid>
                </Grid>
                <Typography color='text.secondary' sx={{ mt: 1.5 }}>Phoenix integration status: {metrics?.phoenix_integration || 'pending'}</Typography>
              </CardContent>
            </Card>
          )}
          {active_module === 'config' && (
            <Card sx={{ mt: 1 }}>
              <CardContent>
                <Box component='form' onSubmit={handleConfigSave}>
                  <Stack spacing={2} sx={{ maxWidth: 620 }}>
                    <FormControl size='small'>
                      <InputLabel id='pipeline-label'>Default Ingest Pipeline</InputLabel>
                      <Select labelId='pipeline-label' label='Default Ingest Pipeline' value={config?.pipeline || 'manual'} onChange={(event) => setConfig((prev) => (prev ? { ...prev, pipeline: event.target.value } : null))}>
                        <MenuItem value='manual'>Manual Python</MenuItem>
                        <MenuItem value='langchain'>LangChain Framework</MenuItem>
                      </Select>
                    </FormControl>

                    <TextField size='small' type='number' label='Top K Documents' inputProps={{ min: 1 }} value={config?.top_k || 5} onChange={(event) => setConfig((prev) => (prev ? { ...prev, top_k: Number.parseInt(event.target.value || '1', 10) } : null))} />

                    <FormControl>
                      <FormLabel>Hybrid Search (RRF)</FormLabel>
                      <RadioGroup row value={String(config?.hybrid_enabled ?? true)} onChange={(event) => setConfig((prev) => (prev ? { ...prev, hybrid_enabled: event.target.value === 'true' } : null))}>
                        <FormControlLabel value='true' control={<Radio />} label='Enable' />
                        <FormControlLabel value='false' control={<Radio />} label='Disable' />
                      </RadioGroup>
                    </FormControl>

                    <Stack direction='row' justifyContent='flex-end'>
                      <Button type='submit' variant='contained'>Save Configuration</Button>
                    </Stack>
                  </Stack>
                </Box>
              </CardContent>
            </Card>
          )}
        </Box>
      </Box>
    </Box>
  );
}

function coerceCount(value: unknown): number {
  if (value === null || value === undefined) {
    return 0;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).reduce((total, item) => total + coerceCount(item), 0);
  }
  return 0;
}

function waitMs(duration: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, duration);
  });
}

function moduleTitle(module: AdminModule) {
  if (module === 'overview') {
    return 'System Overview';
  }
  if (module === 'datasets') {
    return 'Qdrant Dataset Control';
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
  icon: ReactNode;
  label: string;
  isOpen: boolean;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <ListItemButton
      onClick={onClick}
      className={`admin-nav-item ${isActive ? 'active' : ''}`}
      title={label}
      aria-label={label}
      sx={{ justifyContent: isOpen ? 'flex-start' : 'center' }}
    >
      <ListItemIcon sx={{ minWidth: 30, color: 'inherit' }}>{icon}</ListItemIcon>
      {isOpen && <ListItemText primary={label} primaryTypographyProps={{ fontFamily: '"Satoshi", sans-serif', fontWeight: 600 }} />}
    </ListItemButton>
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
    <Card variant='outlined'>
      <CardContent>
        <Typography variant='caption' color='text.secondary'>{title}</Typography>
        <Typography variant='h4' sx={{ mt: 0.5, color: status === 'success' ? 'success.main' : status === 'error' ? 'error.main' : 'text.primary' }}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

function Notice({ tone, message }: { tone: NoticeTone; message: string }) {
  const severity = tone === 'success' ? 'success' : tone === 'error' ? 'error' : 'info';
  return (
    <Alert severity={severity} sx={{ mb: 1.5 }}>
      {message}
    </Alert>
  );
}
