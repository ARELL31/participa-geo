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
