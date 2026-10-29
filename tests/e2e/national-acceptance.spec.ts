import { expect, test } from "@playwright/test";

type Page<T> = { items: T[]; total: number; page_size: number };
type Territory = {
  id: string;
  name: string;
  level: "municipality" | "federal_district";
  district_plan: string | null;
};

test("national coverage, district observed-only contract, and bounded WFS", async ({
  page,
}) => {
  const summaryResponse = await page.request.get(
    "/api/v1/participation/summary?level=municipality&year=2024",
  );
  expect(summaryResponse.status()).toBe(200);
  const summary = await summaryResponse.json();
  expect(summary).toHaveLength(32);

  const municipalitiesResponse = await page.request.get(
    "/api/v1/territories?level=municipality&state_code=all&page=1&page_size=500",
  );
  expect(municipalitiesResponse.status()).toBe(200);
  const municipalities = (await municipalitiesResponse.json()) as Page<Territory>;
  expect(municipalities.total).toBe(2477);
  expect(municipalities.items).toHaveLength(500);

  const districtsResponse = await page.request.get(
    "/api/v1/territories?level=federal_district&state_code=14&page=1&page_size=500",
  );
  expect(districtsResponse.status()).toBe(200);
  const districts = (await districtsResponse.json()) as Page<Territory>;
  expect(districts.total).toBeGreaterThan(0);
  const district = districts.items[0]!;
  expect(district.level).toBe("federal_district");
  expect(district.district_plan).toBe("DERFE2023");

  const observed = await page.request.get(
    `/api/v1/participation/history?level=federal_district&territory_id=${district.id}&page=1&page_size=500`,
  );
  expect(observed.status()).toBe(200);
  const history = await observed.json();
  expect(history.items.map((row: { year: number }) => row.year)).toEqual([2024]);
  expect(history.items[0]).not.toHaveProperty("prediction");
  expect(history.items[0]).not.toHaveProperty("lower_bound");

  const prediction = await page.request.get(
    `/api/v1/predictions?level=federal_district&territory_id=${district.id}`,
  );
  expect(prediction.status()).toBe(409);
  expect((await prediction.json()).code).toBe("district_model_unavailable");

  const scenario = await page.request.post("/api/v1/scenarios", {
    data: {
      model_run_id: "00000000-0000-4000-8000-000000000001",
      level: "federal_district",
      target_year: 2027,
      territory_ids: [district.id],
      reduction_pp: 3,
      assumption_code: "preventive_exploration",
    },
  });
  expect(scenario.status()).toBe(409);

  const fullCountryWfs = await page.request.get(
    "/api/v1/gis/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=participa_geo:municipality",
  );
  expect(fullCountryWfs.status()).toBe(422);

  await page.goto("/?level=municipality&state=14");
  await expect(page.getByLabel("Nivel territorial")).toHaveValue("municipality");
  await page.getByLabel("Nivel territorial").selectOption("federal_district");
  await expect(page).toHaveURL(/level=federal_district/);
  await expect(page.getByLabel("Nivel territorial")).toHaveValue(
    "federal_district",
  );
  await expect(
    page.getByText(/Distrito federal · Observado 2024 · Sin modelo 2027/),
  ).toBeVisible();
});

test("municipal observations are state-scoped and paginated; map follows the selected entity", async ({ page }) => {
  for (const [stateCode, count] of [["14", 125], ["19", 51], ["20", 570]] as const) {
    const observationsResponse = await page.request.get(`/api/v1/participation/municipal-observations?state_code=${stateCode}&year=2024&page_size=500`);
    expect(observationsResponse.status()).toBe(200);
    const observations = await observationsResponse.json();
    expect(observations.total).toBe(count);
    expect(observations.items).toHaveLength(Math.min(count, 500));
    expect(observations.items.every((item: { state_code: string }) => item.state_code === stateCode)).toBe(true);
    const geometryResponse = await page.request.get(`/api/v1/gis/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=participa_geo_national:municipalities&outputFormat=application/json&srsName=EPSG:4326&count=1000&level=municipality&state_code=${stateCode}`);
    expect(geometryResponse.status()).toBe(200);
    const geometry = await geometryResponse.json();
    expect(geometry.features).toHaveLength(count);
  }
  await page.goto("/territory?state=20&year=2024");
  await expect(page.getByRole("heading", { name: "Mapa de abstención municipal" })).toBeVisible();
  const canvas = page.locator(".map-canvas");
  await expect(canvas).toHaveAttribute("aria-label", /entidad 20, año 2024/);
  await expect(page.getByText(/Oaxaca · año 2024/i)).toBeVisible();
  await expect(canvas.locator("canvas")).toBeVisible();
  await expect(page.getByText("Cargando mapa…")).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByText("Cargando historia territorial")).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByTestId("kpi-abstention")).not.toHaveText("Cargando…");

  for (const [code, name] of [["14", "Jalisco"], ["19", "Nuevo León"], ["20", "Oaxaca"]] as const) {
    await page.getByLabel("Entidad", { exact: true }).selectOption(code);
    await expect(page).toHaveURL(new RegExp(`state=${code}`));
    await expect(canvas).toHaveAttribute("aria-label", new RegExp(`entidad ${code}, año 2024`));
    await expect.poll(async () => (await page.locator(".map-card .card-heading").innerText()).normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase()).toContain(name.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase());
    await expect(canvas.locator("canvas")).toBeVisible();
    await expect(page.getByText("Cargando mapa…")).toHaveCount(0, { timeout: 30_000 });
    await expect(page.getByText("Cargando historia territorial")).toHaveCount(0, { timeout: 60_000 });
    await expect(page.getByTestId("kpi-abstention")).not.toHaveText("Cargando…");
    await expect(page.locator(".map-frame #map-description")).toHaveCount(0);
    const geometry = await page.request.get(`/api/v1/gis/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=participa_geo_national:municipalities&outputFormat=application/json&srsName=EPSG:4326&count=1000&level=municipality&state_code=${code}`);
    expect(geometry.status()).toBe(200);
    const result = await geometry.json();
    expect(result.features).toHaveLength(code === "14" ? 125 : code === "19" ? 51 : 570);
    expect(result.features.every((feature: { properties: { state_code: string } }) => feature.properties.state_code === code)).toBe(true);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: `/tmp/opencode/municipal-map-${code}-1440.png`, fullPage: true });
    if (code === "19") {
      await page.setViewportSize({ width: 375, height: 812 });
      await expect(canvas.locator("canvas")).toBeVisible();
      await expect(page.getByText("Cargando historia territorial")).toHaveCount(0, { timeout: 60_000 });
      await page.screenshot({ path: "/tmp/opencode/municipal-map-19-375.png", fullPage: true });
    }
  }
  const observationsPage2 = await page.request.get("/api/v1/participation/municipal-observations?state_code=20&year=2024&page=2&page_size=500");
  expect(observationsPage2.status()).toBe(200);
  expect((await observationsPage2.json()).items).toHaveLength(70);
  const catalogPage1 = await page.request.get("/api/v1/territories?state_code=20&level=municipality&page=1&page_size=500");
  const catalogPage2 = await page.request.get("/api/v1/territories?state_code=20&level=municipality&page=2&page_size=500");
  expect((await catalogPage1.json()).total).toBe(570);
  const lastCatalogPage = await catalogPage2.json();
  expect(lastCatalogPage.items).toHaveLength(70);
  expect(lastCatalogPage.items.at(-1)).toMatchObject({ municipality_code: "570", name: "ZIMATLAN DE ALVAREZ" });
  await page.goto("/territory?state=20&year=2024");
  const lastMunicipality = page.getByLabel("Municipio", { exact: true });
  await expect(lastMunicipality.locator("option").filter({ hasText: "570 · ZIMATLAN DE ALVAREZ" })).toHaveCount(1, { timeout: 60_000 });
  await lastMunicipality.selectOption({ label: "570 · ZIMATLAN DE ALVAREZ" });
  await expect(page.getByText("Cargando historia territorial")).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByRole("heading", { name: /ZIMATLAN DE ALVAREZ/ })).toBeVisible();
  await expect(page.getByText("Cargando año seleccionado…")).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByTestId("kpi-abstention")).not.toHaveText("Cargando…");
  await page.screenshot({ path: "/tmp/opencode/municipal-map-20-1440.png", fullPage: true });
  await page.goto("/");
  await expect(page.locator(".map-canvas")).toHaveCount(0);
});
