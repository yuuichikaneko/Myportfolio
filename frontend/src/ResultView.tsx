import { GenerateConfigResponse } from "./api";

interface ResultProps {
  config: GenerateConfigResponse;
  onBack: () => void;
}

export function ResultView({ config, onBack }: ResultProps) {
  const formatCurrency = (price: number) =>
    new Intl.NumberFormat("ja-JP", {
      style: "currency",
      currency: "JPY",
    }).format(price);

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
            {'ガシキース用途: '}
            <span className="font-semibold">
              {config.usage === "gaming"
                ? "ゲーミングPC"
                : config.usage === "video_editing"
                  ? "動画編集PC"
                  : "汎用PC"}
            </span>
          </p>

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
                  {config.estimated_power_w}W
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-2xl font-bold text-gray-800">PC構成</h3>
            {config.parts.map((part, index) => (
              <div
                key={index}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
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
                  <p className="text-lg font-bold text-indigo-600">
                    {formatCurrency(part.price)}
                  </p>
                </div>
                <a
                  href={part.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:text-blue-700 text-sm font-medium inline-flex items-center"
                >
                  購入ページを見る →
                </a>
              </div>
            ))}
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
