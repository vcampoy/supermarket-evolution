import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  Object.defineProperty(globalThis, "ResizeObserver", { writable: true, value: class { observe(): void {} unobserve(): void {} disconnect(): void {} } });
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
