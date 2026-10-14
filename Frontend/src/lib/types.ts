export type ChatSource = {
  id?: string | number;
  title?: string;
  name?: string;
  filename?: string;
  file_name?: string;
  source?: string;
};

export type Message = {
  id?: number | string;
  role: "user" | "model";
  content: string;
  isStreaming?: boolean;
  statusText?: string;
  sources?: ChatSource[];
  images?: string[];
};

export type ChatSession = {
  id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
};

export type ImageChatResponse = {
  ok: boolean;
  answer: string;
  image_url?: string;
  sources?: ChatSource[];
};

export type DocumentItem = {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  created_at?: string;
};

export type DocumentStats = {
  total_documents: number;
  total_chunks: number;
  collection_name: string;
};

export type UserMemoryItem = {
  id: number;
  key: string;
  value: string;
  confidence: number;
  updated_at?: string;
};

export type CrawlArticleResult = {
  post_id?: number | string;
  title: string;
  url?: string;
  status: "new" | "updated" | "skipped" | "failed";
  chunk_count: number;
  error?: string | null;
};

export type CrawlJob = {
  running: boolean;
  max_articles: number;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  done: number;
  current: string | null;
  new: number;
  updated: number;
  skipped: number;
  failed: number;
  errors: string[];
  articles: CrawlArticleResult[];
};

export type CrawlerStatus = {
  total_crawled_articles: number;
  total_crawled_chunks: number;
  latest_announcements: {
    id: string;
    title: string;
    chunks: number;
    created_at?: string;
  }[];
  job?: CrawlJob;
};
