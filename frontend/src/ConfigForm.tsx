import { useEffect, useMemo, useState } from "react";
import { getMarketPriceRange, getPartPriceRanges, type CustomBudgetWeights, type PartPriceRange } from "./api";

const FALLBACK_MARKET_PRICE_RANGE = {
  min: 89980,
  max: 404980,
  default: 250000,
};

interface ConfigFormProps {
  onSubmit: (
    budget: number,
    usage: string,
    options: {
      coolerType: "air" | "liquid";
      radiatorSize: "120" | "240" | "360";
      coolingProfile: "silent" | "performance";
      caseSize: "mini" | "mid" | "full";
      cpuVendor: "any" | "intel" | "amd";
      buildPriority: "cost" | "spec";
      useCustomBudgetWeights: boolean;
      customBudgetWeights: CustomBudgetWeights;
    }
  ) => void;
  isLoading: boolean;
}

const DEFAULT_CUSTOM_BUDGET_WEIGHTS: CustomBudgetWeights = {
  cpu: 20,
  cpu_cooler: 2,
  gpu: 30,
  motherboard: 10,
  memory: 15,
  storage: 15,
  psu: 5,
  case: 3,
};

const CUSTOM_BUDGET_WEIGHT_FIELDS: Array<{ key: keyof CustomBudgetWeights; label: string }> = [
  { key: "cpu", label: "CPU" },
  { key: "cpu_cooler", label: "CPUクーラー" },
  { key: "gpu", label: "GPU" },
  { key: "motherboard", label: "マザーボード" },
  { key: "memory", label: "メモリー" },
  { key: "storage", label: "ストレージ" },
  { key: "psu", label: "PSU" },
  { key: "case", label: "ケース" },
];

const USAGE_OPTIONS = [
  { value: "gaming", label: "ゲーミングPC", icon: "🎮", desc: "GPU重視・高フレームレート向け" },
  { value: "creator", label: "クリエイターPC", icon: "🎨", desc: "動画編集・3DCG・配信向け" },
  { value: "business", label: "ビジネスPC", icon: "💼", desc: "オフィス作業・安定運用重視" },
  { value: "standard", label: "スタンダードPC", icon: "🖥️", desc: "日常使い・バランス型" },
] as const;

const COOLER_OPTIONS = [
  { value: "air", label: "空冷", desc: "静音性・メンテ重視" },
  { value: "liquid", label: "水冷", desc: "高負荷時の冷却性能重視" },
] as const;

const RADIATOR_OPTIONS = [
  { value: "120", label: "120mm" },
  { value: "240", label: "240mm" },
  { value: "360", label: "360mm" },
] as const;

const COOLING_PROFILE_OPTIONS = [
  { value: "silent", label: "静音重視" },
  { value: "performance", label: "冷却重視" },
] as const;

const CASE_SIZE_OPTIONS = [
  { value: "mini", label: "コンパクト" },
  { value: "mid", label: "ミドル" },
  { value: "full", label: "フルサイズ" },
] as const;

const CPU_VENDOR_OPTIONS = [
  { value: "any", label: "こだわらない" },
  { value: "intel", label: "Intel" },
  { value: "amd", label: "AMD" },
] as const;

const BUILD_PRIORITY_OPTIONS = [
  { value: "cost", label: "コスト重視" },
  { value: "spec", label: "スペック重視" },
] as const;

export function ConfigForm({ onSubmit, isLoading }: ConfigFormProps) {
  const [marketRange, setMarketRange] = useState(FALLBACK_MARKET_PRICE_RANGE);
  const [budget, setBudget] = useState(FALLBACK_MARKET_PRICE_RANGE.default);
  const [usage, setUsage] = useState("gaming");
  const [coolerType, setCoolerType] = useState<"air" | "liquid">("air");
  const [radiatorSize, setRadiatorSize] = useState<"120" | "240" | "360">("240");
  const [coolingProfile, setCoolingProfile] = useState<"silent" | "performance">("performance");
  const [caseSize, setCaseSize] = useState<"mini" | "mid" | "full">("mid");
  const [cpuVendor, setCpuVendor] = useState<"any" | "intel" | "amd">("any");
  const [buildPriority, setBuildPriority] = useState<"cost" | "spec">("cost");
  const [useCustomBudgetWeights, setUseCustomBudgetWeights] = useState(false);
  const [customBudgetWeights, setCustomBudgetWeights] = useState<CustomBudgetWeights>(DEFAULT_CUSTOM_BUDGET_WEIGHTS);
  const [gpuRange, setGpuRange] = useState<PartPriceRange | null>(null);
  const [showMarketSummary, setShowMarketSummary] = useState(false);
  const [popupMessage, setPopupMessage] = useState<string | null>(null);
  const [activeUsageTooltip, setActiveUsageTooltip] = useState<string | null>(null);
  const [activeCoolerTooltip, setActiveCoolerTooltip] = useState<string | null>(null);

  useEffect(() => {
    const loadMarketRange = async () => {
      try {
        const range = await getMarketPriceRange();
        if (range.min > 0 && range.max >= range.min) {
          const safeDefault = Math.min(range.max, Math.max(range.min, range.default));
          setMarketRange({ min: range.min, max: range.max, default: safeDefault });
          setBudget((current) => {
            if (current < range.min || current > range.max) {
              return safeDefault;
            }
            return current;
          });
        }
      } catch {
        return;
      }
    };

    loadMarketRange();
  }, []);

  useEffect(() => {
    const loadPartRanges = async () => {
      try {
        const ranges = await getPartPriceRanges();
        if (ranges.gpu) {
          setGpuRange(ranges.gpu);
        }
      } catch {
        return;
      }
    };

    loadPartRanges();
  }, []);

  useEffect(() => {
    if (usage === "business" || usage === "standard") {
      setBudget(Math.max(0, marketRange.min - 15000));
    }
  }, [usage, marketRange.min]);

  useEffect(() => {
    if (!popupMessage) {
      return;
    }

    const timer = window.setTimeout(() => {
      setPopupMessage(null);
    }, 2200);

    return () => window.clearTimeout(timer);
  }, [popupMessage]);

  const budgetMin = 50000;
  const budgetMax = 1500000;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const clamped = Math.min(budgetMax, Math.max(budgetMin, budget));
    onSubmit(clamped, usage, {
      coolerType,
      radiatorSize,
      coolingProfile,
      caseSize,
      cpuVendor,
      buildPriority,
      useCustomBudgetWeights,
      customBudgetWeights,
    });
  };

  const customBudgetWeightTotal = useMemo(
    () => Object.values(customBudgetWeights).reduce((sum, value) => sum + value, 0),
    [customBudgetWeights]
  );

  const presets = useMemo(() => {
    const min = marketRange.min;
    const sub = 15000;

    if (usage === "gaming") {
      const bases = [184980, 274980, 589980, 1309980].map((value) => Math.min(budgetMax, value));
      const [entry, middle, high, flagship] = bases.map((price) => price - sub);
      return [
        { label: "ロウ", value: entry },
        { label: "ミドル", value: middle },
        { label: "ハイ", value: high },
        { label: "ハイエンド", value: flagship },
      ];
    }

    if (usage === "standard") {
      const bases = [89980, 109980, 172980, 249980];
      const [entry, middle, high, flagship] = bases.map((price) => price - sub);
      return [
        { label: "ロウ", value: entry },
        { label: "ミドル", value: middle },
        { label: "ハイ", value: high },
        { label: "ハイエンド", value: flagship },
      ];
    }

    if (usage === "business") {
      return [
        { label: "ロウ", value: Math.max(0, min - sub) },
        { label: "ミドル", value: Math.max(0, Math.round((min * 1.3) / 10000) * 10000 - sub) },
        { label: "ハイ", value: Math.max(0, Math.round((min * 1.7) / 10000) * 10000 - sub) },
        { label: "ハイエンド", value: Math.max(0, Math.round((min * 2.2) / 10000) * 10000 - sub) },
      ];
    }

    const bases = [349980, 574980, 679980];
    const [entry, middle, high] = bases.map((price) => price - sub);
    const flagship = 979980 - sub;

    return [
      { label: "ロウ", value: entry },
      { label: "ミドル", value: middle },
      { label: "ハイ", value: high },
      { label: "ハイエンド", value: flagship },
    ];
  }, [budgetMax, marketRange.min, usage]);

  const usagePriceHint = useMemo(() => {
    if (presets.length === 0) {
      return null;
    }
    const min = Math.min(...presets.map((preset) => preset.value));
    const max = Math.max(...presets.map((preset) => preset.value));
    return { min, max };
  }, [presets]);

  const budgetProgress = useMemo(() => {
    const range = budgetMax - budgetMin;
    if (range <= 0) {
      return 0;
    }
    return Math.max(0, Math.min(100, ((budget - budgetMin) / range) * 100));
  }, [budget, budgetMax, budgetMin]);

  const canSubmit = !isLoading && (!useCustomBudgetWeights || customBudgetWeightTotal > 0);

  const segmentButtonClass = (selected: boolean) =>
    `rounded-lg border px-3 py-2 text-sm font-medium transition ${
      selected
        ? "border-blue-700 bg-blue-700 text-white"
        : "border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
    }`;

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-6">
      <div className="mx-auto max-w-4xl space-y-4">
        <header className="rounded-xl border border-slate-300 bg-white p-5">
          {showMarketSummary && (
            <>
              <p className="mt-1 text-sm text-slate-600">予算と用途を選ぶと、条件に沿った構成を提案します。</p>
              <div className="mt-4 grid gap-2 text-sm">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  相場目安: <span className="font-semibold text-slate-900">{usagePriceHint ? `¥${usagePriceHint.min.toLocaleString("ja-JP")} - ¥${usagePriceHint.max.toLocaleString("ja-JP")}` : `¥${marketRange.min.toLocaleString("ja-JP")} - ¥${marketRange.max.toLocaleString("ja-JP")}`}</span>
                </div>
              </div>
            </>
          )}
          {gpuRange?.max != null && gpuRange?.min != null && (
            <p className="mt-2 text-xs text-slate-600">
              GPU価格帯: ¥{gpuRange.min.toLocaleString("ja-JP")} - ¥{gpuRange.max.toLocaleString("ja-JP")}
            </p>
          )}
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div className="h-full bg-blue-600" style={{ width: `${budgetProgress}%` }} />
          </div>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-300 bg-white p-5">
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-slate-900">1. 予算</h2>
            <label className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={showMarketSummary}
                onChange={(e) => setShowMarketSummary(e.target.checked)}
              />
              相場目安の表示
            </label>
            <input
              type="number"
              value={budget}
              onFocus={() => setPopupMessage(`入力範囲: ¥${budgetMin.toLocaleString("ja-JP")} - ¥${budgetMax.toLocaleString("ja-JP")}`)}
              onChange={(e) => {
                setBudget(Number(e.target.value));
                setPopupMessage(`入力範囲: ¥${budgetMin.toLocaleString("ja-JP")} - ¥${budgetMax.toLocaleString("ja-JP")}`);
              }}
              min={50000}
              max={1500000}
              step={1}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-center text-lg font-semibold text-slate-900 outline-none focus:border-blue-600"
            />
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {presets.map((preset) => (
                <button key={preset.value} type="button" onClick={() => setBudget(preset.value)} className={segmentButtonClass(budget === preset.value)}>
                  {preset.label}
                </button>
              ))}
            </div>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-4">
            <h2 className="text-base font-semibold text-slate-900">2. 用途</h2>
            <div className="grid gap-2 sm:grid-cols-2">
              {USAGE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={`relative rounded-lg border p-3 ${usage === option.value ? "border-blue-700 bg-blue-50" : "border-slate-300"}`}
                  onMouseEnter={() => setActiveUsageTooltip(option.value)}
                  onMouseLeave={() => setActiveUsageTooltip((current) => (current === option.value ? null : current))}
                >
                  <input
                    type="radio"
                    name="usage"
                    value={option.value}
                    checked={usage === option.value}
                    onChange={(e) => {
                      const nextUsage = e.target.value;
                      setUsage(nextUsage);
                    }}
                    onFocus={() => setActiveUsageTooltip(option.value)}
                    onBlur={() => setActiveUsageTooltip((current) => (current === option.value ? null : current))}
                    className="mr-2"
                  />
                  <span className="font-medium text-slate-900">{option.icon} {option.label}</span>
                  {activeUsageTooltip === option.value && (
                    <span className="pointer-events-none absolute -top-11 left-1/2 z-30 w-max max-w-[90%] -translate-x-1/2 rounded-md border border-blue-200 bg-white px-3 py-1 text-xs font-medium text-blue-800 shadow-md">
                      {option.desc}
                    </span>
                  )}
                </label>
              ))}
            </div>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-4">
            <h2 className="text-base font-semibold text-slate-900">3. 冷却・ケース</h2>

            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-800">CPUクーラー方式</p>
              {COOLER_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={`relative block rounded-lg border p-3 ${coolerType === option.value ? "border-blue-700 bg-blue-50" : "border-slate-300"}`}
                  onMouseEnter={() => setActiveCoolerTooltip(option.value)}
                  onMouseLeave={() => setActiveCoolerTooltip((current) => (current === option.value ? null : current))}
                >
                  <input
                    type="radio"
                    name="coolerType"
                    value={option.value}
                    checked={coolerType === option.value}
                    onChange={(e) => setCoolerType(e.target.value as "air" | "liquid")}
                    onFocus={() => setActiveCoolerTooltip(option.value)}
                    onBlur={() => setActiveCoolerTooltip((current) => (current === option.value ? null : current))}
                    className="mr-2"
                  />
                  <span className="font-medium text-slate-900">{option.label}</span>
                  {activeCoolerTooltip === option.value && (
                    <span className="pointer-events-none absolute -top-11 left-1/2 z-30 w-max max-w-[90%] -translate-x-1/2 rounded-md border border-blue-200 bg-white px-3 py-1 text-xs font-medium text-blue-800 shadow-md">
                      {option.desc}
                    </span>
                  )}
                </label>
              ))}
            </div>

            {coolerType === "liquid" && (
              <div className="space-y-2 rounded-lg border border-rose-200 bg-rose-50 p-3">
                <p className="text-xs text-rose-700">水漏れ時の保証はクーラー単体のみで、他パーツは対象外になる可能性があります。</p>
                <div className="grid grid-cols-3 gap-2">
                  {RADIATOR_OPTIONS.map((option) => (
                    <button key={option.value} type="button" onClick={() => setRadiatorSize(option.value as "120" | "240" | "360")} className={segmentButtonClass(radiatorSize === option.value)}>
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-sm font-medium text-slate-800">クーラー方針</p>
                <div className="grid grid-cols-2 gap-2">
                  {COOLING_PROFILE_OPTIONS.map((option) => (
                    <button key={option.value} type="button" onClick={() => setCoolingProfile(option.value as "silent" | "performance")} className={segmentButtonClass(coolingProfile === option.value)}>
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-slate-800">ケースサイズ</p>
                <div className="grid grid-cols-3 gap-2">
                  {CASE_SIZE_OPTIONS.map((option) => (
                    <button key={option.value} type="button" onClick={() => setCaseSize(option.value as "mini" | "mid" | "full")} className={segmentButtonClass(caseSize === option.value)}>
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {(caseSize === "mini" || caseSize === "mid") && (
              <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                コンパクト / ミドルケースでは、CPUクーラー高とラジエーター対応寸法を確認してください。
              </p>
            )}
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-4">
            <h2 className="text-base font-semibold text-slate-900">4. CPUと構成方針</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-sm font-medium text-slate-800">CPUメーカー</p>
                <div className="grid grid-cols-3 gap-2">
                  {CPU_VENDOR_OPTIONS.map((option) => (
                    <button key={option.value} type="button" onClick={() => setCpuVendor(option.value as "any" | "intel" | "amd")} className={segmentButtonClass(cpuVendor === option.value)}>
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-slate-800">構成方針</p>
                <div className="grid grid-cols-2 gap-2">
                  {BUILD_PRIORITY_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      disabled={isLoading || (useCustomBudgetWeights && customBudgetWeightTotal <= 0)}
                      onClick={() => setBuildPriority(option.value as "cost" | "spec")}
                      className={`${segmentButtonClass(buildPriority === option.value)} disabled:cursor-not-allowed disabled:opacity-50`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="space-y-3 border-t border-slate-200 pt-4">
            <h2 className="text-base font-semibold text-slate-900">5. 予算配分</h2>
            <label className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <input type="checkbox" checked={useCustomBudgetWeights} onChange={(e) => setUseCustomBudgetWeights(e.target.checked)} />
              カスタム予算配分を使う
            </label>

            {useCustomBudgetWeights && (
              <>
                <div className="mx-auto grid w-full max-w-2xl gap-3 sm:grid-cols-2">
                  {CUSTOM_BUDGET_WEIGHT_FIELDS.map((field) => (
                    <label key={field.key} className="mx-auto flex w-full max-w-xs items-center justify-between rounded-lg border border-slate-300 p-3 text-sm text-slate-700">
                      <span className="font-medium">{field.label}</span>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          min={0}
                          step={1}
                          value={customBudgetWeights[field.key]}
                          onChange={(e) => {
                            const nextValue = Number(e.target.value);
                            setCustomBudgetWeights((current) => ({
                              ...current,
                              [field.key]: Number.isFinite(nextValue) ? nextValue : 0,
                            }));
                          }}
                          className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-center text-sm text-slate-900 outline-none focus:border-blue-600"
                        />
                        <span className="text-slate-600">%</span>
                      </div>
                    </label>
                  ))}
                </div>
                <p className={`text-center text-sm font-semibold ${customBudgetWeightTotal === 100 ? "text-emerald-700" : "text-rose-700"}`}>
                  合計: {customBudgetWeightTotal}%
                </p>
              </>
            )}
          </section>

          <button
            type="submit"
            disabled={!canSubmit}
            className={`w-full rounded-lg px-4 py-3 text-base font-semibold transition ${
              canSubmit
                ? "bg-blue-700 text-white hover:bg-blue-800"
                : "cursor-not-allowed bg-slate-300 text-slate-600"
            }`}
          >
            {isLoading ? "構成を生成中..." : "PC構成を提案してもらう"}
          </button>

          <p className="text-center text-xs text-slate-500">
            全パーツの互換性を確認しながら、条件に沿った構成を提案します。
          </p>
        </form>
      </div>

      {popupMessage && (
        <div className="fixed top-4 left-1/2 z-[70] -translate-x-1/2 rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-800 shadow-lg">
          {popupMessage}
        </div>
      )}
    </div>
  );
}