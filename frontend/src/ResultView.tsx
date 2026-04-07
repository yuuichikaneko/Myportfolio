import { useEffect, useMemo, useState } from "react";
import {
  compareCpuSelectionMaterial,
  compareGpuPerformance,
  CpuSelectionEntryResponse,
  CpuSelectionMaterialCompareResponse,
  CpuSelectionMaterialLatestResponse,
  getLatestGpuPerformance,
  getLatestCpuSelectionMaterial,
  GenerateConfigResponse,
  GpuPerformanceCompareResponse,
  GpuPerformanceEntryResponse,
  GpuPerformanceLatestResponse,
  SavedConfigurationResponse,
  SavedPartResponse,
} from "./api";

interface ResultProps {
  config: GenerateConfigResponse | SavedConfigurationResponse;
  onBack: () => void;
}

interface NormalizedResultPart {
  category: string;
  name: string;
  price: number;
  url: string;
  specs: Record<string, unknown> | null;
  isPlaceholder?: boolean;
}

const PART_DISPLAY_ORDER = [
  "cpu",
  "cpu_cooler",
  "gpu",
  "motherboard",
  "memory",
  "storage",
  "storage2",
  "storage3",
  "os",
  "psu",
  "case",
] as const;

const STORAGE_MEDIA_LABELS: Record<"ssd" | "hdd" | "other", string> = {
  ssd: "SSD",
  hdd: "HDD",
  other: "不明",
};

const STORAGE_INTERFACE_LABELS: Record<"nvme" | "sata" | "other", string> = {
  nvme: "NVMe",
  sata: "SATA",
  other: "接続方式不明",
};

const GPU_POWER_RULES: Array<[RegExp, number]> = [
  [/rtx\s*5090/i, 575],
  [/rtx\s*5080/i, 360],
  [/rtx\s*5070\s*ti/i, 300],
  [/rtx\s*5070/i, 250],
  [/rtx\s*5060\s*ti/i, 180],
  [/rtx\s*5060/i, 150],
  [/rtx\s*5050/i, 130],
  [/rtx\s*3050/i, 70],
  [/rx\s*9070\s*xt/i, 320],
  [/rx\s*9070/i, 260],
  [/rx\s*9060\s*xt/i, 190],
  [/rx\s*6400/i, 55],
  [/arc\s*b580/i, 190],
  [/arc\s*b570/i, 150],
  [/arc\s*a310/i, 50],
];

function extractGpuModelKey(text: string) {
  const normalized = text.replace(/\s+/g, " ").trim();
  const patterns = [
    /RTX\s*\d{4}\s*Ti\s*SUPER/i,
    /RTX\s*\d{4}\s*SUPER/i,
    /RTX\s*\d{4}\s*Ti/i,
    /RTX\s*\d{4}/i,
    /GTX\s*\d{3,4}\s*Ti/i,
    /GTX\s*\d{3,4}/i,
    /GT\s*\d{3,4}/i,
    /RX\s*\d{4}\s*XTX/i,
    /RX\s*\d{4}\s*XT/i,
    /RX\s*\d{4}\s*GRE/i,
    /RX\s*\d{4}/i,
    /Intel\s+Arc\s+[AB]\d{3,4}/i,
    /Arc\s+[AB]\d{3,4}/i,
  ];

  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match) {
      return match[0].replace(/\s+/g, " ").trim().toUpperCase();
    }
  }

  return null;
}

function normalizeGpuModelKey(text: string) {
  return text.replace(/[^A-Z0-9]+/g, "").toUpperCase();
}

function formatGpuModelLabel(entry: GpuPerformanceEntryResponse) {
  const vramLabel = entry.vram_gb ? ` ${entry.vram_gb}GB` : "";
  return `${entry.model_key}${vramLabel}`;
}

function extractCpuModelKey(text: string) {
  const normalized = text.replace(/\s+/g, " ").trim();
  const patterns = [
    /Ryzen\s+[3579]\s+\d{4}[A-Z0-9]*/i,
    /Core\s+Ultra\s+[3579]\s+\d{3}[A-Z]*/i,
    /Core\s+i[3579]\s*-?\s*\d{4,5}[A-Z]*/i,
    /Pentium\s+G\d{3,4}[A-Z]*/i,
    /Celeron\s+G\d{3,4}[A-Z]*/i,
  ];

  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match) {
      return match[0].replace(/\s+/g, " ").trim().toUpperCase();
    }
  }

  return null;
}

function formatCpuModelLabel(entry: CpuSelectionEntryResponse) {
  return entry.model_name;
}

const GAMING_CPU_EXCLUDED_MODELS = new Set([
  "RYZEN 5 7500F",
  "RYZEN 5 9500F",
  "RYZEN 7 8700G",
  "RYZEN 9 9900X",
  "RYZEN 9 9900X3D",
  "RYZEN 9 9950X",
  "RYZEN 9 9950X3D",
]);

function isGamingCpuX3dModel(modelName: string) {
  return /x3d/i.test(modelName);
}

const RANKING_DISPLAY_LIMIT = 5;

function sortGamingCpuEntries(entries: CpuSelectionEntryResponse[], mode: "cost" | "spec") {
  const sortedEntries = entries
    .slice()
    .filter((entry) => entry.vendor.toLowerCase() === "amd")
    .filter((entry) => !GAMING_CPU_EXCLUDED_MODELS.has(entry.model_name.replace(/\s+/g, " ").trim().toUpperCase()))
    .sort((left, right) => {
      if (mode === "cost") {
        const leftRank = left.cost_rank ?? Number.MAX_SAFE_INTEGER;
        const rightRank = right.cost_rank ?? Number.MAX_SAFE_INTEGER;

        if (leftRank !== rightRank) {
          return leftRank - rightRank;
        }

        const leftValue = left.value_score ?? (left.price && left.price > 0 ? left.perf_score / left.price : 0);
        const rightValue = right.value_score ?? (right.price && right.price > 0 ? right.perf_score / right.price : 0);

        if (rightValue !== leftValue) {
          return rightValue - leftValue;
        }

        if (right.perf_score !== left.perf_score) {
          return right.perf_score - left.perf_score;
        }

        return (left.price ?? Number.MAX_SAFE_INTEGER) - (right.price ?? Number.MAX_SAFE_INTEGER);
      }

      const leftIsX3d = isGamingCpuX3dModel(left.model_name);
      const rightIsX3d = isGamingCpuX3dModel(right.model_name);

      if (leftIsX3d !== rightIsX3d) {
        return Number(rightIsX3d) - Number(leftIsX3d);
      }

      if (right.perf_score !== left.perf_score) {
        return right.perf_score - left.perf_score;
      }

      return left.model_name.localeCompare(right.model_name, "ja");
    });

  return sortedEntries.slice(0, RANKING_DISPLAY_LIMIT);
}

export function ResultView({ config, onBack }: ResultProps) {
  const formatCurrency = (price: number) =>
    new Intl.NumberFormat("ja-JP", {
      style: "currency",
      currency: "JPY",
    }).format(price);

  const parsePsuCapacityWatts = (name: string) => {
    const match = name.match(/(\d{3,4})\s*W/i);
    return match ? Number(match[1]) : null;
  };

  const PART_CATEGORY_LABELS: Record<string, string> = {
    cpu: "CPU",
    cpu_cooler: "CPUクーラー",
    gpu: "グラフィックボード",
    motherboard: "マザーボード",
    memory: "メモリー",
    storage: "ストレージ",
    storage2: "ストレージ2",
    storage3: "ストレージ3",
    os: "OS",
    psu: "電源",
    case: "ケース",
  };

  const isSavedConfiguration = (value: GenerateConfigResponse | SavedConfigurationResponse): value is SavedConfigurationResponse =>
    "created_at" in value;

  const sortPartsByDisplayOrder = (parts: NormalizedResultPart[]) => {
    return [...parts].sort((left, right) => {
      const leftIndex = PART_DISPLAY_ORDER.indexOf(left.category as (typeof PART_DISPLAY_ORDER)[number]);
      const rightIndex = PART_DISPLAY_ORDER.indexOf(right.category as (typeof PART_DISPLAY_ORDER)[number]);
      const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
      const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;
      return normalizedLeft - normalizedRight;
    });
  };

  const IGPU_USAGES = new Set(["business", "standard"]);

  const normalizedParts: NormalizedResultPart[] = isSavedConfiguration(config)
    ? (() => {
      const parts: NormalizedResultPart[] = [
            ["cpu", config.cpu_data],
            ["cpu_cooler", config.cpu_cooler_data],
            ["gpu", config.gpu_data],
            ["motherboard", config.motherboard_data],
            ["memory", config.memory_data],
            ["storage", config.storage_data],
            ["storage2", config.storage2_data],
            ["storage3", config.storage3_data],
            ["os", config.os_data],
            ["psu", config.psu_data],
            ["case", config.case_data],
          ]
            .filter((entry): entry is [string, SavedPartResponse] => entry[1] !== null)
            .map(([category, part]) => ({
              category,
              name: part.name,
              price: part.price,
              url: part.url,
              specs: part.specs,
            }));
        // iGPU構成の場合: gpu_data=null なので保存済み構成でも内蔵GPU行を復元
        if (IGPU_USAGES.has(config.usage) && config.gpu_data === null) {
          const cpuIndexForIgpu = parts.findIndex((p) => p.category === "cpu");
          parts.splice(cpuIndexForIgpu + 1, 0, {
            category: "gpu",
            name: "内蔵GPU（統合グラフィックス）",
            price: 0,
            url: "",
            specs: null,
          });
        }
        return sortPartsByDisplayOrder(parts);
      })()
    : sortPartsByDisplayOrder(
        config.parts.map((part) => ({
          ...part,
          specs: part.specs ?? null,
        }))
      );

  const displayParts = useMemo(() => {
    const parts = [...normalizedParts];
    for (const category of ["storage2", "storage3"]) {
      if (!parts.some((part) => part.category === category)) {
        parts.push({
          category,
          name: "未選択",
          price: 0,
          url: "",
          specs: null,
          isPlaceholder: true,
        });
      }
    }
    return sortPartsByDisplayOrder(parts);
  }, [normalizedParts]);

  const inferStorageCapacityGb = (part: { name: string; specs?: Record<string, unknown> | null }) => {
    const capacity = Number(part.specs?.capacity_gb ?? 0);
    if (capacity > 0) {
      return capacity;
    }
    // TB単位を優先、モデル番号埋め込み ("F20GB" 等) を除外
    const tbMatch = part.name.match(/(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*TB/i);
    if (tbMatch) {
      return Math.round(Number(tbMatch[1]) * 1024);
    }
    const gbMatch = part.name.match(/(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*GB/i);
    if (gbMatch) {
      return Math.round(Number(gbMatch[1]));
    }
    return 0;
  };

  const inferStorageInterface = (part: { name: string; specs?: Record<string, unknown> | null }) => {
    const interfaceValue = String(part.specs?.interface ?? "").toLowerCase();
    if (interfaceValue === "nvme") {
      return "nvme";
    }
    if (interfaceValue === "sata") {
      return "sata";
    }
    const name = part.name.toLowerCase();
    if (name.includes("nvme")) {
      return "nvme";
    }
    if (name.includes("sata")) {
      return "sata";
    }
    // WD NVMe モデル番号 (SN500/580/700/750/850)
    if (/\bsn[5-9]\d{2}\b/.test(name)) {
      return "nvme";
    }
    // WD SATA SSD モデル番号 (SA500)
    if (/\bsa\d{3}\b/.test(name)) {
      return "sata";
    }
    // Samsung NVMe (970/980/990 EVO・PRO)
    if (/\b(970|980|990)\s*(evo|pro)\b/i.test(name)) {
      return "nvme";
    }
    // 名前に M.2 が含まれる → NVMe
    if (name.includes("m.2")) {
      return "nvme";
    }
    return "other";
  };

  const inferStorageMediaTypeFromPart = (part: { name: string; specs?: Record<string, unknown> | null }) => {
    const text = part.name.toLowerCase();
    const formFactor = String(part.specs?.form_factor ?? "").toLowerCase();
    const interfaceValue = inferStorageInterface(part);

    if (interfaceValue === "nvme") {
      return "ssd" as const;
    }
    if (text.includes("ssd") || formFactor.includes("m.2") || formFactor.includes("2.5inch") || text.includes("m.2")) {
      return "ssd" as const;
    }
    // WD SSD モデル番号
    if (/\b(sa500|sn500|sn580|sn700|sn750|sn850)\b/.test(text)) {
      return "ssd" as const;
    }
    if (/(5400|7200|10000|15000)\s*rpm/i.test(part.name)) {
      return "hdd" as const;
    }
    // HDD キーワード ─ "wd red" 単体は SSD モデルと被るため除外
    const hddKeywords = [
      "barracuda",
      "ironwolf",
      "wd blue wd",
      "wd green wd",
      "wd red wd",
      "wd purple wd",
      "mq04",
      "dt02",
      "n300",
      "mg10",
      "mg11",
      "hat3300",
      "hdd",
    ];
    if (hddKeywords.some((keyword) => text.includes(keyword))) {
      return "hdd" as const;
    }
    if (interfaceValue === "sata" && formFactor.includes("3.5")) {
      return "hdd" as const;
    }
    if (interfaceValue === "sata" && (formFactor.includes("2.5") || formFactor.includes("m.2"))) {
      return "ssd" as const;
    }
    return "other" as const;
  };

  const formatCapacityLabel = (capacityGb: number) => {
    if (capacityGb <= 0) {
      return null;
    }
    if (capacityGb >= 1024) {
      const tb = capacityGb / 1024;
      return Number.isInteger(tb) ? `${tb}TB` : `${tb.toFixed(1)}TB`;
    }
    return `${capacityGb}GB`;
  };

  const getStoragePartMeta = (part: NormalizedResultPart) => {
    const mediaType = inferStorageMediaTypeFromPart(part);
    const interfaceType = inferStorageInterface(part);
    const capacityLabel = formatCapacityLabel(inferStorageCapacityGb(part));
    const formFactor = String(part.specs?.form_factor ?? "").trim();

    return {
      mediaLabel: STORAGE_MEDIA_LABELS[mediaType],
      interfaceLabel: STORAGE_INTERFACE_LABELS[interfaceType],
      capacityLabel,
      formFactor: formFactor || null,
    };
  };

  const inferMemoryCapacityGb = (part: NormalizedResultPart) => {
    const specCapacity = Number(part.specs?.capacity_gb ?? 0);
    if (specCapacity > 0) {
      return specCapacity;
    }

    const text = part.name;
    const multiMatch = text.match(/(\d+)\s*GB\s*[x×*]\s*(\d+)/i) || text.match(/(\d+)\s*GB\s*(\d+)\s*枚組/i);
    if (multiMatch) {
      return Number(multiMatch[1]) * Number(multiMatch[2]);
    }

    const singleMatch = text.match(/(\d+)\s*GB/i);
    if (singleMatch) {
      return Number(singleMatch[1]);
    }
    return 0;
  };

  const inferMemoryModuleCount = (part: NormalizedResultPart) => {
    const specModule = Number(part.specs?.module_count ?? 0);
    if (specModule > 0) {
      return specModule;
    }
    const text = part.name;
    const multiMatch = text.match(/[x×*]\s*(\d+)/i) || text.match(/(\d+)\s*枚組/i);
    if (multiMatch) {
      return Number(multiMatch[1]);
    }
    return 1;
  };

  const inferCpuPower = (part: NormalizedResultPart | null) => {
    if (!part) {
      return 0;
    }
    const specTdp = Number(part.specs?.tdp_w ?? 0);
    if (specTdp > 0) {
      return specTdp;
    }
    const text = part.name.toLowerCase();
    for (const watts of [170, 125, 105, 95, 65, 35]) {
      if (text.includes(`${watts}w`)) {
        return watts;
      }
    }
    return 95;
  };

  const inferGpuPower = (part: NormalizedResultPart | null) => {
    if (!part) {
      return 0;
    }
    const specTdp = Number(part.specs?.tdp_w ?? 0);
    if (specTdp > 0) {
      return specTdp;
    }
    for (const [pattern, watts] of GPU_POWER_RULES) {
      if (pattern.test(part.name)) {
        return watts;
      }
    }
    return 180;
  };

  const estimatedPower = useMemo(() => {
    if (!isSavedConfiguration(config)) {
      return config.estimated_power_w;
    }

    const cpu = normalizedParts.find((part) => part.category === "cpu") ?? null;
    const gpu = normalizedParts.find((part) => part.category === "gpu" && part.price > 0) ?? null;
    const cpuCooler = normalizedParts.find((part) => part.category === "cpu_cooler") ?? null;
    const motherboard = normalizedParts.find((part) => part.category === "motherboard") ?? null;
    const memory = normalizedParts.find((part) => part.category === "memory") ?? null;
    const storageParts = normalizedParts.filter((part) => ["storage", "storage2", "storage3"].includes(part.category));
    const hasCase = normalizedParts.some((part) => part.category === "case");

    const cpuPower = inferCpuPower(cpu);
    const gpuPower = inferGpuPower(gpu);
    const motherboardPower = motherboard ? 45 : 0;
    const memoryPower = memory ? 10 : 0;
    const storagePower = storageParts.reduce((sum, part) => sum + (inferStorageMediaTypeFromPart(part) === "hdd" ? 12 : 6), 0);
    const coolerText = `${cpuCooler?.name ?? ""}`.toLowerCase();
    const coolerPower = cpuCooler ? ((coolerText.includes("水冷") || coolerText.includes("aio") || coolerText.includes("360") || coolerText.includes("280") || coolerText.includes("240")) ? 20 : 8) : 0;
    const casePower = hasCase ? 10 : 0;

    return cpuPower + gpuPower + motherboardPower + memoryPower + storagePower + coolerPower + casePower;
  }, [config, normalizedParts]);

  const configurationId = isSavedConfiguration(config)
    ? config.id
    : config.configuration_id;

  const USAGE_LABELS: Record<string, string> = {
    gaming: "ゲーミングPC",
    creator: "クリエイターPC",
    business: "ビジネスPC",
    standard: "スタンダードPC",
    video_editing: "動画編集PC",
    general: "汎用PC",
  };
  const usageLabel = USAGE_LABELS[config.usage] ?? config.usage;
  const isAutoAdjusted = !isSavedConfiguration(config) && Boolean(config.budget_auto_adjusted);
  const marketBudgetAdjusted = !isSavedConfiguration(config) && Boolean(config.market_budget_adjusted);
  const marketBudgetNote = !isSavedConfiguration(config) ? (config.market_budget_note ?? "") : "";
  const requestedBudget = !isSavedConfiguration(config)
    ? (config.requested_budget ?? config.budget)
    : config.budget;
  const benchmarkFloorScore = !isSavedConfiguration(config)
    ? Number(config.minimum_gaming_gpu_perf_score ?? 0)
    : 0;
  const selectedGpuBenchmarkScore = !isSavedConfiguration(config)
    ? Number(config.selected_gpu_perf_score ?? 0)
    : 0;
  const selectedGpuGamingTierLabel = !isSavedConfiguration(config)
    ? config.selected_gpu_gaming_tier_label ?? ""
    : "";

  const currentGpuPart = normalizedParts.find((part) => part.category === "gpu" && part.price > 0)
    ?? normalizedParts.find((part) => part.category === "gpu")
    ?? null;
  const currentGpuModelKey = currentGpuPart ? extractGpuModelKey(currentGpuPart.name) : null;
  const currentGpuModelKeyNormalized = currentGpuModelKey ? normalizeGpuModelKey(currentGpuModelKey) : null;
  const currentCpuPart = normalizedParts.find((part) => part.category === "cpu") ?? null;
  const currentCpuModelKey = currentCpuPart ? extractCpuModelKey(currentCpuPart.name) : null;
  const isGamingUsage = config.usage === "gaming";
  const gamingCpuRankingMode = isGamingUsage && !isSavedConfiguration(config) && config.build_priority === "cost" ? "cost" : "spec";

  const [gpuComparison, setGpuComparison] = useState<GpuPerformanceCompareResponse | null>(null);
  const [gpuSnapshot, setGpuSnapshot] = useState<GpuPerformanceLatestResponse["snapshot"] | null>(null);
  const [gpuComparisonLoading, setGpuComparisonLoading] = useState(false);
  const [gpuComparisonError, setGpuComparisonError] = useState<string | null>(null);
  const [cpuComparison, setCpuComparison] = useState<CpuSelectionMaterialCompareResponse | null>(null);
  const [cpuMaterialMeta, setCpuMaterialMeta] = useState<Pick<CpuSelectionMaterialLatestResponse, "entry_count" | "excluded_count" | "exclude_intel_13_14"> | null>(null);
  const [cpuComparisonLoading, setCpuComparisonLoading] = useState(false);
  const [cpuComparisonError, setCpuComparisonError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (!currentGpuModelKey) {
      setGpuComparison(null);
      setGpuSnapshot(null);
      setGpuComparisonError(null);
      setGpuComparisonLoading(false);
      return () => {
        cancelled = true;
      };
    }

    const loadGpuComparison = async () => {
      setGpuComparisonLoading(true);
      setGpuComparisonError(null);

      try {
        const latest = await getLatestGpuPerformance();
        const currentEntry = latest.entries.results.find(
          (entry) => normalizeGpuModelKey(entry.model_key) === currentGpuModelKeyNormalized,
        );

        if (!currentEntry) {
          if (!cancelled) {
            setGpuComparison(null);
            setGpuSnapshot(latest.snapshot);
            setGpuComparisonError(`GPU性能データに ${currentGpuModelKey} が見つかりませんでした。`);
          }
          return;
        }

        const nearbyModelKeys = latest.entries.results
          .filter((entry) => Math.abs(entry.rank_global - currentEntry.rank_global) <= 2)
          .sort((left, right) => left.rank_global - right.rank_global)
          .map((entry) => entry.model_key);

        const compare = await compareGpuPerformance(nearbyModelKeys.length > 0 ? nearbyModelKeys : [currentGpuModelKey]);

        if (!cancelled) {
          setGpuSnapshot(latest.snapshot);
          setGpuComparison(compare);
          setGpuComparisonError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setGpuComparison(null);
          setGpuSnapshot(null);
          setGpuComparisonError(error instanceof Error ? error.message : "GPU性能比較の取得に失敗しました。");
        }
      } finally {
        if (!cancelled) {
          setGpuComparisonLoading(false);
        }
      }
    };

    void loadGpuComparison();

    return () => {
      cancelled = true;
    };
  }, [currentGpuModelKey, currentGpuModelKeyNormalized]);

  useEffect(() => {
    let cancelled = false;

    if (!currentCpuModelKey && !isGamingUsage) {
      setCpuComparison(null);
      setCpuMaterialMeta(null);
      setCpuComparisonError(null);
      setCpuComparisonLoading(false);
      return () => {
        cancelled = true;
      };
    }

    const normalizeModel = (value: string) => value.replace(/\s+/g, " ").trim().toUpperCase();

    const loadCpuComparison = async () => {
      setCpuComparisonLoading(true);
      setCpuComparisonError(null);

      try {
        const latest = await getLatestCpuSelectionMaterial();

        if (isGamingUsage) {
          const gamingRanking = sortGamingCpuEntries(latest.entries.results, gamingCpuRankingMode);

          if (!cancelled) {
            setCpuMaterialMeta({
              entry_count: latest.entry_count,
              excluded_count: latest.excluded_count,
              exclude_intel_13_14: latest.exclude_intel_13_14,
            });

            if (gamingRanking.length === 0) {
              setCpuComparison(null);
              setCpuComparisonError("ゲーミングCPU順位のAMD候補が見つかりませんでした。");
              return;
            }

            setCpuComparison({
              requested_models: gamingRanking.map((entry) => entry.model_name),
              missing_models: [],
              results: gamingRanking,
            });
            setCpuComparisonError(null);
          }
          return;
        }

        if (!currentCpuModelKey) {
          return;
        }

        const sorted = latest.entries.results
          .slice()
          .sort((left, right) => right.perf_score - left.perf_score);

        const currentIndex = sorted.findIndex((entry) => {
          const model = normalizeModel(entry.model_name);
          return model === currentCpuModelKey || model.includes(currentCpuModelKey) || currentCpuModelKey.includes(model);
        });

        if (currentIndex < 0) {
          if (!cancelled) {
            setCpuComparison(null);
            setCpuMaterialMeta({
              entry_count: latest.entry_count,
              excluded_count: latest.excluded_count,
              exclude_intel_13_14: latest.exclude_intel_13_14,
            });
            setCpuComparisonError(`CPU選考資料に ${currentCpuModelKey} が見つかりませんでした。`);
          }
          return;
        }

        const start = Math.max(0, currentIndex - 2);
        const end = Math.min(sorted.length, currentIndex + 3);
        const nearbyModels = sorted.slice(start, end).map((entry) => entry.model_name);

        const compare = await compareCpuSelectionMaterial(nearbyModels.length > 0 ? nearbyModels : [currentCpuModelKey]);

        if (!cancelled) {
          setCpuMaterialMeta({
            entry_count: latest.entry_count,
            excluded_count: latest.excluded_count,
            exclude_intel_13_14: latest.exclude_intel_13_14,
          });
          setCpuComparison(compare);
          setCpuComparisonError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setCpuComparison(null);
          setCpuMaterialMeta(null);
          setCpuComparisonError(error instanceof Error ? error.message : "CPU選考資料の取得に失敗しました。");
        }
      } finally {
        if (!cancelled) {
          setCpuComparisonLoading(false);
        }
      }
    };

    void loadCpuComparison();

    return () => {
      cancelled = true;
    };
  }, [currentCpuModelKey, gamingCpuRankingMode, isGamingUsage]);

  const selectionSummary = {
    coolerType:
      !isSavedConfiguration(config) && config.cooler_type
        ? (config.cooler_type === "air" ? "空冷" : config.cooler_type === "liquid" ? "水冷" : "指定なし")
        : null,
    radiatorSize:
      !isSavedConfiguration(config) && config.radiator_size
        ? (config.radiator_size === "any" ? "指定なし" : `${config.radiator_size}mm`)
        : null,
    coolingProfile:
      !isSavedConfiguration(config) && config.cooling_profile
        ? (
            config.cooling_profile === "silent"
              ? "静音重視"
              : config.cooling_profile === "performance"
                ? "冷却重視"
                : "バランス"
          )
        : null,
    caseSize:
      !isSavedConfiguration(config) && config.case_size
        ? (
            config.case_size === "mini"
              ? "Mini"
              : config.case_size === "mid"
                ? "Mid"
                : config.case_size === "full"
                  ? "Full"
                  : "指定なし"
          )
        : null,
    caseFanPolicy:
      !isSavedConfiguration(config) && config.case_fan_policy
        ? (
            config.case_fan_policy === "silent"
              ? "静音重視"
              : config.case_fan_policy === "airflow"
                ? "冷却重視"
                : "自動"
          )
        : null,
    cpuVendor:
      !isSavedConfiguration(config) && config.cpu_vendor
        ? (
            config.cpu_vendor === "intel"
              ? "Intel"
              : config.cpu_vendor === "amd"
                ? "AMD"
                : "指定なし"
          )
        : null,
    buildPriority:
      !isSavedConfiguration(config) && config.build_priority
        ? (
            config.build_priority === "cost"
              ? "コスト重視"
              : config.build_priority === "spec"
                ? "スペック重視"
                : "バランス"
          )
        : null,
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="sticky top-4 z-30 mb-6 flex justify-start">
          <button
            onClick={onBack}
            className="rounded-lg bg-slate-600 px-4 py-2 font-semibold text-white shadow hover:bg-slate-700 transition"
          >
            ← 戻る
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8 pb-28">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h2 className="text-3xl font-bold text-gray-800">
              構成提案が完成しました！
            </h2>
            {isAutoAdjusted && (
              <span className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                自動調整しました
              </span>
            )}
          </div>
          <p className="text-gray-600 mb-6">
            用途: 
            <span className="font-semibold">
              {usageLabel}
            </span>
          </p>

          {isAutoAdjusted && (
            <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <p className="font-semibold">
                {marketBudgetAdjusted ? "相場変動により補正しました。" : "相場変動により最低価格を下げました。"}
              </p>
              {marketBudgetAdjusted && marketBudgetNote && (
                <p className="mt-1 text-xs text-amber-800">{marketBudgetNote}</p>
              )}
              {!isSavedConfiguration(config) && typeof config.recommended_budget_min_for_x3d === "number" && (
                <p className="mt-1 text-xs text-amber-800">X3D必須構成の推奨下限: {formatCurrency(config.recommended_budget_min_for_x3d)}</p>
              )}
            </div>
          )}

          {!isSavedConfiguration(config) && config.message && (
            <div className="mb-6 rounded-lg border border-sky-300 bg-sky-50 px-4 py-3 text-sm text-sky-900">
              <p className="font-semibold">選定ポリシーの自動調整</p>
              <p className="mt-1 text-xs text-sky-800">{config.message}</p>
            </div>
          )}

          {!isSavedConfiguration(config) && config.usage === "gaming" && benchmarkFloorScore > 0 && (
            <div className="mb-6 rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              <p className="font-semibold">GPU性能目安: ベンチマークスコア {benchmarkFloorScore.toLocaleString("ja-JP")} 以上</p>
              <p className="mt-1 text-xs text-emerald-800">
                選択GPUスコア: {selectedGpuBenchmarkScore.toLocaleString("ja-JP")}
                {selectedGpuBenchmarkScore >= benchmarkFloorScore ? " (基準達成)" : " (候補不足のため未達)"}
              </p>
              {selectedGpuGamingTierLabel && (
                <p className="mt-1 text-xs text-emerald-800">GPU帯: {selectedGpuGamingTierLabel}</p>
              )}
            </div>
          )}

          {configurationId && (
            <p className="text-sm text-gray-500 mb-6">
              {isSavedConfiguration(config) ? "保存済み構成ID" : "新規生成ID"}: {configurationId}
            </p>
          )}

          {isSavedConfiguration(config) && (
            <p className="text-sm text-gray-500 -mt-4 mb-6">
              保存日時: {new Date(config.created_at).toLocaleString("ja-JP")}
            </p>
          )}

          <div className="bg-blue-50 border-2 border-blue-300 rounded-lg p-6 mb-8">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-gray-600">指定予算</p>
                <p className="text-2xl font-bold text-gray-800">
                  {formatCurrency(requestedBudget)}
                </p>
              </div>
              <div className="text-3xl text-gray-400">→</div>
              <div>
                <p className="text-gray-600">構成金額</p>
                <p className="text-2xl font-bold text-green-600">
                  {formatCurrency(config.total_price)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-gray-600">推定消費電力</p>
                <p className="text-2xl font-bold text-gray-800">
                  {estimatedPower}W
                </p>
              </div>
            </div>
          </div>

          {selectionSummary.coolerType && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-8">
              <p className="text-sm font-semibold text-slate-700 mb-2">選択条件</p>
              <div className="grid grid-cols-2 gap-2 text-sm text-slate-600">
                <div>クーラー方式: <span className="font-semibold text-slate-800">{selectionSummary.coolerType}</span></div>
                <div>ラジエーター: <span className="font-semibold text-slate-800">{selectionSummary.radiatorSize ?? "指定なし"}</span></div>
                <div>クーラー方針: <span className="font-semibold text-slate-800">{selectionSummary.coolingProfile ?? "指定なし"}</span></div>
                <div>ケースサイズ: <span className="font-semibold text-slate-800">{selectionSummary.caseSize ?? "指定なし"}</span></div>
                <div>ケースファン方針: <span className="font-semibold text-slate-800">{selectionSummary.caseFanPolicy ?? "指定なし"}</span></div>
                <div>CPUメーカー: <span className="font-semibold text-slate-800">{selectionSummary.cpuVendor ?? "指定なし"}</span></div>
                <div>構成方針: <span className="font-semibold text-slate-800">{selectionSummary.buildPriority ?? "指定なし"}</span></div>
              </div>
            </div>
          )}

          <div className="mb-8 rounded-lg border border-indigo-200 bg-indigo-50 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-indigo-700">GPU性能比較</p>
                <p className="text-xs text-indigo-600">
                  {currentGpuPart ? `選択中GPU: ${currentGpuPart.name}` : "GPU比較対象は見つかりませんでした。"}
                </p>
              </div>
              {gpuSnapshot && (
                <p className="text-xs text-indigo-600">
                  Snapshot #{gpuSnapshot.id} / {gpuSnapshot.source_name}
                </p>
              )}
            </div>

            {gpuComparisonLoading ? (
              <p className="text-sm text-indigo-700">GPU性能データを読み込み中です…</p>
            ) : gpuComparisonError ? (
              <p className="text-sm font-medium text-rose-700">{gpuComparisonError}</p>
            ) : gpuComparison ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] border-separate border-spacing-0 text-left text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wide text-indigo-600">
                      <th className="border-b border-indigo-200 pb-2 pr-4">順位</th>
                      <th className="border-b border-indigo-200 pb-2 pr-4">モデル</th>
                      <th className="border-b border-indigo-200 pb-2 pr-4">VRAM</th>
                      <th className="border-b border-indigo-200 pb-2 pr-4">性能スコア</th>
                      <th className="border-b border-indigo-200 pb-2">詳細</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gpuComparison.results
                      .slice()
                      .sort((left, right) => left.rank_global - right.rank_global)
                      .slice(0, RANKING_DISPLAY_LIMIT)
                      .map((entry) => {
                        const isCurrent = entry.model_key === currentGpuModelKey;
                        return (
                          <tr key={entry.model_key} className={isCurrent ? "bg-indigo-100/80" : "bg-white/70"}>
                            <td className="border-b border-indigo-100 py-2 pr-4 font-semibold text-slate-700">
                              #{entry.rank_global}
                            </td>
                            <td className="border-b border-indigo-100 py-2 pr-4 font-medium text-slate-800">
                              {formatGpuModelLabel(entry)}
                              {isCurrent && (
                                <span className="ml-2 rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                                  現在の構成
                                </span>
                              )}
                            </td>
                            <td className="border-b border-indigo-100 py-2 pr-4 text-slate-700">
                              {entry.vram_gb ? `${entry.vram_gb}GB` : "-"}
                            </td>
                            <td className="border-b border-indigo-100 py-2 pr-4 text-slate-700">
                              {entry.perf_score.toLocaleString("ja-JP")}
                            </td>
                            <td className="border-b border-indigo-100 py-2 text-slate-700">
                              <a
                                href={entry.detail_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-medium text-indigo-700 hover:text-indigo-900"
                              >
                                表示
                              </a>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-indigo-700">GPU比較データはまだありません。</p>
            )}

            {gpuComparison?.missing_models?.length ? (
              <p className="mt-3 text-xs text-slate-600">
                見つからなかったモデル: {gpuComparison.missing_models.join(", ")}
              </p>
            ) : null}
          </div>

          <div className="mb-8 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-emerald-700">
                  {isGamingUsage
                    ? gamingCpuRankingMode === "cost"
                      ? "ゲーミングCPU選択テーブル（AMD・コスパ重視）"
                      : "ゲーミングCPU順位（AMD・スペック順）"
                    : "CPU選考資料（AMD/Intel）"}
                </p>
                <p className="text-xs text-emerald-600">
                  {currentCpuPart
                    ? `選択中CPU: ${currentCpuPart.name}`
                    : isGamingUsage
                      ? "AMDのみで順位付けしています。"
                      : "CPU比較対象は見つかりませんでした。"}
                </p>
              </div>
              {cpuMaterialMeta && (
                <p className="text-xs text-emerald-600">
                  {isGamingUsage ? "元データ" : "件数"}: {cpuMaterialMeta.entry_count} / 除外: {cpuMaterialMeta.excluded_count}
                </p>
              )}
            </div>

            {isGamingUsage ? (
              <p className="mb-3 text-xs text-emerald-600">
                {gamingCpuRankingMode === "cost"
                  ? "コスパ重視では性能/価格で選択候補を並べています。"
                  : "スペック重視ではX3Dを優先して性能順に並べています。"}
              </p>
            ) : null}

            {cpuComparisonLoading ? (
              <p className="text-sm text-emerald-700">CPU選考資料を読み込み中です…</p>
            ) : cpuComparisonError ? (
              <p className="text-sm font-medium text-rose-700">{cpuComparisonError}</p>
            ) : cpuComparison ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[680px] border-separate border-spacing-0 text-left text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wide text-emerald-700">
                      <th className="border-b border-emerald-200 pb-2 pr-4">順位</th>
                      <th className="border-b border-emerald-200 pb-2 pr-4">モデル</th>
                      <th className="border-b border-emerald-200 pb-2 pr-4">Vendor</th>
                      <th className="border-b border-emerald-200 pb-2 pr-4">{gamingCpuRankingMode === "cost" ? "コスパ" : "性能目安"}</th>
                      <th className="border-b border-emerald-200 pb-2">詳細</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cpuComparison.results.slice(0, RANKING_DISPLAY_LIMIT).map((entry, index) => {
                        const isCurrent = currentCpuModelKey
                          ? entry.model_name.replace(/\s+/g, " ").trim().toUpperCase().includes(currentCpuModelKey)
                          : false;
                        return (
                          <tr key={`${entry.vendor}:${entry.model_name}`} className={isCurrent ? "bg-emerald-100/80" : "bg-white/70"}>
                            <td className="border-b border-emerald-100 py-2 pr-4 font-semibold text-slate-700">{index + 1}</td>
                            <td className="border-b border-emerald-100 py-2 pr-4 font-medium text-slate-800">
                              {formatCpuModelLabel(entry)}
                              {isCurrent && (
                                <span className="ml-2 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                                  現在の構成
                                </span>
                              )}
                            </td>
                            <td className="border-b border-emerald-100 py-2 pr-4 text-slate-700">{entry.vendor.toUpperCase()}</td>
                            <td className="border-b border-emerald-100 py-2 pr-4 text-slate-700">
                              {gamingCpuRankingMode === "cost"
                                ? (entry.value_score ?? 0).toFixed(6)
                                : entry.perf_score.toLocaleString("ja-JP")}
                            </td>
                            <td className="border-b border-emerald-100 py-2 text-slate-700">
                              <a href={entry.source_url} target="_blank" rel="noopener noreferrer" className="font-medium text-emerald-700 hover:text-emerald-900">
                                表示
                              </a>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-emerald-700">CPU選考資料データはまだありません。</p>
            )}

            {cpuMaterialMeta?.exclude_intel_13_14 ? (
              <p className="mt-3 text-xs text-slate-600">Intel 13世代/14世代は除外して集計しています。</p>
            ) : null}
          </div>

          <div className="space-y-4">
            <h3 className="text-2xl font-bold text-gray-800">PC構成</h3>
            {displayParts.map((part, index) => {
              const isIgpu = part.category === "gpu" && part.price === 0 && part.name.includes("内蔵");
              const isUnselectedOptionalStorage = (part.category === "storage2" || part.category === "storage3") && Boolean(part.isPlaceholder);
              const isCaseWithoutIncludedFans = part.category === "case" && Number(part.specs?.included_fan_count ?? -1) === 0;
              const categoryLabel = PART_CATEGORY_LABELS[part.category] ?? part.category;
              const psuCapacityWatts = part.category === "psu" ? parsePsuCapacityWatts(part.name) : null;
              const memoryCapacityGb = part.category === "memory" ? inferMemoryCapacityGb(part) : 0;
              const memoryModuleCount = part.category === "memory" ? inferMemoryModuleCount(part) : 0;
              return (
                <div
                  key={index}
                  className={`border rounded-lg p-4 transition ${
                    isIgpu
                      ? "border-green-200 bg-green-50"
                      : "border-gray-200 hover:shadow-md"
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <p className="text-sm font-semibold text-gray-500">
                        {categoryLabel}
                      </p>
                      <p className="text-lg font-bold text-gray-800">
                        {part.name?.trim() ? part.name : "未選択"}
                      </p>
                    </div>
                    {isIgpu ? (
                      <span className="inline-block bg-green-100 text-green-700 text-xs font-semibold px-2 py-1 rounded">
                        内蔵GPU
                      </span>
                    ) : isUnselectedOptionalStorage ? (
                      <span className="inline-block bg-slate-100 text-slate-600 text-xs font-semibold px-2 py-1 rounded">
                        任意
                      </span>
                    ) : (
                      <p className="text-lg font-bold text-indigo-600">
                        {formatCurrency(part.price)}
                      </p>
                    )}
                  </div>

                  {part.category === "memory" && memoryCapacityGb > 0 && (
                    <p className="mb-2 text-xs text-slate-600">
                      合計容量: <span className="font-semibold text-slate-800">{memoryCapacityGb}GB</span>
                      {memoryModuleCount > 1 && (
                        <span className="ml-2">({Math.max(1, Math.floor(memoryCapacityGb / memoryModuleCount))}GB x {memoryModuleCount})</span>
                      )}
                    </p>
                  )}

                  {isCaseWithoutIncludedFans && (
                    <div className="mb-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      このケースは付属ファンなしのため、別途ケースファンの追加を推奨します。
                    </div>
                  )}
                  {!isIgpu && !isUnselectedOptionalStorage && part.url && (
                    <a
                      href={part.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:text-blue-700 text-sm font-medium inline-flex items-center"
                    >
                      購入ページを見る →
                    </a>
                  )}
                  {part.category === "psu" && psuCapacityWatts !== null && psuCapacityWatts > 1000 && (
                    <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      1000Wを超える電源容量のため、コンセント側の工事が必要になる可能性があります。
                    </p>
                  )}
                  {isIgpu && (
                    <p className="text-xs text-green-600">
                      CPU内蔵グラフィックスを使用します。別途GPUは不要です。
                    </p>
                  )}
                </div>
              );
            })}
          </div>

        </div>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-4xl p-3 md:p-4">
          <button
            onClick={onBack}
            className="w-full rounded-lg bg-indigo-600 px-4 py-3 font-bold text-white transition hover:bg-indigo-700"
          >
            別の構成を生成
          </button>
        </div>
      </div>
    </div>
  );
}
