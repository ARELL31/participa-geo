import { readFile } from "node:fs/promises";

import { expect, test, type Download, type Page } from "@playwright/test";

/**
 * End-to-end institutional journey against the real API/PostGIS/GeoServer.
 * Nothing is mocked: the expected values are read from the same API before the
 * UI is exercised, and the downloaded files are compared with the persisted
 * scenario and the historical aggregate.
 */

type ModelRun = {
  model_run_id: string;
  family: string;
  metrics: {
    metrics: { m0: Record<string, { mae: number }> };
    cohorts: Record<string, { eligible_count: number; excluded_count: number }>;
  };
};

type Prediction = {
  territory_id: string;
  municipality_code: string;
  municipality_name: string;
  estimated_abstention_pct: number | null;
  eligible: boolean;
};

type HistoryRow = {
  territory_id: string;
  year: number;
  abstention_pct: number | null;
};

type ScenarioResult = {
  territory_id: string;
  municipality_code: string;
  municipality_name: string;
  baseline_abstention_pct: number | null;
  hypothetical_abstention_pct: number | null;
  effective_reduction_pp: number | null;
  selected: boolean;
};

type Scenario = {
  scenario_id: string;
  model_run_id: string;
  assumption_code: string;
  results: ScenarioResult[];
};

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} should return 200`).toBeTruthy();
  return (await response.json()) as T;
}

/** Small RFC-4180-compatible parser for exported CSV files. */
function parseCsv(text: string): Array<Record<string, string>> {
  const source = text.replace(/^\uFEFF/, "");
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index]!;
    if (quoted) {
      if (char === '"' && source[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  const dataRows = rows.filter(
    (cells) => cells.length > 1 && !cells[0]!.startsWith("#"),
  );
  const header = dataRows.shift();
  if (!header) return [];
  return dataRows.map((cells) =>
    Object.fromEntries(header.map((name, index) => [name, cells[index] ?? ""])),
  );
}

async function download(
  page: Page,
  buttonName: string,
  timeout = 90_000,
): Promise<{ download: Download; bytes: Buffer; name: string }> {
  const pending = page.waitForEvent("download", { timeout });
  await page.getByRole("button", { name: buttonName }).click();
  const file = await pending;
  const path = await file.path();
  expect(path, "Playwright must persist the downloaded file").toBeTruthy();
  return {
    download: file,
    bytes: await readFile(path!),
    name: file.suggestedFilename(),
  };
}

async function forecast(page: Page) {
  const models = await apiJson<{ items: ModelRun[] }>(page, "/api/v1/models");
  const model = models.items[0];
  expect(model, "a published model run must exist").toBeTruthy();
  expect(model!.family).toBe("M0");
  const predictions = await apiJson<{ items: Prediction[] }>(
    page,
    `/api/v1/predictions?model_run_id=${model!.model_run_id}&page=1&page_size=125`,
  );
  const eligible = predictions.items.find(
    (item) => item.eligible && (item.estimated_abstention_pct ?? 0) >= 3,
  );
  const insufficient = predictions.items.find((item) => !item.eligible);
  expect(
    eligible,
    "an eligible municipality with A >= 3 pp must exist",
  ).toBeTruthy();
  expect(
    insufficient,
    "the published universe must include insufficient rows",
  ).toBeTruthy();
  return { model: model!, eligible: eligible!, insufficient: insufficient! };
}

test.skip("Jalisco-only journey superseded by national-acceptance.spec.ts; it asserts the old 125-row MVP artifact/export contract", async ({
  page,
}) => {
  const { model, eligible } = await forecast(page);
  const history = await apiJson<{ items: HistoryRow[] }>(
    page,
    `/api/v1/participation/history?territory_id=${eligible.territory_id}&page=1&page_size=125`,
  );
  const historyBefore = history.items;
  const expected2024 = historyBefore.find((row) => row.year === 2024);
  const expected2021 = historyBefore.find((row) => row.year === 2021);
  expect(expected2024?.abstention_pct).not.toBeNull();
  expect(expected2021?.abstention_pct).not.toBeNull();

  // 1. Municipality + year -> historical series and KPI.
  await page.goto("/territory?year=2024");
  await expect(
    page.getByRole("heading", { level: 1, name: "Inteligencia territorial" }),
  ).toBeVisible();
  const municipality = page.getByLabel("Municipio");
  await expect(municipality).toBeVisible();
  await municipality.selectOption(eligible.territory_id);
  await expect(page).toHaveURL(
    new RegExp(`territory_id=${eligible.territory_id}`),
  );
  await expect(
    page.getByRole("heading", {
      name: `${eligible.municipality_name} · ${eligible.municipality_code}`,
    }),
  ).toBeVisible();
  await expect(page.getByTestId("kpi-abstention")).toHaveText(
    `${expected2024!.abstention_pct!.toFixed(1)} %`,
  );

  await page.getByLabel("Año histórico").selectOption("2021");
  await expect(page).toHaveURL(/year=2021/);
  await expect(page.getByTestId("kpi-abstention")).toHaveText(
    `${expected2021!.abstention_pct!.toFixed(1)} %`,
  );
  const historyTable = page.getByRole("table", {
    name: "Historia de participación por año",
  });
  await expect(
    historyTable.getByRole("row", { name: /2021/ }),
  ).toHaveAttribute("aria-current", "true");

  // 2. Prediction is explicitly separated from observation and carries M0.
  await page.goto(
    `/prediction?territory_id=${eligible.territory_id}&year=2024`,
  );
  await expect(
    page.getByRole("heading", { level: 1, name: "Predicción 2027" }),
  ).toBeVisible();
  await expect(page.getByText("M0 seleccionado")).toBeVisible();
  await expect(page.getByTestId("coverage-eligible")).toHaveText(
    `${model.metrics.cohorts["2027"]!.eligible_count} de 125`,
  );
  await expect(page.getByTestId("coverage-insufficient")).toHaveText(
    String(model.metrics.cohorts["2027"]!.excluded_count),
  );

  // 3. 3 pp hypothetical scenario through the form, with assumptions and A/B.
  await page.goto(
    `/scenarios?territory_id=${eligible.territory_id}&year=2024`,
  );
  await expect(
    page.getByRole("heading", { level: 1, name: "Escenarios hipotéticos" }),
  ).toBeVisible();
  await expect(
    page.getByText("Escenario hipotético — no implica efecto causal").first(),
  ).toBeVisible();
  const municipalities = page.getByLabel("Municipios");
  await expect(municipalities.locator("option")).not.toHaveCount(0);
  await municipalities.selectOption([eligible.territory_id]);
  await page
    .getByLabel("Reducción hipotética (puntos porcentuales)")
    .fill("3");
  await page.getByLabel("Supuesto").selectOption("preventive_exploration");
  await page.getByRole("button", { name: "Crear escenario" }).click();
  await expect(
    page.getByRole("heading", { name: "Confirme el escenario" }),
  ).toBeVisible();
  await expect(page.getByText("Municipios seleccionados: 1")).toBeVisible();
  await expect(page.getByText("Reducción solicitada: 3 pp")).toBeVisible();

  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/scenarios") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Confirmar y crear escenario" })
    .click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const scenario = (await created.json()) as Scenario;
  expect(scenario.results).toHaveLength(125);
  expect(scenario.results.filter((row) => row.selected)).toHaveLength(1);

  await expect(page).toHaveURL(
    new RegExp(`scenario_id=${scenario.scenario_id}`),
  );
  await expect(
    page.getByRole("heading", { name: "Resultado persistido" }),
  ).toBeVisible();

  const baseline = eligible.estimated_abstention_pct!;
  const hypothetical = Math.max(0, baseline - 3);
  const abTable = page.getByRole("table", {
    name: "Comparación A/B por municipio",
  });
  const selectedRow = abTable.getByRole("row", {
    name: new RegExp(eligible.municipality_name),
  });
  await expect(selectedRow.locator("td").nth(2)).toHaveText(
    `${baseline.toFixed(1)} %`,
  );
  await expect(selectedRow.locator("td").nth(3)).toHaveText(
    `${hypothetical.toFixed(1)} %`,
  );
  await expect(selectedRow.locator("td").nth(7)).toHaveText("Seleccionado");
  await expect(
    page.getByText("Escala compartida A/B — mismos cortes y leyenda"),
  ).toBeVisible();
  await expect(page.locator(".scenario-map__canvas canvas")).toHaveCount(2, {
    timeout: 30_000,
  });

  // 4. Persisted scenario CSV matches the API row-by-row.
  const scenarioCsv = await download(page, "Exportar CSV");
  expect(scenarioCsv.name).toMatch(/\.csv$/);
  expect(await scenarioCsv.download.failure()).toBeNull();
  const csvRows = parseCsv(scenarioCsv.bytes.toString("utf8"));
  expect(csvRows).toHaveLength(125);
  expect(csvRows.every((row) => row.scenario_id === scenario.scenario_id)).toBe(
    true,
  );
  const csvSelected = csvRows.find(
    (row) => row.territory_id === eligible.territory_id,
  );
  expect(csvSelected).toBeTruthy();
  expect(csvSelected!.selected).toBe("true");
  expect(Number(csvSelected!.baseline_abstention_pct)).toBeCloseTo(baseline, 6);
  expect(Number(csvSelected!.hypothetical_abstention_pct)).toBeCloseTo(
    hypothetical,
    6,
  );
  const apiSelected = scenario.results.find(
    (row) => row.territory_id === eligible.territory_id,
  )!;
  expect(Number(csvSelected!.effective_reduction_pp)).toBeCloseTo(
    apiSelected.effective_reduction_pp!,
    6,
  );

  // 5. GeoJSON keeps all 125 reference geometries in EPSG:4326.
  const geojsonDownload = await download(page, "Exportar GeoJSON");
  expect(geojsonDownload.name).toMatch(/\.geojson$/);
  const geojson = JSON.parse(geojsonDownload.bytes.toString("utf8")) as {
    features: Array<{
      geometry: { type: string; coordinates: unknown };
      properties: Record<string, unknown>;
    }>;
    metadata: { reference_date: string };
  };
  expect(geojson.features).toHaveLength(125);
  expect(geojson.metadata.reference_date).toBe("2025-12-15");
  expect(geojson.features[0]!.geometry.type).toMatch(/Polygon/);

  // 6. PDF and A/B map PDF are real files, not placeholders.
  const scenarioPdf = await download(page, "Exportar PDF");
  expect(scenarioPdf.name).toMatch(/\.pdf$/);
  expect(scenarioPdf.bytes.subarray(0, 4).toString()).toBe("%PDF");
  expect(scenarioPdf.bytes.length).toBeGreaterThan(10_000);

  const mapPdf = await download(page, "Mapa PDF");
  expect(mapPdf.name).toMatch(/\.pdf$/);
  expect(mapPdf.bytes.subarray(0, 4).toString()).toBe("%PDF");
  expect(mapPdf.bytes.length).toBeGreaterThan(10_000);

  // 7. History CSV/XLSX from the same filters; XLSX is a real workbook.
  await page.goto(
    `/reports?territory_id=${eligible.territory_id}&year=2024`,
  );
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Reportes y exportaciones",
    }),
  ).toBeVisible();
  const historyCsv = await download(page, "Descargar historial CSV");
  expect(historyCsv.name).toMatch(/\.csv$/);
  const historyRows = parseCsv(historyCsv.bytes.toString("utf8"));
  expect(historyRows).toHaveLength(1);
  const csv2024 = historyRows.find((row) => Number(row.year) === 2024);
  expect(csv2024, "the 2024 history row must be exported").toBeTruthy();
  expect(csv2024!.territory_id).toBe(eligible.territory_id);
  expect(Number(csv2024!.abstention_pct)).toBeCloseTo(
    expected2024!.abstention_pct!,
    6,
  );

  const historyXlsx = await download(page, "Descargar historial XLSX");
  expect(historyXlsx.name).toMatch(/\.xlsx$/);
  expect(historyXlsx.bytes.subarray(0, 4).toString("binary")).toBe("PK\u0003\u0004");
  expect(historyXlsx.bytes.length).toBeGreaterThan(5_000);

  // 8. The scenario is persisted and the historical observation is untouched.
  const persisted = await apiJson<Scenario>(
    page,
    `/api/v1/scenarios/${scenario.scenario_id}`,
  );
  expect(persisted.scenario_id).toBe(scenario.scenario_id);
  expect(
    persisted.results.find(
      (row) => row.territory_id === eligible.territory_id,
    )?.selected,
  ).toBe(true);
  const historyAfter = await apiJson<{ items: HistoryRow[] }>(
    page,
    `/api/v1/participation/history?territory_id=${eligible.territory_id}&page=1&page_size=125`,
  );
  expect(historyAfter.items).toEqual(historyBefore);
});

test.skip("Jalisco-only insufficient fixture superseded by national API/unit contracts and national-acceptance.spec.ts", async ({
  page,
}) => {
  const { model, insufficient } = await forecast(page);
  await page.goto("/scenarios");
  await expect(
    page.getByRole("heading", { level: 1, name: "Escenarios hipotéticos" }),
  ).toBeVisible();
  const municipalities = page.getByLabel("Municipios");
  await expect(municipalities).toBeVisible();
  await expect(
    municipalities.locator(`option[value="${insufficient.territory_id}"]`),
  ).toHaveCount(0);

  const rejected = await page.request.post("/api/v1/scenarios", {
    data: {
      model_run_id: model.model_run_id,
      target_year: 2027,
      territory_ids: [insufficient.territory_id],
      reduction_pp: 3,
      assumption_code: "preventive_exploration",
    },
  });
  expect(rejected.status()).toBe(422);
  const problem = (await rejected.json()) as {
    code: string;
    errors: Array<{ reason: string; territory_id?: string }>;
  };
  expect(problem.code).toBe("validation_error");
  expect(problem.errors.map((error) => error.reason)).toContain(
    "ineligible_territory",
  );
  expect(
    problem.errors.some(
      (error) => error.territory_id === insufficient.territory_id,
    ),
  ).toBe(true);
  await expect(
    page.getByRole("heading", { name: "Resultado persistido" }),
  ).toHaveCount(0);
});
