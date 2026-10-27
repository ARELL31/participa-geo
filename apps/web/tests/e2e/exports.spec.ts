import { readFile } from "node:fs/promises";

import { expect, test, type Download, type Page } from "@playwright/test";

/**
 * Real export downloads through the same-origin web proxy. The test creates a
 * persisted scenario through the API first; no report data is mocked.
 */

type ModelRun = { model_run_id: string; family: string };
type Prediction = {
  territory_id: string;
  municipality_code: string;
  municipality_name: string;
  estimated_abstention_pct: number | null;
  eligible: boolean;
};
type ScenarioResult = {
  territory_id: string;
  municipality_code: string;
  baseline_abstention_pct: number | null;
  hypothetical_abstention_pct: number | null;
  effective_reduction_pp: number;
  selected: boolean;
};
type Scenario = { scenario_id: string; results: ScenarioResult[] };

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} should return 200`).toBeTruthy();
  return (await response.json()) as T;
}

function parseCsv(text: string): Array<Record<string, string>> {
  const lines = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"));
  const header = lines.shift();
  if (!header) return [];
  const fields = header.split(",");
  return lines.map((line) => {
    const values = line.split(",");
    return Object.fromEntries(
      fields.map((field, index) => [field, values[index] ?? ""]),
    );
  });
}

async function downloadBytes(
  page: Page,
  buttonName: string,
  timeout = 60_000,
): Promise<{ download: Download; bytes: Buffer; name: string }> {
  const pending = page.waitForEvent("download", { timeout });
  await page.getByRole("button", { name: buttonName }).click();
  const download = await pending;
  const path = await download.path();
  expect(path, "Playwright must persist the downloaded file").toBeTruthy();
  const bytes = await readFile(path!);
  return { download, bytes, name: download.suggestedFilename() };
}

test("exports history, scenario CSV/GeoJSON and real A/B maps", async ({ page }) => {
  const models = await apiJson<{ items: ModelRun[] }>(page, "/api/v1/models");
  const model = models.items[0];
  expect(model, "a published model run must exist").toBeTruthy();

  const predictions = await apiJson<{ items: Prediction[] }>(
    page,
    `/api/v1/predictions?model_run_id=${model!.model_run_id}&page=1&page_size=125`,
  );
  const eligible = predictions.items.find(
    (item) => item.eligible && (item.estimated_abstention_pct ?? 0) >= 3,
  );
  const insufficient = predictions.items.find((item) => !item.eligible);
  expect(eligible, "an eligible municipality with A >= 3 must exist").toBeTruthy();
  expect(insufficient, "the published universe includes insufficient rows").toBeTruthy();

  const createdResponse = await page.request.post("/api/v1/scenarios", {
    data: {
      model_run_id: model!.model_run_id,
      target_year: 2027,
      territory_ids: [eligible!.territory_id],
      reduction_pp: 3,
      assumption_code: "preventive_exploration",
    },
  });
  expect(createdResponse.status()).toBe(201);
  const scenario = (await createdResponse.json()) as Scenario;
  expect(scenario.results).toHaveLength(125);

  // ---- History CSV: values match the API aggregate for the same filter. ----
  const history = await apiJson<{ items: Array<Record<string, unknown>> }>(
    page,
    `/api/v1/participation/history?territory_id=${eligible!.territory_id}&year=2024&page=1&page_size=125`,
  );
  await page.goto(
    `/reports?territory_id=${eligible!.territory_id}&year=2024`,
  );
  expect(
    await page.getByRole("heading", { level: 1, name: "Reportes y exportaciones" }),
  ).toBeVisible();
  const historyDownload = await downloadBytes(page, "Descargar historial CSV");
  const historyRows = parseCsv(historyDownload.bytes.toString("utf8"));
  expect(historyRows.length).toBe(history.items.length);
  const apiHistory = history.items.find((item) => Number(item.year) === 2024);
  const csvHistory = historyRows.find((row) => Number(row.year) === 2024);
  expect(csvHistory, "the CSV must contain the 2024 row").toBeTruthy();
  expect(Number(csvHistory!.abstention_pct)).toBeCloseTo(
    Number(apiHistory!.abstention_pct),
    6,
  );
  expect(csvHistory!.territory_id).toBe(eligible!.territory_id);

  // ---- Scenario CSV: 125 persisted rows, same A/B values as the API. ----
  await page.goto(`/scenarios?scenario_id=${scenario.scenario_id}`);
  expect(
    await page.getByRole("heading", { name: "Resultado persistido" }),
  ).toBeVisible();
  const scenarioDownload = await downloadBytes(page, "Exportar CSV");
  const scenarioRows = parseCsv(scenarioDownload.bytes.toString("utf8"));
  expect(scenarioRows).toHaveLength(125);
  const byId = new Map(scenarioRows.map((row) => [row.territory_id, row]));
  for (const result of [eligible!, insufficient!]) {
    const row = byId.get(result.territory_id);
    const api = scenario.results.find(
      (item) => item.territory_id === result.territory_id,
    );
    expect(row, `missing CSV row for ${result.territory_id}`).toBeTruthy();
    expect(api).toBeTruthy();
    if (api!.baseline_abstention_pct === null) {
      expect(row!.baseline_abstention_pct).toBe("");
      expect(row!.hypothetical_abstention_pct).toBe("");
    } else {
      expect(Number(row!.baseline_abstention_pct)).toBeCloseTo(
        api!.baseline_abstention_pct,
        6,
      );
      expect(Number(row!.hypothetical_abstention_pct)).toBeCloseTo(
        api!.hypothetical_abstention_pct!,
        6,
      );
    }
  }
  expect(
    scenarioRows.find((row) => row.territory_id === eligible!.territory_id)!
      .selected,
  ).toBe("true");

  // ---- GeoJSON: 125 reference geometries in EPSG:4326. ----
  const geojsonDownload = await downloadBytes(page, "Exportar GeoJSON");
  const geojson = JSON.parse(geojsonDownload.bytes.toString("utf8")) as {
    features: Array<{ geometry: { type: string; coordinates: number[][] } }>;
    metadata: { reference_date: string };
  };
  expect(geojson.features).toHaveLength(125);
  expect(geojson.metadata.reference_date).toBe("2025-12-15");
  expect(geojson.features[0]!.geometry.type).toMatch(/Polygon/);

  // ---- PNG and PDF maps are real, non-empty composed files. ----
  const png = await downloadBytes(page, "Mapa PNG");
  expect(png.name.endsWith(".png")).toBeTruthy();
  expect(png.bytes.length).toBeGreaterThan(10_000);
  expect(png.bytes.subarray(0, 8)).toEqual(
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  );

  const mapPdf = await downloadBytes(page, "Mapa PDF");
  expect(mapPdf.name.endsWith(".pdf")).toBeTruthy();
  expect(mapPdf.bytes.length).toBeGreaterThan(10_000);
  expect(mapPdf.bytes.subarray(0, 4).toString()).toBe("%PDF");

  // The API never returns a local filesystem path in artifact metadata.
  const artifact = (await (
    await page.request.post("/api/v1/reports", {
      data: { kind: "scenario_csv", scenario_id: scenario.scenario_id },
    })
  ).json()) as Record<string, unknown>;
  expect(artifact).not.toHaveProperty("path");
  expect(typeof artifact.sha256).toBe("string");
  expect(String(artifact.sha256)).toHaveLength(64);
});
