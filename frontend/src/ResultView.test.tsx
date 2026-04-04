import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { GenerateConfigResponse } from "./api";
import { ResultView } from "./ResultView";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    getLatestGpuPerformance: vi.fn(async () => ({
      snapshot: {
        id: 1,
        source_name: "Dospara GPU Performance",
        source_url: "https://example.com/gpu",
        updated_at_source: "2026-04-04",
        score_note: "Higher is better",
        parser_version: "v1",
        fetched_at: "2026-04-04T00:00:00Z",
      },
      entries: {
        count: 3,
        next: null,
        previous: null,
        results: [
          {
            gpu_name: "RTX 5070 12GB",
            model_key: "RTX 5070",
            vendor: "nvidia",
            vram_gb: 12,
            perf_score: 3931,
            detail_url: "https://example.com/5070",
            rank_global: 12,
          },
          {
            gpu_name: "RX 9070 XT 16GB",
            model_key: "RX 9070 XT",
            vendor: "amd",
            vram_gb: 16,
            perf_score: 3673,
            detail_url: "https://example.com/9070xt",
            rank_global: 13,
          },
          {
            gpu_name: "RTX 5060 Ti 16GB",
            model_key: "RTX 5060 TI",
            vendor: "nvidia",
            vram_gb: 16,
            perf_score: 2500,
            detail_url: "https://example.com/5060ti",
            rank_global: 14,
          },
        ],
      },
    })),
    compareGpuPerformance: vi.fn(async () => ({
      snapshot_id: 1,
      requested_models: ["RTX 5070", "RX 9070 XT"],
      missing_models: [],
      results: [
        {
          gpu_name: "RTX 5070 12GB",
          model_key: "RTX 5070",
          vendor: "nvidia",
          vram_gb: 12,
          perf_score: 3931,
          detail_url: "https://example.com/5070",
          rank_global: 12,
        },
        {
          gpu_name: "RX 9070 XT 16GB",
          model_key: "RX 9070 XT",
          vendor: "amd",
          vram_gb: 16,
          perf_score: 3673,
          detail_url: "https://example.com/9070xt",
          rank_global: 13,
        },
      ],
    })),
    getLatestCpuSelectionMaterial: vi.fn(async () => ({
      source_name: "dospara_cpu_comparison_pages",
      source_urls: ["https://example.com/amd", "https://example.com/intel"],
      exclude_intel_13_14: true,
      entry_count: 3,
      excluded_count: 2,
      entries: {
        count: 3,
        next: null,
        previous: null,
        results: [
          { vendor: "intel", model_name: "Core i5-12400F", perf_score: 3918, source_url: "https://example.com/intel" },
          { vendor: "amd", model_name: "Ryzen 7 7800X3D", perf_score: 3609, source_url: "https://example.com/amd" },
          { vendor: "amd", model_name: "Ryzen 5 7600", perf_score: 3275, source_url: "https://example.com/amd2" },
        ],
      },
    })),
    compareCpuSelectionMaterial: vi.fn(async () => ({
      requested_models: ["Core i5-12400F", "Ryzen 7 7800X3D", "Ryzen 5 7600"],
      missing_models: [],
      results: [
        { vendor: "intel", model_name: "Core i5-12400F", perf_score: 3918, source_url: "https://example.com/intel" },
        { vendor: "amd", model_name: "Ryzen 7 7800X3D", perf_score: 3609, source_url: "https://example.com/amd" },
        { vendor: "amd", model_name: "Ryzen 5 7600", perf_score: 3275, source_url: "https://example.com/amd2" },
      ],
    })),
  };
});

describe("ResultView", () => {
  it("renders CPU selection panel entries and highlights current CPU", async () => {
    const config: GenerateConfigResponse = {
      usage: "gaming",
      budget: 200000,
      configuration_id: 1,
      total_price: 188000,
      estimated_power_w: 550,
      parts: [
        { category: "cpu", name: "Ryzen 7 7800X3D BOX", price: 60000, url: "https://example.com/cpu" },
        { category: "gpu", name: "RTX 5070", price: 90000, url: "https://example.com/gpu" },
      ],
    };

    render(<ResultView config={config} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("CPU選考資料（AMD/Intel）")).toBeInTheDocument();
    });

    expect(screen.getByText("件数: 3 / 除外: 2")).toBeInTheDocument();
    expect(screen.getByText("Ryzen 7 7800X3D")).toBeInTheDocument();
    expect(screen.getByText("INTEL")).toBeInTheDocument();
    expect(screen.getByText("Intel 13世代/14世代は除外して集計しています。")).toBeInTheDocument();

    const badges = screen.getAllByText("現在の構成");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });
});
