import { useState } from "react";

interface ConfigFormProps {
  onSubmit: (budget: number, usage: string) => void;
  isLoading: boolean;
}

export function ConfigForm({ onSubmit, isLoading }: ConfigFormProps) {
  const [budget, setBudget] = useState(100000);
  const [usage, setUsage] = useState("gaming");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(budget, usage);
  };

  const presets = [
    { label: "エントリー (50k)", value: 50000 },
    { label: "ミドル (100k)", value: 100000 },
    { label: "ハイエンド (150k)", value: 150000 },
    { label: "プレミアム (200k)", value: 200000 },
  ];

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
              max={500000}
              step={10000}
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:border-indigo-500 font-bold text-lg"
            />
            <p className="text-gray-600 text-sm mt-1">
              ¥{budget.toLocaleString("ja-JP")}
            </p>
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
                { value: "gaming", label: "🎮 ゲーミングPC", desc: "高いGPU性能" },
                { value: "video_editing", label: "🎬 動画編集PC", desc: "CPU・メモリ重視" },
                { value: "general", label: "💼 汎用PC", desc: "バランス型" },
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
