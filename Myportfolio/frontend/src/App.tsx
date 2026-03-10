import { useState } from "react";
import { ConfigForm } from "./ConfigForm";
import { ResultView } from "./ResultView";
import { generateConfig, GenerateConfigResponse } from "./api";

function App() {
  const [result, setResult] = useState<GenerateConfigResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
