import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { GenerateConfigResponse, SavedConfigurationResponse } from "./api";
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
      entry_count: 4,
      excluded_count: 3,
      entries: {
        count: 4,
        next: null,
        previous: null,
        results: [
          { vendor: "intel", model_name: "Core i5-12400F", perf_score: 3918, source_url: "https://example.com/intel" },
          { vendor: "amd", model_name: "Ryzen 9 9950X3D", perf_score: 7390, price: 114470, value_score: 0.064558, source_url: "https://example.com/amd3" },
          { vendor: "amd", model_name: "Ryzen 7 9700X", perf_score: 3904, price: 40180, value_score: 0.097163, source_url: "https://example.com/amd4" },
          { vendor: "amd", model_name: "Ryzen 7 7800X3D", perf_score: 3609, price: 49800, value_score: 0.07247, source_url: "https://example.com/amd" },
          { vendor: "amd", model_name: "Ryzen 5 9600X", perf_score: 3163, price: 35280, value_score: 0.089654, source_url: "https://example.com/amd5" },
        ],
      },
    })),
    compareCpuSelectionMaterial: vi.fn(async () => ({
      requested_models: ["Core i5-12400F", "Ryzen 7 9700X", "Ryzen 7 7800X3D", "Ryzen 5 9600X"],
      missing_models: [],
      results: [
        { vendor: "intel", model_name: "Core i5-12400F", perf_score: 3918, source_url: "https://example.com/intel" },
        { vendor: "amd", model_name: "Ryzen 7 9700X", perf_score: 3904, price: 40180, value_score: 0.097163, source_url: "https://example.com/amd4" },
        { vendor: "amd", model_name: "Ryzen 7 7800X3D", perf_score: 3609, price: 49800, value_score: 0.07247, source_url: "https://example.com/amd" },
        { vendor: "amd", model_name: "Ryzen 5 9600X", perf_score: 3163, price: 35280, value_score: 0.089654, source_url: "https://example.com/amd5" },
      ],
    })),
  };
});

describe("ResultView", () => {
  it("renders gaming cpu ranking entries and highlights current cpu", async () => {
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
      expect(screen.getByText("ゲーミングCPU順位（AMD・スペック順）")).toBeInTheDocument();
    });

    expect(screen.getByText("新規生成ID: 1")).toBeInTheDocument();

    expect(screen.getByText("スペック重視ではX3Dを優先して性能順に並べています。")).toBeInTheDocument();
    expect(screen.getByText("元データ: 4 / 除外: 3")).toBeInTheDocument();
    expect(screen.getByText("Ryzen 7 7800X3D")).toBeInTheDocument();
    expect(screen.getByText("Ryzen 5 9600X")).toBeInTheDocument();
    expect(screen.queryByText("Ryzen 9 9950X3D")).not.toBeInTheDocument();
    expect(screen.queryByText("INTEL")).not.toBeInTheDocument();

    const badges = screen.getAllByText("現在の構成");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });

  it("renders gaming cpu cost ranking entries when build priority is cost", async () => {
    const config: GenerateConfigResponse = {
      usage: "gaming",
      build_priority: "cost",
      budget: 200000,
      configuration_id: 2,
      total_price: 178000,
      estimated_power_w: 520,
      parts: [
        { category: "cpu", name: "Ryzen 7 7800X3D BOX", price: 60000, url: "https://example.com/cpu" },
        { category: "gpu", name: "RTX 5070", price: 90000, url: "https://example.com/gpu" },
      ],
    };

    render(<ResultView config={config} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("ゲーミングCPU順位（AMD・コスパ順）")).toBeInTheDocument();
    });

    expect(screen.getByText("新規生成ID: 2")).toBeInTheDocument();

    expect(screen.getByText("コスパ重視では性能/価格で順位付けしています。")).toBeInTheDocument();
    expect(screen.getByText("Ryzen 7 9700X")).toBeInTheDocument();
    expect(screen.getByText("Ryzen 5 9600X")).toBeInTheDocument();
    expect(screen.getByText("0.097163")).toBeInTheDocument();
    expect(screen.getByText("0.089654")).toBeInTheDocument();
    expect(screen.queryByText("Ryzen 9 9950X3D")).not.toBeInTheDocument();
  });

  it("shows saved configuration id label for saved results", async () => {
    const savedConfig: SavedConfigurationResponse = {
      id: 787,
      budget: 169980,
      usage: "gaming",
      usage_display: "ゲーミングPC",
      total_price: 169868,
      cpu_data: {
        id: 1,
        part_type: "cpu",
        part_type_display: "CPU",
        name: "AMD Ryzen 7 7700 BOX",
        price: 41800,
        specs: {},
        url: "https://example.com/cpu",
        scraped_at: "2026-04-05T12:00:00Z",
        updated_at: "2026-04-05T12:00:00Z",
      },
      cpu_cooler_data: null,
      gpu_data: {
        id: 2,
        part_type: "gpu",
        part_type_display: "グラフィックボード",
        name: "RTX 3050 6GB",
        price: 32360,
        specs: {},
        url: "https://example.com/gpu",
        scraped_at: "2026-04-05T12:00:00Z",
        updated_at: "2026-04-05T12:00:00Z",
      },
      motherboard_data: null,
      memory_data: null,
      storage_data: null,
      storage2_data: null,
      storage3_data: null,
      os_data: null,
      psu_data: null,
      case_data: null,
      created_at: "2026-04-05T12:00:00Z",
    };

    render(<ResultView config={savedConfig} onBack={() => {}} />);

    expect(screen.getByText("保存済み構成ID: 787")).toBeInTheDocument();
    expect(screen.queryByText("新規生成ID: 787")).not.toBeInTheDocument();
  });
});
