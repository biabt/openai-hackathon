import { expect, test } from "@playwright/test";

test("portal usa apenas recursos locais durante a demonstração", async ({ page }) => {
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (["http:", "https:", "ws:", "wss:"].includes(url.protocol)
      && !["127.0.0.1", "localhost"].includes(url.hostname)) {
      externalRequests.push(request.url());
    }
  });

  await page.goto("/");
  await expect(page.getByText("Fixture C0 offline")).toBeVisible();
  await page.getByRole("button", { name: "Executar comparação" }).click();
  await expect(page.getByText("33.3% faster")).toBeVisible();
  await expect(page.getByTestId("operational-evidence")).toContainText("Cenários ativos:");
  expect(externalRequests).toEqual([]);
});
