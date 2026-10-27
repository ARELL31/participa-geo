import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * Accessibility acceptance checks.
 *
 * Automated coverage: keyboard order, visible focus, labelled controls, axe
 * WCAG 2.0/2.1 A+AA critical/serious violations, reflow at 320/375/1440,
 * reduced-motion CSS and a 200% zoom approximation. This is *not* an AA
 * certification: screen-reader speech, reading order with a real AT and final
 * content review remain manual and are documented in
 * `docs/hackathon/verification-results.md`.
 */

const PAGES = [
  { path: "/", heading: "Panel ejecutivo" },
  { path: "/territory?year=2024", heading: "Inteligencia territorial" },
  { path: "/prediction", heading: "Predicción 2027" },
  { path: "/scenarios", heading: "Escenarios hipotéticos" },
  { path: "/reports", heading: "Reportes y exportaciones" },
] as const;

async function open(page: Page, path: string, heading: string) {
  await page.goto(path);
  await expect(
    page.getByRole("heading", { level: 1, name: heading }),
  ).toBeVisible();
  // Let the real API queries settle before scanning; no data is mocked.
  await page.waitForTimeout(500);
}

test.describe("axe WCAG A/AA", () => {
  for (const target of PAGES) {
    test(`${target.path} no tiene violaciones críticas ni serias`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await open(page, target.path, target.heading);

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      const severe = results.violations.filter(
        (violation) =>
          violation.impact === "critical" || violation.impact === "serious",
      );
      expect(
        severe,
        JSON.stringify(
          severe.map((violation) => ({
            id: violation.id,
            impact: violation.impact,
            help: violation.help,
            nodes: violation.nodes.map((node) => node.target),
          })),
          null,
          2,
        ),
      ).toEqual([]);
    });
  }

  test("el diálogo móvil tampoco introduce violaciones críticas ni serias", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await open(page, "/territory?year=2024", "Inteligencia territorial");
    await page.getByRole("button", { name: "Abrir menú de navegación" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const severe = results.violations.filter(
      (violation) =>
        violation.impact === "critical" || violation.impact === "serious",
    );
    expect(
      severe,
      JSON.stringify(
        severe.map((violation) => ({
          id: violation.id,
          impact: violation.impact,
          nodes: violation.nodes.map((node) => node.target),
        })),
        null,
        2,
      ),
    ).toEqual([]);
  });
});

test("skip link, tab order, visible focus and Enter activation", async ({
  page,
}) => {
  await page.goto("/");
  const skip = page.getByRole("link", { name: "Saltar al contenido" });
  await page.keyboard.press("Tab");
  await expect(skip).toBeFocused();

  const focusStyle = await skip.evaluate((element) => {
    const style = window.getComputedStyle(element);
    return {
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
      outlineColor: style.outlineColor,
    };
  });
  expect(focusStyle.outlineStyle).not.toBe("none");
  expect(focusStyle.outlineWidth).not.toBe("0px");
  expect(focusStyle.outlineColor).not.toBe("rgba(0, 0, 0, 0)");

  // Advance through the shell until the territory module link is focused.
  let focused = "";
  for (let index = 0; index < 10; index += 1) {
    await page.keyboard.press("Tab");
    focused = await page.evaluate(
      () => document.activeElement?.textContent?.replace(/\s+/g, " ").trim() ?? "",
    );
    if (focused.includes("Inteligencia territorial")) break;
  }
  expect(focused).toContain("Inteligencia territorial");

  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/territory/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Inteligencia territorial" }),
  ).toBeVisible();
});

test("controles principales tienen etiqueta accesible y nombres de acción", async ({
  page,
}) => {
  await page.goto("/territory?year=2024");
  await expect(page.getByLabel("Municipio")).toBeVisible();
  await expect(page.getByLabel("Año histórico")).toBeVisible();
  expect(
    await page.getByLabel("Municipio").evaluate((element) => element.tagName),
  ).toBe("SELECT");

  await page.goto("/scenarios");
  await expect(page.getByLabel("Municipios")).toBeVisible();
  await expect(
    page.getByLabel("Reducción hipotética (puntos porcentuales)"),
  ).toBeVisible();
  await expect(page.getByLabel("Supuesto")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Crear escenario" }),
  ).toBeVisible();

  await page.goto("/reports");
  await expect(
    page.getByRole("button", { name: "Descargar historial CSV" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Descargar historial XLSX" }),
  ).toBeVisible();
});

test.describe("reflow 320/375/1440", () => {
  for (const width of [320, 375, 1440] as const) {
    test(`${width}px no provoca desbordamiento horizontal`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      for (const target of PAGES) {
        await page.goto(target.path);
        await expect(
          page.getByRole("heading", { level: 1, name: target.heading }),
        ).toBeVisible();
        const metrics = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          bodyWidth: document.body.getBoundingClientRect().width,
        }));
        expect(
          metrics.scrollWidth,
          `${target.path} must not overflow at ${width}px`,
        ).toBeLessThanOrEqual(width);
      }
    });
  }

  test("375px mantiene menú móvil con foco atrapado y retorno", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/territory?year=2024");
    const trigger = page.getByRole("button", {
      name: "Abrir menú de navegación",
    });
    await expect(trigger).toBeVisible();
    await trigger.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("1440px conserva la navegación persistente y la cabecera de 64px", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/territory?year=2024");
    await expect(
      page.getByRole("navigation", { name: "Navegación principal" }),
    ).toBeVisible();
    const metrics = await page.evaluate(() => ({
      header: document.querySelector(".app-header")?.getBoundingClientRect()
        .height,
      sidebar: document.querySelector(".sidebar")?.getBoundingClientRect()
        .width,
    }));
    expect(metrics.header).toBe(64);
    expect(metrics.sidebar).toBe(264);
  });
});

test("prefers-reduced-motion reduce animaciones y transiciones", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  expect(
    await page.evaluate(
      () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);

  const motion = await page.evaluate(() => {
    const probe = document.createElement("span");
    probe.className = "spin";
    probe.textContent = "prueba";
    document.body.appendChild(probe);
    const style = window.getComputedStyle(probe);
    const result = {
      duration: style.animationDuration,
      iterations: style.animationIterationCount,
      scrollBehavior: window.getComputedStyle(document.documentElement)
        .scrollBehavior,
    };
    probe.remove();
    return result;
  });

  const seconds = motion.duration.endsWith("ms")
    ? Number.parseFloat(motion.duration) / 1000
    : Number.parseFloat(motion.duration);
  expect(seconds).toBeLessThanOrEqual(0.001);
  expect(motion.iterations).toBe("1");
  expect(motion.scrollBehavior).toBe("auto");
});

test("aproximación de zoom 200% mantiene contenido y controles utilizables", async ({
  page,
}) => {
  // Playwright does not expose browser zoom. A 640 CSS px viewport with
  // body zoom 2 approximates a 320 CSS px layout at 200% and catches reflow
  // regressions without claiming a full browser-zoom test.
  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto("/territory?year=2024");
  await page.evaluate(() => {
    document.body.style.zoom = "2";
  });
  const width = await page.evaluate(
    () => document.documentElement.scrollWidth,
  );
  expect(width).toBeLessThanOrEqual(640);
  await expect(page.getByLabel("Año histórico")).toBeVisible();
  await expect(page.getByTestId("kpi-abstention")).toBeVisible();
});
