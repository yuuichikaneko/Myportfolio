import {
  GenerateConfigResponse,
  SavedConfigurationResponse,
  SavedPartResponse,
} from "./api";

interface ResultProps {
  config: GenerateConfigResponse | SavedConfigurationResponse;
  onBack: () => void;
}

export function ResultView({ config, onBack }: ResultProps) {
  const formatCurrency = (price: number) =>
    new Intl.NumberFormat("ja-JP", {
      style: "currency",
      currency: "JPY",
    }).format(price);

  const isSavedConfiguration = (value: GenerateConfigResponse | SavedConfigurationResponse): value is SavedConfigurationResponse =>
    "created_at" in value;

  const IGPU_USAGES = new Set(["business", "standard"]);

  const normalizedParts = isSavedConfiguration(config)
    ? (() => {
        const parts = [
            ["cpu", config.cpu_data],
            ["cpu_cooler", config.cpu_cooler_data],
            ["gpu", config.gpu_data],
            ["motherboard", config.motherboard_data],
            ["memory", config.memory_data],
            ["storage", config.storage_data],
            ["psu", config.psu_data],
            ["case", config.case_data],
          ]
            .filter((entry): entry is [string, SavedPartResponse] => entry[1] !== null)
            .map(([category, part]) => ({
              category,
              name: part.name,
              price: part.price,
              url: part.url,
            }));
        // iGPU構成の場合: gpu_data=null なので保存済み構成でも内蔵GPU行を復元
        if (IGPU_USAGES.has(config.usage) && config.gpu_data === null) {
          const cpuIndexForIgpu = parts.findIndex((p) => p.category === "cpu");
          parts.splice(cpuIndexForIgpu + 1, 0, {
            category: "gpu",
            name: "内蔵GPU（統合グラフィックス）",
            price: 0,
            url: "",
          });
        }
        return parts;
      })()
    : config.parts;

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

  const ESTIMATED_POWER: Record<string, number> = {
    gaming: 550,
    creator: 500,
    business: 250,
    standard: 300,
    video_editing: 500,
    general: 350,
  };
  const estimatedPower = ESTIMATED_POWER[config.usage] ?? 400;

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
                  {isSavedConfiguration(config) ? estimatedPower : config.estimated_power_w}W
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
                <div>CPUメーカー: <span className="font-semibold text-slate-800">{selectionSummary.cpuVendor ?? "指定なし"}</span></div>
                <div>構成方針: <span className="font-semibold text-slate-800">{selectionSummary.buildPriority ?? "指定なし"}</span></div>
              </div>
            </div>
          )}

          <div className="space-y-4">
            <h3 className="text-2xl font-bold text-gray-800">PC構成</h3>
            {normalizedParts.map((part, index) => {
              const isIgpu = part.category === "gpu" && part.price === 0 && part.name.includes("内蔵");
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
                      <p className="text-sm font-semibold text-gray-500 uppercase">
                        {part.category}
                      </p>
                      <p className="text-lg font-bold text-gray-800">
                        {part.name}
                      </p>
                    </div>
                    {isIgpu ? (
                      <span className="inline-block bg-green-100 text-green-700 text-xs font-semibold px-2 py-1 rounded">
                        内蔵GPU
                      </span>
                    ) : (
                      <p className="text-lg font-bold text-indigo-600">
                        {formatCurrency(part.price)}
                      </p>
                    )}
                  </div>
                  {!isIgpu && (
                    <a
                      href={part.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:text-blue-700 text-sm font-medium inline-flex items-center"
                    >
                      購入ページを見る →
                    </a>
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
