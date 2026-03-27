import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  Collapse,
  Container,
  Paper,
  Stack,
  TextField,
  Toolbar,
  Typography,
} from '@mui/material';
import { QueryResponse } from '../types';
import { useAuth } from '../context/AuthContext';

const SUGGESTED_QUERIES = [
  'What does the document say about portability in Docker Compose?',
];

const DRAWER_STORAGE_KEY = 'rag:evidence-collapsed';
const SNIPPET_LIMIT = 220;

type ApiError = {
  error?: string;
  message?: string;
  detail?: string;
};

export default function Search() {
  const [query, setQuery] = useState('');
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isEvidenceCollapsed, setIsEvidenceCollapsed] = useState(true);
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());

  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    const stored = window.localStorage.getItem(DRAWER_STORAGE_KEY);
    if (stored === 'false') {
      setIsEvidenceCollapsed(false);
    }
  }, []);

  const canSubmit = useMemo(() => query.trim().length > 0 && !isLoading, [query, isLoading]);

  const toggleEvidence = () => {
    setIsEvidenceCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(DRAWER_STORAGE_KEY, String(next));
      return next;
    });
  };

  const toggleCitation = (id: string) => {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const runQuery = async (event: FormEvent) => {
    event.preventDefault();
    const cleaned = query.trim();
    if (!cleaned) {
      setError('Please enter a query before running retrieval.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setLastQuery(cleaned);
    setExpandedCitations(new Set());

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: cleaned }),
      });

      if (!response.ok) {
        const payload = (await response.json()) as ApiError;
        throw new Error(payload.message ?? payload.detail ?? 'Query failed.');
      }

      const payload = (await response.json()) as QueryResponse;
      setResult(payload);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unexpected error while querying.';
      setError(message);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar position='sticky' color='transparent' elevation={0} sx={{ borderBottom: '1px solid #DFE3EA', backgroundColor: 'rgba(255,255,255,0.92)' }}>
        <Toolbar sx={{ width: 'min(1160px, calc(100% - 16px))', mx: 'auto', justifyContent: 'space-between' }}>
          <Typography variant='h6' sx={{ fontFamily: '"Satoshi", sans-serif', fontWeight: 700 }}>RAG Operator</Typography>
          <Button variant='contained' onClick={() => navigate(isAuthenticated ? '/admin' : '/login')}>
            {isAuthenticated ? 'Admin Dashboard' : 'Sign In'}
          </Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth='md' sx={{ py: { xs: 3, md: 5 } }}>
        <Stack spacing={2.5}>
          <Box>
            <Typography variant='overline' color='text.secondary'>Single Query Workflow</Typography>
            <Typography variant='h3' sx={{ mt: 0.5 }}>Ask once. Verify quickly.</Typography>
            <Typography color='text.secondary' sx={{ mt: 1 }}>
              Submit one query, read the grounded answer, then open evidence only when you need to validate retrieval quality.
            </Typography>
          </Box>

          <Box component='form' onSubmit={runQuery}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
              <TextField
                fullWidth
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder='Ask about architecture, retrieval behavior, or corpus content...'
                size='small'
              />
              <Button type='submit' variant='contained' disabled={!canSubmit} sx={{ minWidth: { sm: 120 } }}>
                {isLoading ? 'Retrieving...' : 'Send'}
              </Button>
            </Stack>
          </Box>

          <Stack direction='row' spacing={1} flexWrap='wrap' useFlexGap>
            {SUGGESTED_QUERIES.map((item) => (
              <Chip key={item} label={item} variant='outlined' onClick={() => setQuery(item)} sx={{ borderRadius: '9999px' }} />
            ))}
          </Stack>

          <Paper sx={{ p: 2.25, borderRadius: '14px', boxShadow: '0 12px 32px rgba(14,17,22,0.08)' }}>
            <Stack spacing={1.5}>
              {lastQuery && (
                <Paper variant='outlined' sx={{ p: 1.5, backgroundColor: '#edf2ff' }}>
                  <Typography variant='caption' color='text.secondary'>You</Typography>
                  <Typography sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}>{lastQuery}</Typography>
                </Paper>
              )}

              {isLoading && (
                <Paper variant='outlined' sx={{ p: 1.5 }}>
                  <Typography variant='caption' color='text.secondary'>Assistant</Typography>
                  <Typography sx={{ mt: 0.5 }}>Retrieving context and generating response...</Typography>
                </Paper>
              )}

              {error && <Alert severity='error'>{error}</Alert>}

              {!isLoading && !error && result && (
                <Paper variant='outlined' sx={{ p: 1.5, backgroundColor: '#fcfdff' }}>
                  <Stack direction='row' alignItems='center' justifyContent='space-between' flexWrap='wrap' gap={1}>
                    <Typography variant='caption' color='text.secondary'>Assistant</Typography>
                    <Chip
                      size='small'
                      color={result.insufficient_context ? 'warning' : 'success'}
                      label={result.insufficient_context ? 'Insufficient context' : 'Grounded answer'}
                    />
                  </Stack>

                  <Typography sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>{result.answer}</Typography>

                  <Button
                    fullWidth
                    variant='outlined'
                    onClick={toggleEvidence}
                    sx={{ mt: 1.5, justifyContent: 'space-between' }}
                  >
                    {isEvidenceCollapsed ? 'Show evidence' : 'Hide evidence'}
                    <Typography variant='caption'>{result.citations.length} citations</Typography>
                  </Button>

                  <Collapse in={!isEvidenceCollapsed}>
                    <Stack spacing={1.25} sx={{ pt: 1.25 }}>
                      {result.citations.length === 0 && <Typography color='text.secondary'>No citations returned.</Typography>}
                      {result.citations.map((citation) => {
                        const isExpanded = expandedCitations.has(citation.chunk_id);
                        const shouldTruncate = citation.text.length > SNIPPET_LIMIT;
                        const visibleText = isExpanded || !shouldTruncate
                          ? citation.text
                          : `${citation.text.slice(0, SNIPPET_LIMIT)}...`;

                        return (
                          <Paper key={citation.chunk_id} variant='outlined' sx={{ p: 1.25 }}>
                            <Stack direction='row' justifyContent='space-between' gap={1}>
                              <Typography variant='caption' sx={{ color: '#4f5f78' }}>{citation.chunk_id}</Typography>
                              <Typography variant='caption' sx={{ color: '#4f5f78' }}>{citation.score.toFixed(4)}</Typography>
                            </Stack>
                            <Typography variant='caption' sx={{ mt: 0.5, display: 'block', color: '#5d697c' }}>{citation.source_path}</Typography>
                            <Typography variant='caption' sx={{ color: '#5d697c' }}>
                              {citation.page ? `Page ${citation.page}` : 'No page'}{citation.section ? ` | ${citation.section}` : ''}
                            </Typography>
                            <Typography sx={{ mt: 1 }}>{visibleText}</Typography>
                            {shouldTruncate && (
                              <Button size='small' sx={{ mt: 0.5, px: 0 }} onClick={() => toggleCitation(citation.chunk_id)}>
                                {isExpanded ? 'Show less' : 'Show more'}
                              </Button>
                            )}
                          </Paper>
                        );
                      })}
                    </Stack>
                  </Collapse>
                </Paper>
              )}

              {!lastQuery && !isLoading && !error && !result && (
                <Paper variant='outlined' sx={{ p: 1.5, backgroundColor: '#f8fafc' }}>
                  <Typography variant='caption' color='text.secondary'>Assistant</Typography>
                  <Typography sx={{ mt: 0.5 }}>Start with one question. You will get one response with optional evidence details.</Typography>
                </Paper>
              )}
            </Stack>
          </Paper>
        </Stack>
      </Container>
    </Box>
  );
}
