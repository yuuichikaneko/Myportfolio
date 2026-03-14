const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001/api";

export interface CustomBudgetWeights {
  cpu: number;
  cpu_cooler: number;
  gpu: number;
  motherboard: number;
  memory: number;
  storage: number;
  psu: number;
  case: number;
}

async function safeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch {
    throw new Error(
      `API server is unreachable: ${API_BASE_URL}. Start Django first (python django/manage.py runserver 8001).`
    );
  }
}

async function parseApiError(response: Response, fallbackMessage: string): Promise<Error> {
  try {
    const error = await response.json();
    return new Error(error.detail || fallbackMessage);
  } catch {
    return new Error(fallbackMessage);
  }
}

export interface GenerateConfigRequest {
  budget: number;
  usage: "gaming" | "creator" | "business" | "standard" | "video_editing" | "general";
  cooler_type?: "air" | "liquid";
  radiator_size?: "120" | "240" | "360";
  cooling_profile?: "silent" | "performance";
  case_size?: "mini" | "mid" | "full";
  cpu_vendor?: "intel" | "amd";
  build_priority?: "cost" | "spec";
  custom_budget_weights?: CustomBudgetWeights;
}

export interface PartResponse {
  category: string;
  name: string;
  price: number;
  url: string;
}

export interface GenerateConfigResponse {
  usage: string;
  budget: number;
  cooler_type?: "air" | "liquid" | "any";
  radiator_size?: "120" | "240" | "360" | "any";
  cooling_profile?: "silent" | "performance" | "balanced";
  case_size?: "mini" | "mid" | "full" | "any";
  cpu_vendor?: "intel" | "amd" | "any";
  build_priority?: "cost" | "spec" | "balanced";
  custom_budget_weights?: Record<string, number> | null;
  configuration_id: number | null;
  total_price: number;
  estimated_power_w: number;
  parts: PartResponse[];
}

export interface SavedPartResponse {
  id: number;
  part_type: string;
  part_type_display: string;
  name: string;
  price: number;
  specs: Record<string, unknown>;
  url: string;
  scraped_at: string;
  updated_at: string;
}

export interface SavedConfigurationResponse {
  id: number;
  budget: number;
  usage: "gaming" | "creator" | "business" | "standard" | "video_editing" | "general";
  usage_display: string;
  total_price: number;
  cpu_data: SavedPartResponse | null;
  cpu_cooler_data: SavedPartResponse | null;
  gpu_data: SavedPartResponse | null;
  motherboard_data: SavedPartResponse | null;
  memory_data: SavedPartResponse | null;
  storage_data: SavedPartResponse | null;
  psu_data: SavedPartResponse | null;
  case_data: SavedPartResponse | null;
  created_at: string;
}

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export async function generateConfig(
  request: GenerateConfigRequest
): Promise<GenerateConfigResponse> {
  const response = await safeFetch(`${API_BASE_URL}/configurations/generate/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to generate configuration");
  }

  return response.json();
}

export interface ScraperStatus {
  cache_enabled: boolean;
  cache_ttl_seconds: number;
  last_update_time: string | null;
  cached_categories: string[];
  total_parts_in_db: number;
  retry_count: number;
  rate_limit_delay: number;
}

export interface MarketPriceRangeSource {
  url: string;
  min: number | null;
  max: number | null;
  count: number;
}

export interface MarketPriceRangeResponse {
  min: number;
  max: number;
  default: number;
  currency: string;
  sources: Record<string, MarketPriceRangeSource>;
}

export async function getScraperStatus(): Promise<ScraperStatus> {
  const response = await safeFetch(`${API_BASE_URL}/scraper-status/summary/`);

  if (!response.ok) {
    throw await parseApiError(response, "Failed to get scraper status");
  }

  return response.json();
}

export async function getMarketPriceRange(): Promise<MarketPriceRangeResponse> {
  const response = await safeFetch(`${API_BASE_URL}/market-price-range/`);

  if (!response.ok) {
    throw await parseApiError(response, "Failed to get market price range");
  }

  return response.json();
}

export async function getSavedConfigurations(): Promise<SavedConfigurationResponse[]> {
  const response = await safeFetch(`${API_BASE_URL}/configurations/`);

  if (!response.ok) {
    throw await parseApiError(response, "Failed to get saved configurations");
  }

  const data: PaginatedResponse<SavedConfigurationResponse> = await response.json();
  return data.results;
}

export async function deleteSavedConfiguration(id: number): Promise<void> {
  const response = await safeFetch(`${API_BASE_URL}/configurations/${id}/`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to delete saved configuration");
  }
}

export interface PartPriceRange {
  label: string;
  min: number | null;
  max: number | null;
  avg: number | null;
  count: number;
}

export type PartPriceRangesResponse = Record<string, PartPriceRange>;

export async function getPartPriceRanges(): Promise<PartPriceRangesResponse> {
  const response = await safeFetch(`${API_BASE_URL}/part-price-ranges/`);

  if (!response.ok) {
    throw await parseApiError(response, "Failed to get part price ranges");
  }

  return response.json();
}
