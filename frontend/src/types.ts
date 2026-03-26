export type Citation = {
  chunk_id: string;
  source_path: string;
  source_type: string;
  checksum: string;
  pipeline: string;
  text: string;
  score: number;
  document_id: string;
  page: number | null;
  section: string | null;
};

export type QueryResponse = {
  pipeline: string;
  question: string;
  answer: string;
  citations: Citation[];
  insufficient_context: boolean;
};
