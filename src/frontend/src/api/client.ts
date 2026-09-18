export type ComparableBasis = "unit" | "kg";
export type ParseStatus = "ready" | "partial" | "failed" | "needs_review";

export type Page<T> = { items: T[]; page: number; pageSize: number; totalItems: number; totalPages: number };
export type TicketSummary = { id: string; purchasedAt: string; timezone: string; lineCount: number; totalCents: number; parseStatus: ParseStatus };
export type TicketItem = { id: string; lineIndex: number; rawDescription: string; product: { id: string; name: string; basis: ComparableBasis } | null; quantity: string | null; quantityUnit: string; weightGrams: number | null; comparablePriceCents: number | null; comparableBasis: ComparableBasis | null; lineAmountCents: number; parseStatus: ParseStatus };
export type TicketDetail = { id: string; ticketNumber: string | null; purchasedAt: string; timezone: string; totalCents: number; parseStatus: ParseStatus; originalPdf: { available: boolean; sha256: string | null }; items: TicketItem[] };
export type ProductSearchItem = { id: string; name: string; basis: ComparableBasis; match: string };
export type PriceSummary = { firstPriceCents: number | null; lastPriceCents: number | null; minimumPriceCents: number | null; maximumPriceCents: number | null; changeCents: number | null; changePercent: number | null; observationCount: number };
export type HistoryPoint = { ticketId: string; purchasedAt: string; priceCents: number; basis: ComparableBasis };
export type ProductDetail = { id: string; name: string; basis: ComparableBasis; summary: PriceSummary; priceHistory: HistoryPoint[] };
export type ProductTicketAppearance = { ticketId: string; purchasedAt: string; lineAmountCents: number; comparablePriceCents: number; basis: ComparableBasis };
export type SyncRun = { id: string; mode: string; status: string; matchedMessages: number; importedTickets: number; skippedDuplicates: number; partialTickets: number; errorCount: number; errors: Array<{ code: string; count: number }> };
export type SyncStatus = { running: boolean; lastRun: { id: string; mode: string; status: string; startedAt: string | null; finishedAt: string | null; importedTickets: number; partialTickets: number; errorCount: number } | null; nextScheduledAt: string | null; hostOnline: boolean };

type ErrorEnvelope = { error?: { code?: string; message?: string; requestId?: string } };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

const baseUrl = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const fetchInit: RequestInit = { ...init, headers: { Accept: "application/json", ...init?.headers } };
  if (import.meta.env.MODE === "test") delete fetchInit.signal;
  else fetchInit.signal = init?.signal;
  const response = await fetch(`${baseUrl}${path}`, fetchInit);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    throw new ApiError(response.status, body.error?.code ?? "API_REQUEST_FAILED", body.error?.message ?? "No se pudo completar la solicitud.", body.error?.requestId ?? null);
  }
  return response.json() as Promise<T>;
}

const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined) search.set(key, String(value)); });
  return search.toString();
};

export const api = {
  listTickets: (page = 1, signal?: AbortSignal) => request<Page<TicketSummary>>(`/tickets?${query({ page, pageSize: 50 })}`, { signal }),
  getTicket: (ticketId: string, signal?: AbortSignal) => request<TicketDetail>(`/tickets/${ticketId}`, { signal }),
  searchProducts: (term: string, signal?: AbortSignal) => request<{ items: ProductSearchItem[] }>(`/products/search?${query({ q: term, limit: 10 })}`, { signal }),
  getProduct: (productId: string, signal?: AbortSignal) => request<ProductDetail>(`/products/${productId}`, { signal }),
  getProductTickets: (productId: string, page = 1, signal?: AbortSignal) => request<Page<ProductTicketAppearance>>(`/products/${productId}/tickets?${query({ page, pageSize: 50 })}`, { signal }),
  getSyncStatus: (signal?: AbortSignal) => request<SyncStatus>("/sync/status", { signal }),
  startSync: (mode: "manual" | "backfill" | "incremental" | "recovery" = "manual", signal?: AbortSignal) => request<{ id: string; mode: string; status: string }>("/sync-runs", { method: "POST", signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }) }),
  getSyncRun: (runId: string, signal?: AbortSignal) => request<SyncRun>(`/sync-runs/${runId}`, { signal }),
};
