import type { ProductDetail, ProductTicketAppearance, SyncStatus, TicketDetail, TicketSummary } from "../api/client";

export const ticketId = "11111111-1111-4111-8111-111111111111";
export const secondTicketId = "22222222-2222-4222-8222-222222222222";
export const productId = "33333333-3333-4333-8333-333333333333";

export const ticketSummaries: TicketSummary[] = Array.from({ length: 50 }, (_, index) => ({
  id: index === 0 ? ticketId : "00000000-0000-4000-8000-" + String(index + 1).padStart(12, "0"),
  purchasedAt: "2026-09-" + String(Math.max(1, 18 - Math.floor(index / 3))).padStart(2, "0") + "T18:42:00+02:00",
  timezone: "Europe/Madrid",
  lineCount: 8 + index,
  totalCents: 1290 + index * 25,
  parseStatus: index === 1 ? "partial" : "ready",
}));

export const ticketDetail: TicketDetail = {
  id: ticketId,
  ticketNumber: "123456",
  purchasedAt: "2026-09-17T18:42:00+02:00",
  timezone: "Europe/Madrid",
  totalCents: 1290,
  parseStatus: "ready",
  originalPdf: { available: true, sha256: "fixture-sha256" },
  items: [
    { id: "44444444-4444-4444-8444-444444444444", lineIndex: 1, rawDescription: "Tomate pera", product: { id: productId, name: "Tomate pera", basis: "kg" }, quantity: null, quantityUnit: "kg", weightGrams: 740, comparablePriceCents: 219, comparableBasis: "kg", lineAmountCents: 162, parseStatus: "ready" },
    { id: "55555555-5555-4555-8555-555555555555", lineIndex: 2, rawDescription: "Pan integral", product: null, quantity: "1", quantityUnit: "unit", weightGrams: null, comparablePriceCents: 129, comparableBasis: "unit", lineAmountCents: 129, parseStatus: "ready" },
  ],
};

export const productDetail: ProductDetail = {
  id: productId,
  name: "Tomate pera",
  basis: "kg",
  summary: { firstPriceCents: 199, lastPriceCents: 219, minimumPriceCents: 199, maximumPriceCents: 219, changeCents: 20, changePercent: 10.05, observationCount: 2 },
  priceHistory: [
    { ticketId: secondTicketId, purchasedAt: "2026-08-01T10:00:00+02:00", priceCents: 199, basis: "kg" },
    { ticketId, purchasedAt: "2026-09-17T18:42:00+02:00", priceCents: 219, basis: "kg" },
  ],
};

export const productTickets: ProductTicketAppearance[] = [
  { ticketId: secondTicketId, purchasedAt: "2026-08-01T10:00:00+02:00", lineAmountCents: 149, comparablePriceCents: 199, basis: "kg" },
  { ticketId, purchasedAt: "2026-09-17T18:42:00+02:00", lineAmountCents: 162, comparablePriceCents: 219, basis: "kg" },
];

export const syncStatus: SyncStatus = { running: false, lastRun: null, nextScheduledAt: "2026-09-19T03:00:00+02:00", hostOnline: true };
