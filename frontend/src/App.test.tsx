import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import App from './App';

const mockPayload = {
  pipeline: 'manual',
  question: 'test query',
  answer: 'sample answer [doc-1]',
  insufficient_context: false,
  citations: [
    {
      chunk_id: 'doc-1',
      source_path: '/workspace/data/corpus/rag-basics.md',
      source_type: 'markdown',
      checksum: '123',
      pipeline: 'manual',
      text: 'citation text',
      score: 0.9,
      document_id: 'doc',
      page: null,
      section: 'Overview',
    },
  ],
};

describe('App', () => {
  it('prefills the input when clicking a suggested card', async () => {
    render(<App />);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /Compare manual vs langchain implementations/i }));

    expect(screen.getByLabelText('Query')).toHaveValue('Compare manual vs langchain implementations');
  });

  it('submits query and renders answer with citations', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockPayload,
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText('Query'), 'test query');
    await user.click(screen.getByRole('button', { name: /^Query/i }));

    expect(fetchMock).toHaveBeenCalledWith('/api/query', expect.objectContaining({ method: 'POST' }));
    expect(await screen.findByText(/sample answer/i)).toBeInTheDocument();
    expect(await screen.findByText(/rag-basics\.md/i)).toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});
