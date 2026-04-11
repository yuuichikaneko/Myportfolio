import type { UsageCode } from "./api";

export type NormalizedUsageCode = "gaming" | "creator" | "ai" | "general";

export function normalizeUsageCode(
  usage: string,
  fallback: NormalizedUsageCode | "all" = "all"
): NormalizedUsageCode | "all" {
  if (usage === "video_editing") {
    return "creator";
  }
  if (usage === "business" || usage === "standard") {
    return "general";
  }
  if (usage === "gaming" || usage === "creator" || usage === "ai" || usage === "general") {
    return usage;
  }
  return fallback;
}

export function isNormalizedUsageCode(value: string): value is UsageCode {
  return value === "gaming" || value === "creator" || value === "ai" || value === "general";
}