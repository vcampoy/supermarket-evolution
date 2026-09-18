import { http, HttpResponse } from "msw";
import { productDetail, productId, productTickets, secondTicketId, syncStatus, ticketDetail, ticketId, ticketSummaries } from "./fixtures";

const base = "http://localhost:8000/api/v1";
const page = (items: unknown[], current = 1, pageSize = 50) => ({ items, page: current, pageSize, totalItems: items.length, totalPages: items.length ? 1 : 0 });

export const handlers = [
  http.get(base + "/tickets", () => HttpResponse.json(page(ticketSummaries))),
  http.get(base + "/tickets/" + ticketId, () => HttpResponse.json(ticketDetail)),
  http.get(base + "/tickets/" + secondTicketId, () => HttpResponse.json({ ...ticketDetail, id: secondTicketId })),
  http.get(base + "/products/search", ({ request }) => {
    const term = new URL(request.url).searchParams.get("q") ?? "";
    return HttpResponse.json({ items: term.toLowerCase().includes("tom") ? [{ id: productId, name: "Tomate pera", basis: "kg", match: "Tomate pera" }] : [] });
  }),
  http.get(base + "/products/" + productId, () => HttpResponse.json(productDetail)),
  http.get(base + "/products/" + productId + "/tickets", () => HttpResponse.json(page(productTickets))),
  http.get(base + "/sync/status", () => HttpResponse.json(syncStatus)),
  http.post(base + "/sync-runs", () => HttpResponse.json({ id: "66666666-6666-4666-8666-666666666666", mode: "manual", status: "queued" }, { status: 202 })),
  http.get(base + "/sync-runs/66666666-6666-4666-8666-666666666666", () => HttpResponse.json({ id: "66666666-6666-4666-8666-666666666666", mode: "manual", status: "succeeded", matchedMessages: 2, importedTickets: 2, skippedDuplicates: 0, partialTickets: 0, errorCount: 0, errors: [] })),
];
