import { expect, test, type Page } from "@playwright/test";

/**
 * These tests run against the real compose stack through the same-origin web
 * proxy. MSW is never used here: the expected values are fetched from the API
 * and compared with what the page displays.
 */

const NOTICE =
  "Referencia cartográfica INE: 15 de diciembre de 2025. No implica igualdad de límites históricos.";

type Territory = { id: string; name: string; municipality_code: string };
type History = { year: number; abstention_pct: number | null };

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} should return 200`).toBeTruthy();
  return (await response.json()) as T;
}

async function acaticHistory(page: Page) {
  const territories = await apiJson<{ items: Territory[] }>(
    page,
    "/api/v1/territories?state_code=14&level=municipality&page=1&page_size=125",
  );
  const acatic = territories.items.find((item) => item.name === "ACATIC");
  expect(acatic, "ACATIC must exist in the reference catalogue").toBeTruthy();
  const history = await apiJson<{ items: History[] }>(
    page,
    `/api/v1/participation/history?territory_id=${acatic!.id}&page=1&page_size=125`,
  );
  return { acatic: acatic!, history: history.items };
}

function rate(value: number | null): string {
  return value === null ? "No disponible" : `${value.toFixed(1)} %`;
}

test("territory selection and year update the KPI and the accessible table", async ({
  page,
}) => {
  const { acatic, history } = await acaticHistory(page);
  const expected2024 = history.find((row) => row.year === 2024)?.abstention_pct;
  expect(expected2024).not.toBeNull();

  await page.goto("/territory?year=2024");
  await expect(page.getByRole("heading", { level: 1, name: "Inteligencia territorial" })).toBeVisible();
  await expect(page.getByText(NOTICE)).toBeVisible();

  await page.getByLabel("Municipio").selectOption(acatic.id);
  await expect(page).toHaveURL(new RegExp(`territory_id=${acatic.id}`));
  await expect(page).toHaveURL(/year=2024/);
  await expect(page.getByRole("heading", { name: `${acatic.name} · ${acatic.municipality_code}` })).toBeVisible();
  await expect(page.getByTestId("kpi-abstention")).toHaveText(rate(expected2024 ?? null));

  const historyTable = page.getByRole("table", {
    name: "Historia de participación por año",
  });
  const row2024 = historyTable.getByRole("row", { name: /2024/ });
  await expect(row2024.locator("td").nth(2)).toHaveText(rate(expected2024 ?? null));

  const expected2021 = history.find((row) => row.year === 2021)?.abstention_pct;
  await page.getByLabel("Año histórico").selectOption("2021");
  await expect(page).toHaveURL(/year=2021/);
  await expect(page.getByTestId("kpi-abstention")).toHaveText(rate(expected2021 ?? null));

  const row2021 = historyTable.getByRole("row", { name: /2021/ });
  await expect(row2021).toHaveAttribute("aria-current", "true");
  await expect(row2021.locator("td").nth(2)).toHaveText(rate(expected2021 ?? null));
});

test("history year contract accepts approved years and rejects 2023", async ({
  page,
}) => {
  const accepted = await page.request.get(
    "/api/v1/participation/history?year=2024&page=1&page_size=1",
  );
  expect(accepted.status()).toBe(200);
  const acceptedBody = (await accepted.json()) as {
    items: Array<{ year: number }>;
  };
  expect(acceptedBody.items[0]?.year).toBe(2024);

  const rejected = await page.request.get(
    "/api/v1/participation/history?year=2023&page=1&page_size=1",
  );
  expect(rejected.status()).toBe(422);
  const rejectedBody = (await rejected.json()) as { code: string };
  expect(rejectedBody.code).toBe("validation_error");
});

test("keyboard navigation reaches the module link and activates it with Enter", async ({
  page,
}) => {
  await page.goto("/");
  const predictionLink = page.getByRole("link", { name: /Predicción/ });
  await expect(predictionLink).toBeVisible();
  await expect(predictionLink).toHaveAccessibleName(/Pendiente/);
  const skip = page.getByRole("link", { name: "Saltar al contenido" });
  await page.keyboard.press("Tab");
  await expect(skip).toBeFocused();

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  const focusedText = await page.evaluate(
    () => document.activeElement?.textContent ?? "",
  );
  expect(focusedText).toContain("Inteligencia territorial");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/territory/);
  await expect(page.getByRole("heading", { level: 1, name: "Inteligencia territorial" })).toBeVisible();
});

test("MapLibre renders the WMS map and loads all WFS municipalities", async ({
  page,
}) => {
  const wfsDone = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/gis/wfs") && response.status() === 200,
  );
  const wmsDone = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/gis/wms") && response.status() === 200,
  );
  await page.goto("/territory?year=2024");

  const wfsResponse = await wfsDone;
  const wfsBody = (await wfsResponse.json()) as { features: unknown[] };
  expect(wfsBody.features).toHaveLength(125);
  const wmsResponse = await wmsDone;
  expect(wmsResponse.headers()["content-type"]).toContain("image/png");

  await expect(page.locator(".map-canvas canvas")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Cargando mapa…")).toBeHidden();
  await expect(
    page.getByText(
      "No se pudo mostrar el mapa. La tabla de municipios sigue disponible.",
    ),
  ).toBeHidden();
});

test("the mobile sidebar opens as a dialog at 375px and returns focus", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/territory?year=2024");

  const trigger = page.getByRole("button", { name: "Abrir menú de navegación" });
  await expect(trigger).toBeVisible();
  await trigger.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("navigation", { name: "Navegación principal" }),
  ).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("1440px keeps the persistent sidebar and the 64px header", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/territory?year=2024");
  await expect(
    page.getByRole("navigation", { name: "Navegación principal" }),
  ).toBeVisible();
  const metrics = await page.evaluate(() => ({
    header: document.querySelector(".app-header")?.getBoundingClientRect().height,
    sidebar: document.querySelector(".sidebar")?.getBoundingClientRect().width,
  }));
  expect(metrics.header).toBe(64);
  expect(metrics.sidebar).toBe(264);
});

test("320px layout reflows without horizontal page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/territory?year=2024");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(320);
});

test("200% zoom approximation keeps the page usable without page overflow", async ({
  page,
}) => {
  // Browser zoom is not exposed by Playwright; 640 CSS px with body zoom 2
  // approximates a 320 CSS px layout at 200%, catching reflow regressions.
  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto("/territory?year=2024");
  await page.evaluate(() => {
    document.body.style.zoom = "2";
  });

  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(640);
  await expect(page.getByLabel("Año histórico")).toBeVisible();
});

test("a failed WMS keeps the map error and the tabular alternative", async ({
  page,
}) => {
  await page.route("**/api/v1/gis/wms**", (route) => route.abort());
  await page.goto("/territory?year=2024");

  await expect(
    page.getByText(
      "No se pudo mostrar el mapa. La tabla de municipios sigue disponible.",
    ),
  ).toBeVisible({ timeout: 20_000 });
  await expect(
    page.getByRole("table", { name: "Municipios de Jalisco" }),
  ).toBeVisible();
});
