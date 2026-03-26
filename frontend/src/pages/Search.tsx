import { FormEvent, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { QueryResponse } from '../types';
import { useAuth } from '../context/AuthContext';

const SUGGESTED_QUERIES = [
  'Understand our 2024 roadmap',
  'Compare manual vs langchain implementations',
  'How does this stack stay portable?',
  'What does reranking change in results?',
];

type ApiError = {
  error?: string;
  message?: string;
  detail?: string;
};

export default function Search() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const canSubmit = useMemo(() => query.trim().length > 0 && !isLoading, [query, isLoading]);

  const runQuery = async (event: FormEvent) => {
    event.preventDefault();
    const cleaned = query.trim();
    if (!cleaned) {
      setError('Please enter a query before running retrieval.');
      return;
    }

    setIsLoading(true);
    setError(null);

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
          <span className="brand">The Intelligent Layer</span>
          <div className="top-links">
            <span className="active">Search</span>
            <a href="#">About</a>
            <a href="#">Documentation</a>
          </div>
          <button 
            className="action-pill" 
            type="button" 
            onClick={() => navigate(isAuthenticated ? '/admin' : '/login')}
          >
            {isAuthenticated ? 'Admin Dashboard' : 'Sign In'}
          </button>
        </div>
      </nav>

      <main className="content">
        <section className="hero">
          <span className="eyebrow">Editorial Intelligence v2.4</span>
          <h1>
            Ask your data
            <br />
            <span>anything.</span>
          </h1>
          <p>
            A high-fidelity RAG interface designed for clarity and deep retrieval. Treat your knowledge base with
            the prestige it deserves.
          </p>

          <form className="query-panel" onSubmit={runQuery}>
            <span className="material-symbols-outlined">search</span>
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search implementation guides or product roadmaps..."
              aria-label="Query"
            />
            <button type="submit" disabled={!canSubmit}>
              {isLoading ? 'Running...' : 'Query'}
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          </form>

          <section className="suggestions">
            <div className="suggestions-title">Suggested Insights</div>
            <div className="suggestion-grid">
              {SUGGESTED_QUERIES.map((item) => (
                <button key={item} className="suggestion-card" type="button" onClick={() => setQuery(item)}>
                  <span>{item}</span>
                  <span className="material-symbols-outlined">north_east</span>
                </button>
              ))}
            </div>
          </section>
        </section>

        <section className="results">
          <h2>Response</h2>
          {error && <div className="error-box">{error}</div>}
          {!error && result && (
            <>
              <div className="answer-box">
                <div className="answer-meta">
                  <span>Pipeline: {result.pipeline}</span>
                  <span>{result.insufficient_context ? 'Insufficient context' : 'Grounded answer'}</span>
                </div>
                <p>{result.answer}</p>
              </div>

              <div className="citations-grid">
                {result.citations.map((citation) => (
                  <article className="citation-card" key={citation.chunk_id}>
                    <header>
                      <strong>{citation.chunk_id}</strong>
                      <span>{citation.score.toFixed(4)}</span>
                    </header>
                    <p className="source-path">{citation.source_path}</p>
                    <p className="source-meta">
                      {citation.page ? `Page ${citation.page}` : 'No page'}
                      {citation.section ? ` | ${citation.section}` : ''}
                    </p>
                    <p className="snippet">{citation.text}</p>
                  </article>
                ))}
              </div>
            </>
          )}
          {!error && !result && <p className="placeholder">Run a query to retrieve grounded context and generated output.</p>}
        </section>
      </main>

      <footer className="footer">
        <span>The Intelligent Layer</span>
        <small>Secured via RAG Intelligence</small>
      </footer>
    </div>
  );
}
