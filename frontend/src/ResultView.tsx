import { useEffect, useMemo, useState } from "react";
import {
  GenerateConfigResponse,
  getStorageInventory,
  SavedConfigurationResponse,
  SavedPartResponse,
  StorageInventoryItem,
  StorageInventoryResponse,
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

export function ResultView({ config, onBack }: ResultProps) {
  const [storageInventory, setStorageInventory] = useState<StorageInventoryResponse | null>(null);

  useEffect(() => {
    const loadStorageInventory = async () => {
      try {
        const inventory = await getStorageInventory();
        setStorageInventory(inventory);
      } catch {
        return;
      }
    };

    loadStorageInventory();
  }, []);

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

  const selectedStoragePart = normalizedParts.find((part) => part.category === "storage") ?? null;

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

  const inferStorageMediaTypeFromInventoryItem = (item: StorageInventoryItem) => {
    const text = item.name.toLowerCase();
    const formFactor = (item.form_factor ?? "").toLowerCase();

    if (item.interface === "nvme") {
      return "ssd" as const;
    }
    if (text.includes("ssd") || formFactor.includes("m.2") || formFactor.includes("2.5inch") || text.includes("m.2")) {
      return "ssd" as const;
    }
    // WD SSD モデル番号
    if (/\b(sa500|sn500|sn580|sn700|sn750|sn850)\b/.test(text)) {
      return "ssd" as const;
    }
    if (/(5400|7200|10000|15000)\s*rpm/i.test(item.name)) {
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
    if (item.interface === "sata" && formFactor.includes("3.5")) {
      return "hdd" as const;
    }
    if (item.interface === "sata" && (formFactor.includes("2.5") || formFactor.includes("m.2"))) {
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

  const storageAlternatives = useMemo(() => {
    if (!storageInventory || !selectedStoragePart) {
      return [] as StorageInventoryItem[];
    }

    const selectedCapacityGb = inferStorageCapacityGb(selectedStoragePart);
    const selectedInterface = inferStorageInterface(selectedStoragePart);
    const selectedMediaType = inferStorageMediaTypeFromPart(selectedStoragePart);

    const allItems = storageInventory.capacity_summary.flatMap((group) => group.items);
    return allItems
      .filter((item) => item.name !== selectedStoragePart.name)
      .sort((left, right) => {
        const leftMedia = inferStorageMediaTypeFromInventoryItem(left);
        const rightMedia = inferStorageMediaTypeFromInventoryItem(right);
        const leftMediaMatch = leftMedia === selectedMediaType ? 1 : 0;
        const rightMediaMatch = rightMedia === selectedMediaType ? 1 : 0;
        const leftCapacityDiff = Math.abs(left.capacity_gb - selectedCapacityGb);
        const rightCapacityDiff = Math.abs(right.capacity_gb - selectedCapacityGb);
        const leftInterfaceMatch = left.interface === selectedInterface ? 1 : 0;
        const rightInterfaceMatch = right.interface === selectedInterface ? 1 : 0;

        if (rightMediaMatch !== leftMediaMatch) {
          return rightMediaMatch - leftMediaMatch;
        }
        if (rightInterfaceMatch !== leftInterfaceMatch) {
          return rightInterfaceMatch - leftInterfaceMatch;
        }
        if (leftCapacityDiff !== rightCapacityDiff) {
          return leftCapacityDiff - rightCapacityDiff;
        }
        return left.price - right.price;
      })
      .slice(0, 4);
  }, [selectedStoragePart, storageInventory]);

  const largeCapacityHddCandidates = useMemo(() => {
    if (!storageInventory || !selectedStoragePart) {
      return [] as StorageInventoryItem[];
    }

    const allItems = storageInventory.capacity_summary.flatMap((group) => group.items);
    return allItems
      .filter((item) => item.name !== selectedStoragePart.name)
      .filter((item) => inferStorageMediaTypeFromInventoryItem(item) === "hdd")
      .filter((item) => item.interface === "sata")
      .filter((item) => item.capacity_gb >= 1024 && item.capacity_gb <= 8192)
      .sort((left, right) => {
        if (left.capacity_gb !== right.capacity_gb) {
          return left.capacity_gb - right.capacity_gb;
        }
        return left.price - right.price;
      })
      .slice(0, 3);
  }, [selectedStoragePart, storageInventory]);

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
        <button
          onClick={onBack}
          className="mb-6 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
        >
          ← 戻る
        </button>

        <div className="bg-white rounded-lg shadow-lg p-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-2">
            構成提案が完成しました！
          </h2>
          <p className="text-gray-600 mb-6">
            用途: 
            <span className="font-semibold">
              {usageLabel}
            </span>
          </p>

          {configurationId && (
            <p className="text-sm text-gray-500 mb-6">
              保存済み構成ID: {configurationId}
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
                  {formatCurrency(config.budget)}
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

          <div className="space-y-4">
            <h3 className="text-2xl font-bold text-gray-800">PC構成</h3>
            {displayParts.map((part, index) => {
              const isIgpu = part.category === "gpu" && part.price === 0 && part.name.includes("内蔵");
              const isUnselectedOptionalStorage = (part.category === "storage2" || part.category === "storage3") && Boolean(part.isPlaceholder);
              const isCaseWithoutIncludedFans = part.category === "case" && Number(part.specs?.included_fan_count ?? -1) === 0;
              const categoryLabel = PART_CATEGORY_LABELS[part.category] ?? part.category;
              const psuCapacityWatts = part.category === "psu" ? parsePsuCapacityWatts(part.name) : null;
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
                  {part.category === "storage" && storageAlternatives.length > 0 && (
                    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-700">近い条件のストレージ候補（SSD優先）</p>
                      <div className="mt-2 grid gap-2">
                        {storageAlternatives.map((item) => (
                          <a
                            key={item.id}
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 transition hover:border-blue-300 hover:bg-blue-50"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-medium text-slate-900">{item.name}</p>
                              <span className="text-sm font-semibold text-slate-900">{formatCurrency(item.price)}</span>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                              <span className="rounded bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                                {STORAGE_MEDIA_LABELS[inferStorageMediaTypeFromInventoryItem(item)]}
                              </span>
                              <span>{item.capacity_label}</span>
                              <span>{item.interface_label}</span>
                              {item.form_factor && <span>{item.form_factor}</span>}
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                  {part.category === "storage" && largeCapacityHddCandidates.length > 0 && (
                    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
                      <p className="text-xs font-semibold text-amber-800">大容量用途向け 追加ストレージ候補（HDD）</p>
                      <div className="mt-2 grid gap-2">
                        {largeCapacityHddCandidates.map((item) => (
                          <a
                            key={`hdd-${item.id}`}
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded-lg border border-amber-200 bg-white px-3 py-2 transition hover:border-amber-300 hover:bg-amber-100"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-medium text-slate-900">{item.name}</p>
                              <span className="text-sm font-semibold text-slate-900">{formatCurrency(item.price)}</span>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                              <span className="rounded bg-amber-200 px-2 py-0.5 text-[10px] font-semibold text-amber-800">HDD</span>
                              <span>{item.capacity_label}</span>
                              <span>HDD</span>
                              {item.form_factor && <span>{item.form_factor}</span>}
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
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

          <button
            onClick={onBack}
            className="mt-8 w-full px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition font-bold text-lg"
          >
            別の構成を生成
          </button>
        </div>
      </div>
    </div>
  );
}
