import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { QueryResponse } from '../types';
import { useAuth } from '../context/AuthContext';

const SUGGESTED_QUERIES = [
  'How does this stack stay portable?',
  'Compare manual and langchain implementations.',
  'What changes when reranking is enabled?',
  'Where do citations come from in this workflow?',
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
    <div className="page-shell">
      <nav className="top-nav">
        <div className="top-nav-inner">
          <span className="brand">RAG Operator</span>
          <button className="action-pill" type="button" onClick={() => navigate(isAuthenticated ? '/admin' : '/login')}>
            {isAuthenticated ? 'Admin Dashboard' : 'Sign In'}
          </button>
        </div>
      </nav>

      <main className="query-layout">
        <header className="query-header">
          <p className="query-kicker">Single Query Workflow</p>
          <h1>Ask once. Verify quickly.</h1>
          <p>
            Submit one query, read the grounded answer, then open evidence only when you need to validate retrieval quality.
          </p>
        </header>

        <form className="composer" onSubmit={runQuery} aria-label="Query composer">
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask about architecture, retrieval behavior, or corpus content..."
            aria-label="Query"
          />
          <button type="submit" disabled={!canSubmit}>
            {isLoading ? 'Retrieving...' : 'Send'}
          </button>
        </form>

        <section className="suggestions" aria-label="Suggested queries">
          {SUGGESTED_QUERIES.map((item) => (
            <button key={item} className="suggestion-chip" type="button" onClick={() => setQuery(item)}>
              {item}
            </button>
          ))}
        </section>

        <section className="chat-panel" aria-live="polite">
          {lastQuery && (
            <article className="message user-message">
              <span className="message-label">You</span>
              <p>{lastQuery}</p>
            </article>
          )}

          {isLoading && (
            <article className="message assistant-message loading-message">
              <span className="message-label">Assistant</span>
              <p>Retrieving context and generating response...</p>
            </article>
          )}

          {error && (
            <article className="message assistant-message error-message">
              <span className="message-label">Assistant</span>
              <p>{error}</p>
            </article>
          )}

          {!isLoading && !error && result && (
            <article className="message assistant-message">
              <div className="assistant-head">
                <span className="message-label">Assistant</span>
                <span className={result.insufficient_context ? 'status-pill warning' : 'status-pill success'}>
                  {result.insufficient_context ? 'Insufficient context' : 'Grounded answer'}
                </span>
              </div>

              <p className="assistant-answer">{result.answer}</p>

              <button className="drawer-toggle" type="button" onClick={toggleEvidence}>
                {isEvidenceCollapsed ? 'Show evidence' : 'Hide evidence'}
                <span className="drawer-meta">{result.citations.length} citations</span>
              </button>

              {!isEvidenceCollapsed && (
                <div className="evidence-drawer">
                  {result.citations.length === 0 && <p className="empty-evidence">No citations returned.</p>}
                  {result.citations.map((citation) => {
                    const isExpanded = expandedCitations.has(citation.chunk_id);
                    const shouldTruncate = citation.text.length > SNIPPET_LIMIT;
                    const visibleText = isExpanded || !shouldTruncate
                      ? citation.text
                      : `${citation.text.slice(0, SNIPPET_LIMIT)}...`;

                    return (
                      <article className="evidence-item" key={citation.chunk_id}>
                        <header>
                          <strong>{citation.chunk_id}</strong>
                          <span>{citation.score.toFixed(4)}</span>
                        </header>
                        <p className="evidence-path">{citation.source_path}</p>
                        <p className="evidence-meta">
                          {citation.page ? `Page ${citation.page}` : 'No page'}
                          {citation.section ? ` | ${citation.section}` : ''}
                        </p>
                        <p className="evidence-text">{visibleText}</p>
                        {shouldTruncate && (
                          <button type="button" className="expand-link" onClick={() => toggleCitation(citation.chunk_id)}>
                            {isExpanded ? 'Show less' : 'Show more'}
                          </button>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </article>
          )}

          {!lastQuery && !isLoading && !error && !result && (
            <article className="message assistant-message empty-message">
              <span className="message-label">Assistant</span>
              <p>Start with one question. You will get one response with optional evidence details.</p>
            </article>
          )}
        </section>
      </main>
    </div>
  );
}
