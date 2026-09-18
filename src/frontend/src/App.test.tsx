import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { productId, ticketId } from "./test/fixtures";
import { server } from "./test/setup";

function renderApp(initialEntries = ["/tickets"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={initialEntries}><App /></MemoryRouter></QueryClientProvider>);
}

test("renders the Spanish shell and active tickets navigation", async () => {
  renderApp();
  expect(screen.getByRole("heading", { name: "Tickets" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Tickets/ })).toHaveClass("active");
  expect(await screen.findByText("50 tickets")).toBeInTheDocument();
});

test("mobile menu is keyboard operable and has a visible close control", async () => {
  const user = userEvent.setup();
  renderApp();
  const menu = screen.getByRole("button", { name: "Menú" });
  expect(menu).toHaveAttribute("aria-expanded", "false");
  await user.click(menu);
  expect(menu).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("navigation", { name: "Navegación principal" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Cerrar menú" }));
  expect(menu).toHaveAttribute("aria-expanded", "false");
});

test("paginates 50 tickets and follows ticket to product and back", async () => {
  const user = userEvent.setup();
  renderApp();
  expect((await screen.findAllByRole("row")).length).toBe(51);
  await user.click(screen.getAllByRole("row", { name: /Abrir ticket/ })[0]);
  expect(await screen.findByRole("heading", { name: "Ticket 123456" })).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: /Ver evolución/ }));
  expect(await screen.findByRole("heading", { name: "Tomate pera" })).toBeInTheDocument();
  await user.click(screen.getAllByRole("link", { name: /2026/ })[0]);
  expect(await screen.findByRole("heading", { name: "Ticket 123456" })).toBeInTheDocument();
  expect(productId).toBeTruthy();
  expect(ticketId).toBeTruthy();
});

test("combobox exposes keyboard navigation and selects a product", async () => {
  const user = userEvent.setup();
  renderApp(["/products"]);
  const input = screen.getByRole("combobox", { name: "Buscar producto" });
  expect(input).toHaveAttribute("aria-expanded", "false");
  await user.type(input, "tom");
  const option = await screen.findByRole("option", { name: /Tomate pera/ });
  expect(input).toHaveAttribute("aria-expanded", "true");
  await user.keyboard("{ArrowDown}{Enter}");
  expect(await screen.findByRole("heading", { name: "Tomate pera" })).toBeInTheDocument();
  expect(option).toBeTruthy();
});

test("product detail keeps the accessible table equivalent to the chart", async () => {
  renderApp(["/products/" + productId]);
  expect(await screen.findByRole("heading", { name: "Historia de precio" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: /Datos de la gráfica/ })).toBeInTheDocument();
  expect(screen.getAllByText("€/kg").length).toBeGreaterThan(0);
});

test("shows a safe 404 state for an unknown ticket", async () => {
  server.use(http.get("http://localhost:8000/api/v1/tickets/unknown", () => HttpResponse.json({ error: { code: "TICKET_NOT_FOUND", message: "Ticket not found", requestId: "req_test" } }, { status: 404 })));
  renderApp(["/tickets/unknown"]);
  expect(await screen.findByRole("alert")).toHaveTextContent("No encontramos este ticket");
  expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
});

test("shows empty product search results", async () => {
  const user = userEvent.setup();
  renderApp(["/products"]);
  await user.type(screen.getByRole("combobox", { name: "Buscar producto" }), "zzz");
  await waitFor(() => expect(screen.getByText("No se encontraron productos")).toBeInTheDocument());
});
