export type ComparableBasis = "unit" | "kg";
export type Page<T> = { items: T[]; page: number; pageSize: number; totalItems: number; totalPages: number };
export type TicketSummary = { id: string; purchasedAt: string; timezone: string; lineCount: number; totalCents: number; parseStatus: "ready" | "partial" | "failed" };

const baseUrl = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers: { Accept: "application/json", ...init?.headers } });
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export const api = {
  listTickets: (page = 1): Promise<Page<TicketSummary>> => request(`/tickets?page=${page}&pageSize=50`),
  searchProducts: (query: string): Promise<{ items: Array<{ id: string; name: string; basis: ComparableBasis; match: string }> }> => request(`/products/search?q=${encodeURIComponent(query)}&limit=10`)
};
