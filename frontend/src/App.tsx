import { useState, useEffect } from "react";
import { ConfigForm } from "./ConfigForm";
import { ResultView } from "./ResultView";
import { generateConfig, GenerateConfigResponse, getScraperStatus, ScraperStatus } from "./api";

function App() {
  const [result, setResult] = useState<GenerateConfigResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scraperStatus, setScraperStatus] = useState<ScraperStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [showStatus, setShowStatus] = useState(false);

  // スクレイパー状態を定期的に取得
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await getScraperStatus();
        setScraperStatus(status);
      } catch (err) {
        console.error("Failed to fetch scraper status:", err);
      } finally {
        setStatusLoading(false);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // 30秒ごとに更新

    return () => clearInterval(interval);
  }, []);

  const handleGenerateConfig = async (budget: number, usage: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await generateConfig({
        budget,
        usage: usage as "gaming" | "video_editing" | "general",
      });
      setResult(response);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "予期しないエラーが発生しました"
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    setResult(null);
    setError(null);
  };

  return (
    <>
      {/* スクレイパー統計情報パネル表示切り替えボタン */}
      <button
        onClick={() => setShowStatus(!showStatus)}
        className="fixed bottom-4 left-4 bg-blue-500 hover:bg-blue-600 text-white rounded px-3 py-2 text-sm font-medium transition-colors z-50"
        title={showStatus ? "スクレイパー情報を非表示" : "スクレイパー情報を表示"}
      >
        {showStatus ? "▼ スクレイパー" : "▶ スクレイパー"}
      </button>

      {/* スクレイパー統計情報パネル */}
      {scraperStatus && !statusLoading && showStatus && (
        <div className="fixed bottom-16 left-4 bg-slate-50 border border-slate-300 rounded-lg p-4 shadow-lg text-sm max-w-xs z-50">
          <div className="font-semibold text-slate-700 mb-2">スクレイパー状態</div>
          <div className="space-y-1 text-slate-600">
            <div>キャッシュ: {scraperStatus.cache_enabled ? "有効" : "無効"}</div>
            <div>DB パーツ数: {scraperStatus.total_parts_in_db}</div>
            <div>キャッシュ率: {scraperStatus.cached_categories.length}/7</div>
            {scraperStatus.last_update_time && (
              <div className="text-xs text-slate-500">
                最終更新: {new Date(scraperStatus.last_update_time).toLocaleString("ja-JP")}
              </div>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="fixed top-0 left-0 right-0 bg-red-500 text-white p-4 text-center">
          エラー: {error}
        </div>
      )}
      {result ? (
        <ResultView config={result} onBack={handleBack} />
      ) : (
        <ConfigForm onSubmit={handleGenerateConfig} isLoading={isLoading} />
      )}
    </>
  );
}

export default App;
