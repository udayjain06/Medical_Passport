import { expect, test } from "@playwright/test";

test("Explore Demo is frontend-only and interactive", async ({ page }) => {
  const apiCalls: string[] = [];
  const browserErrors: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiCalls.push(request.url());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });

  await page.goto("/login");
  await expect(page.getByRole("link", { name: "Explore Demo →" })).toHaveAttribute("href", "/demo");
  await page.goto("/signup");
  await expect(page.getByRole("link", { name: "Explore Demo →" })).toHaveAttribute("href", "/demo");

  await page.goto("/");
  await page.getByRole("link", { name: "Explore Demo →" }).click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.getByRole("heading", { name: "Welcome, Aarav Mehta" })).toBeVisible();

  await page.getByRole("button", { name: "Documents & OCR" }).click();
  await page.getByRole("button", { name: "Preview sample" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Patient-reported seasonal allergy symptoms", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Close preview" }).click();

  await page.getByRole("button", { name: "Patient profile" }).click();
  await page.getByLabel("Full name").fill("Aarav Sample");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("heading", { name: "Welcome, Aarav Sample" })).toBeVisible();

  await page.getByRole("button", { name: "Documents & OCR" }).click();
  await page.getByRole("button", { name: "Accept sample fact" }).click();
  await page.getByRole("button", { name: "Medical timeline" }).click();
  await expect(page.getByText(/Accepted in this browser session/)).toBeVisible();

  await page.getByRole("button", { name: "Family profiles" }).click();
  await page.getByRole("button", { name: "Switch to Ira's profile" }).click();
  await expect(page.getByRole("heading", { name: "Welcome, Ira Mehta" })).toBeVisible();
  await page.getByRole("button", { name: "Documents & OCR" }).click();
  await expect(page.getByRole("heading", { name: /Documents & extraction review · Ira Mehta/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Paediatric consultation/ })).toBeVisible();
  await expect(page.getByText("Salbutamol inhaler · sample prescription")).toBeVisible();
  await page.getByRole("button", { name: "Accept sample fact" }).click();
  await page.getByRole("button", { name: "Medical timeline" }).click();
  await expect(page.getByText(/Salbutamol inhaler.*Accepted in this browser session/)).toBeVisible();
  await page.getByRole("button", { name: "Family profiles" }).click();
  await page.getByRole("button", { name: "Return to Aarav" }).click();
  await expect(page.getByRole("heading", { name: "Welcome, Aarav Sample" })).toBeVisible();
  await page.getByRole("button", { name: "Medical timeline" }).click();
  await expect(page.getByText(/Cetirizine 10 mg.*Accepted in this browser session/)).toBeVisible();
  await expect(page.getByText(/Salbutamol inhaler.*Accepted in this browser session/)).toHaveCount(0);

  await page.getByRole("button", { name: "Emergency QR" }).click();
  await page.getByLabel("Blood group").uncheck();
  await page.getByLabel("Emergency contact").check();
  await page.getByRole("button", { name: "Show QR preview" }).click();
  await expect(page.getByRole("img", { name: "Illustrative QR preview" })).toBeVisible();
  const previewFacts = page.locator(".demo-qr-wrap ul");
  await expect(previewFacts).toContainText("Aarav Sample");
  await expect(previewFacts).toContainText("Riya Mehta · fictional contact");
  await expect(previewFacts).not.toContainText("Blood group");
  expect(apiCalls).toEqual([]);
  expect(browserErrors).toEqual([]);
});

test("Explore Demo stays usable on tablet and mobile viewports", async ({ page }) => {
  await page.goto("/demo");
  for (const width of [700, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByRole("navigation", { name: "Demo sections" })).toBeVisible();
    await page.getByRole("button", { name: "Emergency QR" }).click();
    await page.getByRole("button", { name: "Show QR preview" }).click();
    await expect(page.getByRole("img", { name: "Illustrative QR preview" })).toBeVisible();
    await expect(page.locator(".demo-footer")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();
    await page.getByRole("button", { name: "Overview" }).click();
  }
});
