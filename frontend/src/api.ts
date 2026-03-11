const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface GenerateConfigRequest {
  budget: number;
  usage: "gaming" | "video_editing" | "general";
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
  total_price: number;
  estimated_power_w: number;
  parts: PartResponse[];
}

export async function generateConfig(
  request: GenerateConfigRequest
): Promise<GenerateConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/generate-config`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to generate configuration");
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

export async function getScraperStatus(): Promise<ScraperStatus> {
  const response = await fetch(`${API_BASE_URL}/scraper/status`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to get scraper status");
  }

  return response.json();
}
