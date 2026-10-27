import { expect, test, type Page } from "@playwright/test";

/**
 * Real-API checks for the explainable prediction and executive summary. The
 * expected numbers are read from the published model and predictions; the UI
 * must not invent evidence.
 */

type ModelRun = {
  model_run_id: string;
  family: string;
  metrics: {
    metrics: {
      m0: Record<string, { mae: number }>;
      m1: Record<string, { mae: number }>;
    };
    band: { amplitude_pp: number };
    cohorts: Record<string, { eligible_count: number; excluded_count: number }>;
  };
};

type Prediction = {
  municipality_code: string;
  municipality_name: string;
  estimated_abstention_pct: number | null;
  eligible: boolean;
  risk: string | null;
};

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} should return 200`).toBeTruthy();
  return (await response.json()) as T;
}

test("prediction page exposes the real M0 evidence, coverage and insufficient rows", async ({
  page,
}) => {
  const models = await apiJson<{ items: ModelRun[] }>(page, "/api/v1/models");
  const model = models.items[0];
  expect(model).toBeTruthy();
  const predictions = await apiJson<{ items: Prediction[] }>(
    page,
    `/api/v1/predictions?model_run_id=${model!.model_run_id}&page=1&page_size=125`,
  );
  const insufficient = predictions.items.find((item) => !item.eligible);
  expect(insufficient).toBeTruthy();

  await page.goto("/prediction");
  await expect(
    page.getByRole("heading", { level: 1, name: "Predicción 2027" }),
  ).toBeVisible();
  await expect(page.getByText("M0 seleccionado")).toBeVisible();
  await expect(
    page.getByTestId("selection-explanation"),
  ).toContainText("M0 fue seleccionado");
  await expect(page.getByTestId("selection-explanation")).toContainText(
    "M1 añade variables sociodemográficas, no fue seleccionado",
  );

  const metrics = page.getByRole("table", {
    name: "Métricas por familia y periodo",
  });
  await expect(metrics.getByRole("row", { name: /^M0/ }).locator("td").nth(2)).toHaveText(
    `${model!.metrics.metrics.m0["2021"]!.mae.toFixed(2)} pp`,
  );
  await expect(metrics.getByRole("row", { name: /^M1/ }).locator("td").nth(2)).toHaveText(
    `${model!.metrics.metrics.m1["2021"]!.mae.toFixed(2)} pp`,
  );

  const cohort = model!.metrics.cohorts["2027"]!;
  await expect(page.getByTestId("coverage-eligible")).toHaveText(
    `${cohort.eligible_count} de 125`,
  );
  await expect(page.getByTestId("coverage-insufficient")).toHaveText(
    String(cohort.excluded_count),
  );
  await expect(page.getByTestId("historical-band")).toHaveText(
    `${model!.metrics.band.amplitude_pp.toFixed(2)} pp`,
  );
  await expect(
    page.getByText("Rango de error histórico de referencia", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/No es un intervalo de confianza del 90 %/),
  ).toBeVisible();

  const table = page.getByRole("table", {
    name: "Predicciones municipales 2027",
  });
  const insufficientRow = table.getByRole("row", {
    name: new RegExp(insufficient!.municipality_name),
  });
  await expect(insufficientRow.locator("td").nth(2)).toHaveText(
    "Información insuficiente",
  );
  await expect(insufficientRow.locator("td").nth(2)).not.toHaveText("0.0 %");
  await expect(insufficientRow.locator(".risk-badge")).toHaveAttribute(
    "data-risk",
    "insufficient",
  );

  await expect(
    page.getByRole("heading", {
      name: "Contribuciones aditivas del candidato M1",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Coeficientes aditivos del candidato M1" }),
  ).toBeVisible();
});

test("executive summary derives coverage and high-risk counts from the API", async ({
  page,
}) => {
  const models = await apiJson<{ items: ModelRun[] }>(page, "/api/v1/models");
  const model = models.items[0];
  const predictions = await apiJson<{ items: Prediction[] }>(
    page,
    `/api/v1/predictions?model_run_id=${model!.model_run_id}&page=1&page_size=125`,
  );
  const highRisk = predictions.items.filter(
    (item) => item.eligible && item.risk === "high",
  ).length;
  const cohort = model!.metrics.cohorts["2027"]!;

  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Panel ejecutivo" }),
  ).toBeVisible();
  await expect(page.getByText(`${cohort.eligible_count} de 125`)).toBeVisible();
  await expect(page.getByTestId("executive-high-risk")).toHaveText(
    String(highRisk),
  );
  await expect(page.getByText("MAE validación 2021")).toBeVisible();
  await expect(page.getByText("MAE prueba 2024")).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Distribución de riesgo predicho 2027" }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", {
      name: "Señales prioritarias de abstención estimada 2027",
    }),
  ).toBeVisible();
});

test("prediction and scenario screens reflow at 320px without page overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });

  for (const path of ["/prediction", "/scenarios"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(width, `${path} must not overflow at 320px`).toBeLessThanOrEqual(320);
  }

  const button = page.getByRole("button", { name: "Crear escenario" });
  const box = await button.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
});
