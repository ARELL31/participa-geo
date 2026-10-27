import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../app/App";
import {
  emptyWfsHandler,
  historyHandler,
  historyYear,
  TERRITORY_A,
  territoriesHandler,
  territory,
} from "../test/fixtures";
import { server } from "../test/server";

function renderApp(path = "/") {
  window.history.replaceState({}, "", path);
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("ApplicationShell", () => {
  it("exposes the five routes with the correct accessible landmarks", () => {
    renderApp("/");
    expect(
      screen.getByRole("navigation", { name: "Navegación principal" }),
    ).toBeInTheDocument();
    for (const [name, href] of [
      ["Panel ejecutivo", "/"],
      ["Inteligencia territorial", "/territory"],
      ["Predicción", "/prediction"],
      ["Escenarios", "/scenarios"],
      ["Reportes", "/reports"],
    ] as const) {
      expect(
        screen.getByRole("link", { name: new RegExp(`^${name}`) }),
      ).toHaveAttribute("href", href);
    }
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("starts keyboard navigation on the skip link and navigates with Enter", async () => {
    server.use(
      territoriesHandler([territory(TERRITORY_A, "001", "ACATIC")]),
      historyHandler(() => [historyYear(null, 2024)]),
      emptyWfsHandler(),
    );
    const user = userEvent.setup();
    renderApp("/");
    const skipLink = screen.getByRole("link", { name: "Saltar al contenido" });
    await user.tab();
    expect(skipLink).toHaveFocus();
    expect(skipLink).toHaveAttribute("href", "#contenido");

    const territoryLink = screen.getByRole("link", {
      name: /^Inteligencia territorial/,
    });
    territoryLink.focus();
    expect(territoryLink).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Inteligencia territorial",
      }),
    ).toBeInTheDocument();
  });

  it("marks reports pending without fake actions", async () => {
    const user = userEvent.setup();
    renderApp("/");
    expect(
      screen.getByRole("link", { name: /^Predicción/ }),
    ).not.toHaveAccessibleName(/Pendiente/);
    expect(
      screen.getByRole("link", { name: /^Escenarios/ }),
    ).not.toHaveAccessibleName(/Pendiente/);

    const reportsLink = screen.getByRole("link", { name: /^Reportes/ });
    expect(reportsLink).toHaveAccessibleName(/Pendiente/);
    await user.click(reportsLink);
    const main = screen.getByRole("main");
    expect(within(main).getByText("Pendiente")).toBeInTheDocument();
    expect(
      within(main).getByRole("heading", {
        level: 1,
        name: "Reportes y exportaciones",
      }),
    ).toBeInTheDocument();
    expect(within(main).queryAllByRole("button")).toHaveLength(0);
    expect(within(main).queryAllByRole("link")).toHaveLength(0);
  });

  it("opens the mobile sidebar as a dialog and returns focus on Escape", async () => {
    const user = userEvent.setup();
    renderApp("/");
    const trigger = screen.getByRole("button", {
      name: "Abrir menú de navegación",
    });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("navigation", { name: "Navegación principal" }),
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("catches an invalid historical year and offers to reset filters", async () => {
    server.use(
      territoriesHandler([territory(TERRITORY_A, "001", "ACATIC")]),
      historyHandler(() => [historyYear(TERRITORY_A, 2024)]),
      emptyWfsHandler(),
    );
    const user = userEvent.setup();
    renderApp("/territory?year=2023");
    expect(
      screen.getByRole("heading", { level: 1, name: "Filtros no válidos" }),
    ).toBeInTheDocument();
    const reset = screen.getByRole("button", { name: "Restablecer filtros" });
    await user.click(reset);
    await waitFor(() =>
      expect(window.location.search).not.toContain("year=2023"),
    );
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Inteligencia territorial",
      }),
    ).toBeInTheDocument();
  });
});
