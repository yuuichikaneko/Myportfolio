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

export function ConfigForm({ onSubmit, isLoading }: ConfigFormProps) {
  const [marketRange, setMarketRange] = useState(FALLBACK_MARKET_PRICE_RANGE);
  const [budget, setBudget] = useState(FALLBACK_MARKET_PRICE_RANGE.default);
  const [usage, setUsage] = useState("gaming"); // ドスパラ4カテゴリ: gaming / creator / business / standard
  const [coolerType, setCoolerType] = useState<"air" | "liquid">("air");
  const [radiatorSize, setRadiatorSize] = useState<"120" | "240" | "360">("240");
  const [coolingProfile, setCoolingProfile] = useState<"silent" | "performance">("performance");
  const [caseSize, setCaseSize] = useState<"mini" | "mid" | "full">("mid");
  const [cpuVendor, setCpuVendor] = useState<"any" | "intel" | "amd">("any");
  const [buildPriority, setBuildPriority] = useState<"cost" | "spec">("cost");
  const [useCustomBudgetWeights, setUseCustomBudgetWeights] = useState(true);
  const [customBudgetWeights, setCustomBudgetWeights] = useState<CustomBudgetWeights>(DEFAULT_CUSTOM_BUDGET_WEIGHTS);
  const [gpuRange, setGpuRange] = useState<PartPriceRange | null>(null);

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
        // fallback を使う
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
        // 取得失敗時は非表示
      }
    };

    loadPartRanges();
  }, []);

  // ビジネス・スタンダードは下限 - 15,000円をデフォルト予算にする
  useEffect(() => {
    if (usage === "business" || usage === "standard") {
      setBudget(Math.max(0, marketRange.min - 15000));
    }
  }, [usage, marketRange.min]);

  const BUDGET_MIN = 50000;
  const BUDGET_MAX = 1500000;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clamped = Math.min(BUDGET_MAX, Math.max(BUDGET_MIN, budget));
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
    const sub = 15000; // 全用途・全段階で一律 -15,000円
    if (usage === "gaming") {
      // ドスパラ ゲーミングデスクトップ一覧 (TC30?srule=04) 掲載価格帯を基準に設定 - 15,000円
      // エントリー: ¥184,980 / ミドル: ¥274,980 / ハイ: ¥589,980 / フラッグシップ: ¥1,309,980
      const bases = [184980, 274980, 589980, 1309980].map((v) => Math.min(BUDGET_MAX, v));
      const [e, m, h, f] = bases.map((p) => p - sub);
      return [
        { label: `エントリー (${Math.round(e / 1000)}k)`,     value: e },
        { label: `ミドル (${Math.round(m / 1000)}k)`,         value: m },
        { label: `ハイ (${Math.round(h / 1000)}k)`,           value: h },
        { label: `フラッグシップ (${Math.round(f / 1000)}k)`, value: f },
      ];
    }

    if (usage === "standard") {
      // ドスパラ THIRDWAVE 個人向けデスクトップPC価格帯 (general_desk ページ掲載価格 - 15,000円)
      // ¥89,980 (i5-12400) / ¥109,980 (i5-12400 DDR5) / ¥172,980 (i7-14700) / ¥249,980 (Ryzen7+RTX5070)
      const bases = [89980, 109980, 172980, 249980];
      const [e, m, h, f] = bases.map((p) => p - sub);
      return [
        { label: `エントリー (${Math.round(e / 1000)}k)`,     value: e },
        { label: `ミドル (${Math.round(m / 1000)}k)`,         value: m },
        { label: `ハイ (${Math.round(h / 1000)}k)`,           value: h },
        { label: `フラッグシップ (${Math.round(f / 1000)}k)`, value: f },
      ];
    }

    if (usage === "business") {
      // ドスパラ THIRDWAVE ビジネス/スタンダード価格帯 (min基準 - 15,000円)
      return [
        { label: `エントリー (${Math.round((min - sub) / 1000)}k)`,             value: Math.max(0, min - sub)                                    },
        { label: `ミドル (${Math.round((min * 1.3 - sub) / 1000)}k)`,           value: Math.max(0, Math.round(min * 1.3  / 10000) * 10000 - sub) },
        { label: `ハイ (${Math.round((min * 1.7 - sub) / 1000)}k)`,             value: Math.max(0, Math.round(min * 1.7  / 10000) * 10000 - sub) },
        { label: `フラッグシップ (${Math.round((min * 2.2 - sub) / 1000)}k)`,  value: Math.max(0, Math.round(min * 2.2  / 10000) * 10000 - sub) },
      ];
    }

    // ドスパラ GALLERIA 動画配信向けモデル価格帯 (galleria-haishin ページ掲載価格 - 15,000円)
    // ¥349,980(エントリー帯据え置き) / ¥574,980(ミドル帯据え置き) / ¥679,980(ハイ)
    // ¥979,980(フラッグシップ)
    const bases = [349980, 574980, 679980];
    const [e, m, h] = bases.map((p) => p - sub);
    const f = 979980 - sub;
    return [
      { label: `エントリー (${Math.round(e / 1000)}k)`,     value: e },
      { label: `ミドル (${Math.round(m / 1000)}k)`,         value: m },
      { label: `ハイ (${Math.round(h / 1000)}k)`,           value: h },
      { label: `フラッグシップ (${Math.round(f / 1000)}k)`, value: f },
    ];
  }, [BUDGET_MAX, marketRange.max, marketRange.min, usage]);

  // プリセットの最小値〜最大値を相場目安として表示
  const usagePriceHint = useMemo(() => {
    if (presets.length === 0) return null;
    const min = Math.min(...presets.map((p) => p.value));
    const max = Math.max(...presets.map((p) => p.value));
    return { min, max };
  }, [presets]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-6">
      <div className="bg-white rounded-lg shadow-2xl p-8 max-w-md w-full">
        <h1 className="text-4xl font-bold text-gray-800 mb-2">
          PC構成提案
        </h1>
        <p className="text-gray-600 mb-8">
          予算と用途を入力して、最適なPC構成を提案します
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Budget Input */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              予算（日本円）
            </label>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              min={50000}
              max={1500000}
              step={1}
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:border-indigo-500 font-bold text-lg"
            />
            <p className="text-gray-600 text-sm mt-1">
              ¥{budget.toLocaleString("ja-JP")}
            </p>
            <p className="text-gray-500 text-xs mt-1">
              {usagePriceHint
                ? `相場目安: ¥${usagePriceHint.min.toLocaleString("ja-JP")} ~ ¥${usagePriceHint.max.toLocaleString("ja-JP")}`
                : `相場目安: ¥${marketRange.min.toLocaleString("ja-JP")} ~ ¥${marketRange.max.toLocaleString("ja-JP")}`
              }
            </p>
            {gpuRange?.max != null && gpuRange?.min != null && (
              <p className="text-indigo-700 text-xs mt-1">
                GPU価格帯（最新）: ¥{gpuRange.min.toLocaleString("ja-JP")} ~ ¥{gpuRange.max.toLocaleString("ja-JP")}（{gpuRange.count}件）
              </p>
            )}
          </div>

          {/* Budget Presets */}
          <div className="grid grid-cols-2 gap-2">
            {presets.map((preset) => (
              <button
                key={preset.value}
                type="button"
                onClick={() => setBudget(preset.value)}
                className={`px-3 py-2 rounded-lg font-medium transition text-sm ${
                  budget === preset.value
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Usage Selection */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              用途を選択
            </label>
            <div className="space-y-2">
              {[
                { value: "gaming",   label: "🎮 ゲーミングPC",   desc: "GPU重視・高フレームレート向け" },
                { value: "creator",  label: "🎨 クリエイターPC", desc: "動画編集・3DCG・配信向け" },
                { value: "business", label: "💼 ビジネスPC",     desc: "オフィス作業・安定運用重視（内蔵GPU使用）" },
                { value: "standard", label: "🖥️ スタンダードPC", desc: "日常使い・バランス型（内蔵GPU使用）" },
              ].map((option) => (
                <label
                  key={option.value}
                  className={`cursor-pointer p-3 border-2 rounded-lg transition ${
                    usage === option.value
                      ? "border-indigo-600 bg-indigo-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="usage"
                    value={option.value}
                    checked={usage === option.value}
                    onChange={(e) => setUsage(e.target.value)}
                    className="mr-2"
                  />
                  <span className="font-semibold text-gray-800">
                    {option.label}
                  </span>
                  <p className="text-xs text-gray-600">{option.desc}</p>
                </label>
              ))}
            </div>
          </div>

          {/* CPU Cooler Type Selection */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              CPUクーラー方式
            </label>
            <div className="space-y-2">
              {[
                { value: "air", label: "空冷", desc: "静音性・メンテ性重視" },
                { value: "liquid", label: "水冷", desc: "高負荷時の冷却性能重視" },
              ].map((option) => (
                <label
                  key={option.value}
                  className={`cursor-pointer p-3 border-2 rounded-lg transition ${
                    coolerType === option.value
                      ? "border-indigo-600 bg-indigo-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="coolerType"
                    value={option.value}
                    checked={coolerType === option.value}
                    onChange={(e) => setCoolerType(e.target.value as "air" | "liquid")}
                    className="mr-2"
                  />
                  <span className="font-semibold text-gray-800">
                    {option.label}
                  </span>
                  <p className="text-xs text-gray-600">{option.desc}</p>
                </label>
              ))}
            </div>
            {coolerType === "liquid" && (
              <p className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 leading-relaxed">
                水漏れした時の保証はクーラー単体で他のパーツへの保証は有りません。
              </p>
            )}
          </div>

          {coolerType === "liquid" && (
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                水冷ラジエーターサイズ
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { value: "120", label: "120mm" },
                  { value: "240", label: "240mm" },
                  { value: "360", label: "360mm" },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setRadiatorSize(option.value as "120" | "240" | "360")}
                    className={`px-3 py-2 rounded-lg font-medium transition text-sm ${
                      radiatorSize === option.value
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              クーラー方針
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { value: "silent", label: "静音重視" },
                { value: "performance", label: "冷却重視" },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setCoolingProfile(option.value as "silent" | "performance")}
                  className={`px-3 py-2 rounded-lg font-medium transition text-sm ${
                    coolingProfile === option.value
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              ケースサイズ
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "mini", label: "Mini" },
                { value: "mid", label: "Mid" },
                { value: "full", label: "Full" },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setCaseSize(option.value as "mini" | "mid" | "full")}
                  className={`px-3 py-2 rounded-lg font-medium transition text-sm ${
                    caseSize === option.value
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
              {(caseSize === "mini" || caseSize === "mid") && (
                <p className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3 leading-relaxed">
                  miniとmidケースを選んだ時に、CPUクーラーが入るサイズかご確認ください。
                </p>
              )}
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              CPUメーカー
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "any", label: "指定なし" },
                { value: "intel", label: "Intel" },
                { value: "amd", label: "AMD" },
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setCpuVendor(option.value as "any" | "intel" | "amd")}
                  className={`px-3 py-2 rounded-lg font-medium transition text-sm ${
                    cpuVendor === option.value
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              構成方針
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { value: "cost", label: "コスト重視" },
                { value: "spec", label: "スペック重視" },

          <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 space-y-3">
            <label className="flex items-center gap-2 text-sm font-semibold text-amber-900 cursor-pointer">
              <input
                type="checkbox"
                checked={useCustomBudgetWeights}
                onChange={(e) => setUseCustomBudgetWeights(e.target.checked)}
              />
              カスタム予算配分を使う
            </label>

            <p className="text-xs text-amber-800">
              CPU 20%、CPUクーラー 2%、GPU 30%、マザーボード 10%、メモリー 15%、ストレージ 15%、PSU 5%、ケース 3%
            </p>

            {useCustomBudgetWeights && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  {CUSTOM_BUDGET_WEIGHT_FIELDS.map((field) => (
                    <label key={field.key} className="text-xs text-gray-700">
                      <span className="block mb-1 font-medium">{field.label}</span>
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
                          className="w-full px-3 py-2 border border-amber-300 rounded-lg text-sm"
                        />
                        <span>%</span>
                      </div>
                    </label>
                  ))}
                </div>
                <p className={`text-xs font-semibold ${customBudgetWeightTotal === 100 ? "text-green-700" : "text-red-700"}`}>
                  合計: {customBudgetWeightTotal}%
                </p>
              </>
            )}
          </div>
              ].map((option) => (
                <button
                  key={option.value}
                  type="button"
            disabled={isLoading || (useCustomBudgetWeights && customBudgetWeightTotal <= 0)}
                  onClick={() => setBuildPriority(option.value as "cost" | "spec")}
                  className={`px-3 py-2 rounded-lg font-medium transition text-sm ${
                    buildPriority === option.value
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className={`w-full py-3 rounded-lg font-bold text-lg transition ${
              isLoading
                ? "bg-gray-400 text-white cursor-not-allowed"
                : "bg-indigo-600 text-white hover:bg-indigo-700"
            }`}
          >
            {isLoading ? "生成中..." : "構成を生成"}
          </button>
        </form>

        <p className="text-gray-500 text-xs mt-6 text-center">
          最適なPC構成を自動提案します。複数のパーツの互換性を確認してから提案しますので、安心してご利用ください。
        </p>
      </div>
    </div>
  );
}
