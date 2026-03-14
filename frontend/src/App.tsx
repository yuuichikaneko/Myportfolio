import { useState, useEffect } from "react";
import { ConfigForm } from "./ConfigForm";
import { ResultView } from "./ResultView";
import {
  CustomBudgetWeights,
  deleteSavedConfiguration,
  generateConfig,
  GenerateConfigResponse,
  getSavedConfigurations,
  getScraperStatus,
  SavedConfigurationResponse,
  ScraperStatus,
} from "./api";

function App() {
  const [result, setResult] = useState<GenerateConfigResponse | null>(null);
  const [selectedSavedConfig, setSelectedSavedConfig] = useState<SavedConfigurationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scraperStatus, setScraperStatus] = useState<ScraperStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [showStatus, setShowStatus] = useState(false);
  const [savedConfigurations, setSavedConfigurations] = useState<SavedConfigurationResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyActionLoadingId, setHistoryActionLoadingId] = useState<number | null>(null);
  const [historyBulkDeleting, setHistoryBulkDeleting] = useState(false);
  const [deleteTargetConfig, setDeleteTargetConfig] = useState<SavedConfigurationResponse | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [historyUsageFilter, setHistoryUsageFilter] = useState<"all" | "gaming" | "video_editing" | "general">("all");
  const [historyQuery, setHistoryQuery] = useState("");
  const [historyDeleteScope, setHistoryDeleteScope] = useState<"filtered" | "all">("filtered");
  const [historyToastMessage, setHistoryToastMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!historyToastMessage) {
      return;
    }

    const timer = window.setTimeout(() => {
      setHistoryToastMessage(null);
    }, 2400);

    return () => window.clearTimeout(timer);
  }, [historyToastMessage]);

  const fetchSavedConfigurations = async () => {
    try {
      setHistoryError(null);
      const configurations = await getSavedConfigurations();
      setSavedConfigurations(configurations);
    } catch (err) {
      setHistoryError(
        err instanceof Error ? err.message : "保存済み構成の取得に失敗しました"
      );
    } finally {
      setHistoryLoading(false);
    }
  };

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

  useEffect(() => {
    fetchSavedConfigurations();
  }, []);

  const handleGenerateConfig = async (
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
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await generateConfig({
        budget,
        usage: usage as "gaming" | "creator" | "business" | "standard" | "video_editing" | "general",
        cooler_type: options.coolerType,
        radiator_size: options.radiatorSize,
        cooling_profile: options.coolingProfile,
        case_size: options.caseSize,
        cpu_vendor: options.cpuVendor === "any" ? undefined : options.cpuVendor,
        build_priority: options.buildPriority,
        custom_budget_weights: options.useCustomBudgetWeights ? options.customBudgetWeights : undefined,
      });
      setResult(response);
      setSelectedSavedConfig(null);
      setHistoryLoading(true);
      await fetchSavedConfigurations();
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
    setSelectedSavedConfig(null);
    setError(null);
  };

  const handleSelectSavedConfig = (config: SavedConfigurationResponse) => {
    setSelectedSavedConfig(config);
    setResult(null);
    setError(null);
    setShowHistory(false);
  };

  const executeDeleteSavedConfig = async (config: SavedConfigurationResponse) => {
    setHistoryActionLoadingId(config.id);
    try {
      await deleteSavedConfiguration(config.id);
      if (selectedSavedConfig?.id === config.id) {
        setSelectedSavedConfig(null);
      }
      setHistoryLoading(true);
      await fetchSavedConfigurations();
      setHistoryToastMessage(`ID ${config.id} を削除しました`);
    } catch (err) {
      setHistoryError(
        err instanceof Error ? err.message : "保存済み構成の削除に失敗しました"
      );
      setHistoryToastMessage("削除に失敗しました");
    } finally {
      setHistoryActionLoadingId(null);
    }
  };

  const handleDeleteSavedConfig = (config: SavedConfigurationResponse) => {
    setDeleteTargetConfig(config);
  };

  const confirmDeleteSavedConfig = async () => {
    if (!deleteTargetConfig) {
      return;
    }

    await executeDeleteSavedConfig(deleteTargetConfig);
    setDeleteTargetConfig(null);
  };

  const handleBulkDeleteVisibleHistory = async () => {
    const deleteCandidates = historyDeleteScope === "all" ? savedConfigurations : filteredHistory;
    if (deleteCandidates.length === 0) {
      return;
    }

    const scopeLabel = historyDeleteScope === "all" ? "全件" : "表示中";
    const confirmed = window.confirm(`${scopeLabel}の ${deleteCandidates.length} 件を削除しますか？`);
    if (!confirmed) {
      return;
    }

    setHistoryBulkDeleting(true);
    setHistoryError(null);
    try {
      for (const config of deleteCandidates) {
        await deleteSavedConfiguration(config.id);
      }

      if (selectedSavedConfig && deleteCandidates.some((config) => config.id === selectedSavedConfig.id)) {
        setSelectedSavedConfig(null);
      }

      setHistoryLoading(true);
      await fetchSavedConfigurations();
      setHistoryToastMessage(`${deleteCandidates.length} 件を削除しました`);
    } catch (err) {
      setHistoryError(
        err instanceof Error ? err.message : "保存済み構成の一括削除に失敗しました"
      );
      setHistoryToastMessage("一括削除に失敗しました");
    } finally {
      setHistoryBulkDeleting(false);
    }
  };

  const filteredHistory = savedConfigurations.filter((config) => {
    if (historyUsageFilter !== "all" && config.usage !== historyUsageFilter) {
      return false;
    }

    const query = historyQuery.trim().toLowerCase();
    if (!query) {
      return true;
    }

    const partNames = [
      config.cpu_data?.name,
      config.gpu_data?.name,
      config.motherboard_data?.name,
      config.memory_data?.name,
      config.storage_data?.name,
      config.psu_data?.name,
      config.case_data?.name,
    ]
      .filter((name): name is string => Boolean(name))
      .join(" ")
      .toLowerCase();

    const target = [
      `id ${config.id}`,
      config.usage_display,
      config.total_price.toString(),
      config.budget.toString(),
      partNames,
    ]
      .join(" ")
      .toLowerCase();

    return target.includes(query);
  });

  const activeResult = result ?? selectedSavedConfig;

  return (
    <>
      <button
        onClick={() => setShowHistory(!showHistory)}
        className="fixed top-4 right-4 bg-slate-900 hover:bg-slate-800 text-white rounded px-4 py-2 text-sm font-medium transition-colors z-50"
        title={showHistory ? "保存済み構成を閉じる" : "保存済み構成を開く"}
      >
        {showHistory ? "✕ 保存履歴" : `保存履歴 ${savedConfigurations.length}`}
      </button>

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

      {showHistory && (
        <div className="fixed top-16 right-4 w-[22rem] max-w-[calc(100vw-2rem)] max-h-[calc(100vh-5rem)] overflow-y-auto bg-white border border-slate-200 rounded-2xl shadow-2xl p-4 z-40">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-lg font-bold text-slate-900">保存済み構成</div>
              <div className="text-xs text-slate-500">最新 50 件まで表示 ・ {filteredHistory.length} 件表示中</div>
            </div>
            <button
              onClick={() => {
                setHistoryLoading(true);
                fetchSavedConfigurations();
              }}
              className="text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 rounded px-3 py-1 transition-colors"
              disabled={historyBulkDeleting}
            >
              更新
            </button>
          </div>

          <div className="space-y-2 mb-4">
            <select
              value={historyUsageFilter}
              onChange={(e) => setHistoryUsageFilter(e.target.value as "all" | "gaming" | "video_editing" | "general")}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-700"
            >
              <option value="all">用途: すべて</option>
              <option value="gaming">用途: ゲーミング</option>
              <option value="video_editing">用途: 動画編集</option>
              <option value="general">用途: 汎用</option>
            </select>
            <input
              value={historyQuery}
              onChange={(e) => setHistoryQuery(e.target.value)}
              placeholder="ID・パーツ名・金額で検索"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-700"
            />
            <select
              value={historyDeleteScope}
              onChange={(e) => setHistoryDeleteScope(e.target.value as "filtered" | "all")}
              className="w-full border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700 bg-red-50"
            >
              <option value="filtered">一括削除対象: 表示中のみ</option>
              <option value="all">一括削除対象: 全件</option>
            </select>
            <button
              onClick={handleBulkDeleteVisibleHistory}
              disabled={historyBulkDeleting || (historyDeleteScope === "all" ? savedConfigurations.length === 0 : filteredHistory.length === 0)}
              className="w-full bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-sm rounded-lg px-3 py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {historyBulkDeleting
                ? "一括削除中..."
                : historyDeleteScope === "all"
                  ? `全件 ${savedConfigurations.length} 件を削除`
                  : `表示中 ${filteredHistory.length} 件を削除`}
            </button>
          </div>

          {historyLoading ? (
            <div className="text-sm text-slate-500">読み込み中...</div>
          ) : historyError ? (
            <div className="text-sm text-red-500">{historyError}</div>
          ) : savedConfigurations.length === 0 ? (
            <div className="text-sm text-slate-500">まだ保存済み構成はありません。</div>
          ) : filteredHistory.length === 0 ? (
            <div className="text-sm text-slate-500">条件に一致する保存済み構成はありません。</div>
          ) : (
            <div className="space-y-3">
              {filteredHistory.map((config) => (
                <div
                  key={config.id}
                  className="w-full text-left border border-slate-200 hover:border-indigo-400 hover:bg-indigo-50 rounded-xl p-4 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <div className="font-semibold text-slate-900">{config.usage_display}</div>
                      <div className="text-xs text-slate-500">
                        ID {config.id} ・ {new Date(config.created_at).toLocaleString("ja-JP")}
                      </div>
                    </div>
                    <div className="text-sm font-bold text-indigo-600">
                      ¥{config.total_price.toLocaleString("ja-JP")}
                    </div>
                  </div>
                  <div className="text-sm text-slate-600">
                    予算 ¥{config.budget.toLocaleString("ja-JP")}
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleSelectSavedConfig(config)}
                      className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm rounded-lg px-3 py-2 transition-colors"
                    >
                      詳細を開く
                    </button>
                    <button
                      onClick={() => handleDeleteSavedConfig(config)}
                      disabled={historyActionLoadingId === config.id || historyBulkDeleting}
                      className="bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-sm rounded-lg px-3 py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {historyActionLoadingId === config.id ? "削除中..." : "削除"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {deleteTargetConfig && (
        <div className="fixed inset-0 bg-slate-900/45 flex items-center justify-center p-4 z-[70]">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-2">構成を削除しますか？</h3>
            <p className="text-sm text-slate-600 mb-4">この操作は取り消せません。</p>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-700 space-y-1 mb-5">
              <div>ID: {deleteTargetConfig.id}</div>
              <div>用途: {deleteTargetConfig.usage_display}</div>
              <div>予算: ¥{deleteTargetConfig.budget.toLocaleString("ja-JP")}</div>
              <div>構成金額: ¥{deleteTargetConfig.total_price.toLocaleString("ja-JP")}</div>
            </div>

            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteTargetConfig(null)}
                disabled={historyActionLoadingId === deleteTargetConfig.id}
                className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              >
                キャンセル
              </button>
              <button
                onClick={confirmDeleteSavedConfig}
                disabled={historyActionLoadingId === deleteTargetConfig.id}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm disabled:opacity-50"
              >
                {historyActionLoadingId === deleteTargetConfig.id ? "削除中..." : "削除する"}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="fixed top-0 left-0 right-0 bg-red-500 text-white p-4 text-center">
          エラー: {error}
        </div>
      )}

      {historyToastMessage && (
        <div className="fixed bottom-4 right-4 bg-slate-900 text-white text-sm px-4 py-3 rounded-lg shadow-lg z-[80]">
          {historyToastMessage}
        </div>
      )}

      {activeResult ? (
        <ResultView config={activeResult} onBack={handleBack} />
      ) : (
        <ConfigForm onSubmit={handleGenerateConfig} isLoading={isLoading} />
      )}
    </>
  );
}

export default App;
