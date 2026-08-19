import { expect, test } from "@playwright/test";

test("executa a comparação pareada de enchente com frota 120", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "City OS" })).toBeVisible();

  await page.getByRole("button", { name: /Alagamento/ }).first().click();
  const fleet = page.getByLabel("Tamanho da frota");
  await fleet.fill("120");
  await expect(page.getByText("120 ambulâncias")).toBeVisible();
  await page.getByRole("button", { name: "Executar comparação" }).click();

  await expect(page.getByText("Antes · política estática · P90").locator("..").getByText("21.0 min")).toBeVisible();
  await expect(page.getByText("Depois · política preditiva · P90").locator("..").getByText("14.0 min")).toBeVisible();
  await expect(page.getByText("33.3% faster")).toBeVisible();
  await expect(page.getByTestId("operational-evidence")).toContainText("flood-aricanduva-1730");
  await expect(page.getByText(/de 06:00/)).toBeVisible();
});
