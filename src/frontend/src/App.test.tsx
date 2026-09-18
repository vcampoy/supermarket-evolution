import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

function renderApp(initialEntries = ["/tickets"]) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={initialEntries}><App /></MemoryRouter></QueryClientProvider>);
}

test("renders Spanish shell and active tickets navigation", () => {
  renderApp();
  expect(screen.getByRole("heading", { name: "Tickets" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Tickets" })).toHaveClass("active");
});

test("mobile menu is keyboard operable and exposes navigation", async () => {
  const user = userEvent.setup();
  renderApp();
  const menu = screen.getByRole("button", { name: /menú/i });
  expect(menu).toHaveAttribute("aria-expanded", "false");
  await user.tab();
  await user.keyboard("{Enter}");
  expect(menu).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("navigation", { name: "Navegación principal" })).toBeVisible();
});
