import { afterEach, describe, expect, it, vi } from "vitest";
import {
  deleteSavedConfiguration,
  generateConfig,
  getSavedConfigurations,
  getScraperStatus,
} from "./api";

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("gets scraper status", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          cache_enabled: true,
          cache_ttl_seconds: 3600,
          last_update_time: null,
          cached_categories: ["cpu"],
          total_parts_in_db: 1,
          retry_count: 3,
          rate_limit_delay: 1,
        }),
        { status: 200 }
      )
    );

    const result = await getScraperStatus();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/scraper-status/summary/",
      undefined
    );
    expect(result.total_parts_in_db).toBe(1);
  });

  it("gets saved configurations from paginated response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 10,
              budget: 150000,
              usage: "gaming",
              usage_display: "Gaming",
              total_price: 140000,
              cpu_data: null,
              gpu_data: null,
              motherboard_data: null,
              memory_data: null,
              storage_data: null,
              psu_data: null,
              case_data: null,
              created_at: "2026-03-14T10:00:00Z",
            },
          ],
        }),
        { status: 200 }
      )
    );

    const result = await getSavedConfigurations();

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(10);
  });

  it("sends delete request for saved configuration", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    await deleteSavedConfiguration(7);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/configurations/7/",
      { method: "DELETE" }
    );
  });

  it("returns generated config response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          usage: "gaming",
          budget: 150000,
          configuration_id: 1,
          total_price: 140000,
          estimated_power_w: 550,
          parts: [{ category: "cpu", name: "Sample", price: 30000, url: "https://example.com" }],
        }),
        { status: 200 }
      )
    );

    const result = await generateConfig({ budget: 150000, usage: "gaming" });

    expect(result.configuration_id).toBe(1);
    expect(result.parts[0].category).toBe("cpu");
  });
});
