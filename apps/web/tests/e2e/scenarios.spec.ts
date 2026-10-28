import { expect, test, type Page } from "@playwright/test";

/**
 * These tests hit the real composed stack through the same-origin web proxy.
 * They never mock the API for the happy path; the 422/error cases use request
 * interception only to force an error response the browser must display.
 */

type ModelRun = {
  model_run_id: string;
  family: string;
};

type Prediction = {
  territory_id: string;
  municipality_code: string;
  municipality_name: string;
  estimated_abstention_pct: number | null;
  eligible: boolean;
  risk: string | null;
};

type ScenarioResult = {
  territory_id: string;
  baseline_abstention_pct: number | null;
  hypothetical_abstention_pct: number | null;
  effective_reduction_pp: number;
  selected: boolean;
};

type Scenario = {
  scenario_id: string;
  results: ScenarioResult[];
};

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), `${path} should return 200`).toBeTruthy();
  return (await response.json()) as T;
}

async function forecast(page: Page) {
  const models = await apiJson<{ items: ModelRun[] }>(page, "/api/v1/models");
  const model = models.items[0];
  expect(model, "a published model run must exist").toBeTruthy();
  const predictions = await apiJson<{ items: Prediction[] }>(
    page,
    `/api/v1/predictions?model_run_id=${model!.model_run_id}&state_code=14&page=1&page_size=125`,
  );
  return { model: model!, predictions: predictions.items };
}

function pct(value: number | null): string {
  return value === null ? "Información insuficiente" : `${value.toFixed(1)} %`;
}

test("creates a persisted 3pp scenario with A/B arithmetic and shared maps", async ({
  page,
}) => {
  const { model, predictions } = await forecast(page);
  const eligible = predictions.find(
    (item) => item.eligible && (item.estimated_abstention_pct ?? 0) >= 3,
  );
  const insufficient = predictions.find((item) => !item.eligible);
  expect(eligible, "an eligible municipality with A >= 3 must exist").toBeTruthy();
  expect(insufficient, "the published universe includes insufficient rows").toBeTruthy();

  const historyBefore = await apiJson<{ items: unknown[] }>(
    page,
    `/api/v1/participation/history?territory_id=${eligible!.territory_id}&year=2024&page=1&page_size=125`,
  );

  await page.goto("/scenarios");
  await expect(
    page.getByRole("heading", { level: 1, name: "Escenarios hipotéticos" }),
  ).toBeVisible();
  await expect(
    page.getByText("Escenario hipotético — no implica efecto causal").first(),
  ).toBeVisible();

  await expect(page.getByLabel("Entidad de municipios")).toHaveValue("14");
  const municipalities = page.getByLabel("Municipios", { exact: true });
  await expect(municipalities).toBeVisible();
  await expect(
    municipalities.locator(`option[value="${insufficient!.territory_id}"]`),
  ).toHaveCount(0);

  await municipalities.selectOption([eligible!.territory_id]);
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

  const wfsDone = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/gis/wfs") && response.status() === 200,
  );
  const createResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/scenarios") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Confirmar y crear escenario" })
    .click();

  const created = await createResponse;
  expect(created.status()).toBe(201);
  const scenario = (await created.json()) as Scenario;
  expect(scenario.results).toHaveLength(2477);

  await expect(page).toHaveURL(new RegExp(`scenario_id=${scenario.scenario_id}`));
  await expect(
    page.getByRole("heading", { name: "Resultado persistido" }),
  ).toBeVisible();

  const baseline = eligible!.estimated_abstention_pct!;
  const expectedB = Math.max(0, baseline - 3);
  const table = page.getByRole("table", {
    name: "Comparación A/B por municipio",
  });
  const row = table.getByRole("row", { name: new RegExp(eligible!.municipality_name) });
  await expect(row.locator("td").nth(2)).toHaveText(pct(baseline));
  await expect(row.locator("td").nth(3)).toHaveText(pct(expectedB));
  await expect(row.locator("td").nth(4)).toHaveText(
    `-${(baseline - expectedB).toFixed(1)} pp`,
  );
  await expect(row.locator("td").nth(7)).toHaveText("Seleccionado");

  const insufficientRow = table.getByRole("row", {
    name: new RegExp(insufficient!.municipality_name),
  });
  await expect(insufficientRow.locator("td").nth(2)).toHaveText(
    "Información insuficiente",
  );
  await expect(insufficientRow.locator("td").nth(4)).toHaveText("—");

  const wfsResponse = await wfsDone;
  const wfsBody = (await wfsResponse.json()) as { features: unknown[] };
  expect(wfsBody.features).toHaveLength(125);
  await expect(page.locator(".scenario-map__canvas canvas")).toHaveCount(2, {
    timeout: 20_000,
  });
  await expect(
    page.getByRole("region", { name: "A · Línea base 2027" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "B · Escenario hipotético 2027" }),
  ).toBeVisible();
  await expect(
    page.getByText("Escala compartida A/B — mismos cortes y leyenda"),
  ).toBeVisible();

  // The scenario is persisted, not a client-only result.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Resultado persistido" }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Comparación A/B por municipio" }),
  ).toBeVisible();
  await expect(page.getByText(scenario.scenario_id)).toBeVisible();

  // Historical observation is untouched by the hypothetical scenario.
  const historyAfter = await apiJson<{ items: unknown[] }>(
    page,
    `/api/v1/participation/history?territory_id=${eligible!.territory_id}&year=2024&page=1&page_size=125`,
  );
  expect(historyAfter.items).toEqual(historyBefore.items);

  // The scenario response itself carries the closed request contract.
  const persisted = await apiJson<Scenario>(
    page,
    `/api/v1/scenarios/${scenario.scenario_id}`,
  );
  expect(persisted.scenario_id).toBe(scenario.scenario_id);
  expect(
    persisted.results.find((result) => result.territory_id === eligible!.territory_id)
      ?.selected,
  ).toBe(true);
  expect(
    persisted.results.find((result) => result.territory_id === eligible!.territory_id)
      ?.hypothetical_abstention_pct,
  ).toBeCloseTo(Math.max(0, eligible!.estimated_abstention_pct! - 3), 6);
  expect(model.family).toBe("M0");
});

test("rejects an insufficient municipality with 422 and never offers it in the form", async ({
  page,
}) => {
  const { model, predictions } = await forecast(page);
  const insufficient = predictions.find((item) => !item.eligible);
  expect(insufficient).toBeTruthy();

  await page.goto("/scenarios");
  const municipalities = page.getByLabel("Municipios", { exact: true });
  await expect(
    municipalities.locator(`option[value="${insufficient!.territory_id}"]`),
  ).toHaveCount(0);

  const response = await page.request.post("/api/v1/scenarios", {
    data: {
      model_run_id: model.model_run_id,
      target_year: 2027,
      territory_ids: [insufficient!.territory_id],
      reduction_pp: 3,
      assumption_code: "preventive_exploration",
    },
  });
  expect(response.status()).toBe(422);
  const problem = (await response.json()) as {
    code: string;
    errors: Array<{ reason: string }>;
  };
  expect(problem.code).toBe("validation_error");
  expect(problem.errors.map((error) => error.reason)).toContain(
    "ineligible_territory",
  );
});

test("shows a 422 problem detail and retains the form values", async ({ page }) => {
  const { predictions } = await forecast(page);
  const eligible = predictions.find((item) => item.eligible);
  expect(eligible).toBeTruthy();

  await page.route("**/api/v1/scenarios", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "urn:participa-geo:error:validation_error",
        title: "Validación fallida",
        status: 422,
        detail:
          "La solicitud de escenario no supera la validación. El municipio ya no es elegible.",
        instance: "/api/v1/scenarios",
        code: "validation_error",
        errors: [
          {
            loc: ["body", "territory_ids"],
            msg: "El territorio tiene información insuficiente.",
            reason: "ineligible_territory",
            territory_id: eligible!.territory_id,
          },
        ],
      }),
    }),
  );

  await page.goto("/scenarios");
  const municipalities = page.getByLabel("Municipios", { exact: true });
  await municipalities.selectOption([eligible!.territory_id]);
  const reduction = page.getByLabel(
    "Reducción hipotética (puntos porcentuales)",
  );
  await reduction.fill("3");
  await page.getByLabel("Supuesto").selectOption("model_sensitivity");
  await page.getByRole("button", { name: "Crear escenario" }).click();
  await page
    .getByRole("button", { name: "Confirmar y crear escenario" })
    .click();

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Validación fallida");
  await expect(alert).toContainText(
    "La solicitud de escenario no supera la validación.",
  );
  await expect(municipalities).toHaveValues([eligible!.territory_id]);
  await expect(reduction).toHaveValue("3");
  await expect(page.getByLabel("Supuesto")).toHaveValue("model_sensitivity");
  await expect(
    page.getByRole("heading", { name: "Resultado persistido" }),
  ).toHaveCount(0);
});

test("keeps the A/B table and an explicit error when GIS fails", async ({ page }) => {
  const { model, predictions } = await forecast(page);
  const eligible = predictions.find((item) => item.eligible);
  expect(eligible).toBeTruthy();

  const createdResponse = await page.request.post("/api/v1/scenarios", {
    data: {
      model_run_id: model.model_run_id,
      target_year: 2027,
      territory_ids: [eligible!.territory_id],
      reduction_pp: 3,
      assumption_code: "preventive_exploration",
    },
  });
  expect(createdResponse.status()).toBe(201);
  const created = (await createdResponse.json()) as Scenario;

  let failedWfsUrl = "";
  await page.route("**/api/v1/gis/wfs**", (route) => {
    failedWfsUrl = route.request().url();
    return route.abort();
  });
  await page.goto(`/scenarios?scenario_id=${created.scenario_id}`);

  await expect.poll(() => failedWfsUrl).not.toBe("");
  const wfsUrl = new URL(failedWfsUrl);
  expect(wfsUrl.searchParams.get("typeNames")).toBe("participa_geo_national:municipalities");
  expect(wfsUrl.searchParams.get("state_code")).toBe("14");

  await expect(
    page.getByText(
      "No se pudo cargar la capa cartográfica municipal. La tabla A/B sigue disponible.",
    ),
  ).toBeVisible({ timeout: 20_000 });
  await expect(
    page.getByRole("table", { name: "Comparación A/B por municipio" }),
  ).toBeVisible();
  await expect(page.locator(".scenario-map")).toHaveCount(0);
});
