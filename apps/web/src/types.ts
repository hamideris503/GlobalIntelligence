/** Shared Backend DTOs (subset actually rendered; extra fields ignored). */

export interface Source {
  id: string;
  name: string;
  domain: string | null;
  country: string | null;
  type: string;
  language: string | null;
  credibility_score: number | null;
  independence_score: number | null;
  active: boolean;
  last_success: string | null;
  last_error: string | null;
  collection_method: string | null;
  license: string | null;
  terms: string | null;
  homepage_url: string | null;
  canonical_url: string | null;
  geography: string | null;
  category: string | null;
  subcategory: string | null;
  priority: number | null;
  access_model: string | null;
  api_url: string | null;
  api_documentation_url: string | null;
  rss_url: string | null;
  validation_status: string;
  last_checked_at: string | null;
}

export interface ArticleItem {
  id: string;
  title: string | null;
  topics: string[];
  entities: { name: string; type: string }[];
  sentiment: number | null;
  stance: string | null;
  importance: number | null;
  confidence: number | null;
}

export interface ArticleDetail extends ArticleItem {
  summary: string | null;
  language: string | null;
  country: string | null;
  source_name: string | null;
  url: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  event_id: string | null;
  classification_status: string | null;
  classification_error: string | null;
  provider: string | null;
  is_mock: boolean | null;
}

export interface EventItem {
  id: string;
  event_type: string | null;
  action: string | null;
  occurred_at: string | null;
  actors: string[];
  surprise: number | null;
  confidence: number | null;
  article_count: number;
}

export interface ClaimItem {
  id: string;
  event_id: string | null;
  subject: string | null;
  predicate: string | null;
  object: string | null;
  verification_status: string | null;
  supporting_source_count: number | null;
  independent_source_count: number | null;
  source_independence: number | null;
}

export interface EvidenceItem {
  direction: string;
  summary: string | null;
  weight: number | null;
  confidence: number | null;
}

export interface AIProvider {
  provider: string;
  healthy: boolean;
  detail: string;
}

export interface AIStatus {
  mock_mode: boolean;
  default_provider: string;
  roles: string[];
}

export interface WorldState {
  macro_regime: string | null;
  market_regime: string | null;
  confidence: number | null;
  captured_at?: string;
  growth_pressure?: number | null;
  inflation_pressure?: number | null;
  liquidity?: number | null;
  financial_stress?: number | null;
  geopolitical_risk?: number | null;
  energy_risk?: number | null;
  trade_risk?: number | null;
  political_risk?: number | null;
  social_pressure?: number | null;
}

export interface Quote {
  symbol: string;
  value: number | null;
  source_name: string | null;
  observed_at?: string | null;
}

export interface Decision {
  id?: string;
  asset: string;
  decision: string | null;
  score: number | null;
  confidence: number | null;
  rank: number | null;
  direction?: string | null;
  horizon?: string | null;
  main_drivers?: string | null;
  main_risks?: string | null;
  invalidation?: string | null;
  expected_return?: number | null;
  downside?: number | null;
}

export interface Risk {
  category: string;
  score: number | null;
  level: string | null;
}

export interface Forecast {
  id?: string;
  target: string;
  model: string | null;
  expected_value: number | null;
  confidence: number | null;
  horizon?: string | null;
  target_date?: string | null;
  status?: string | null;
  scenario?: string | null;
}

export interface JobRun {
  id: string;
  job_name: string;
  source: string | null;
  status: string;
  message: string | null;
  started_at: string;
}

export interface AlertItem {
  id: string;
  metric: string;
  value: number | null;
  message: string | null;
  severity: string | null;
  status: string;
}

export interface SelfEval {
  score: number | null;
  grade: string | null;
}
