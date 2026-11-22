import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("Explore Demo opens a persistent, usable synthetic Medical Passport", async ({ page, browser }) => {
  test.setTimeout(120000);
  test.skip(process.env.PLAYWRIGHT_DEMO !== "1", "Run with PLAYWRIGHT_DEMO=1 after starting and seeding the local demo.");

  const fixturePath = process.env.DEMO_E2E_PDF;
  expect(fixturePath, "DEMO_E2E_PDF must point to the deterministic synthetic PDF fixture").toBeTruthy();
  const fixture = await readFile(fixturePath!);

  await page.goto("/signup");
  await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Want to explore before creating an account?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Explore Demo →" })).toBeVisible();

  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Explore Demo →" })).toBeVisible();
  await page.getByRole("button", { name: "Explore Demo →" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Welcome, Aarav Mehta" })).toBeVisible();
  await expect(page.getByText(/DEMO MODE — SYNTHETIC DATA/)).toBeVisible();

  await page.goto("/profile");
  await expect(page.getByLabel("Full name")).toHaveValue("Aarav Mehta");
  await expect(page.getByLabel("Date of birth")).toHaveValue("2001-08-14");
  await expect(page.getByLabel("Blood group")).toHaveValue("O+");
  await expect(page.getByLabel("Known allergies")).toHaveValue(/Pollen/);
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.locator(".form-success")).toHaveText("Profile saved.");
  await page.reload();
  await expect(page.getByLabel("Full name")).toHaveValue("Aarav Mehta");

  await page.goto("/documents");
  await expect(
    page.locator(".document-card").filter({ hasText: "demo-cbc-report.pdf" }).first(),
  ).toBeVisible();
  const documentName = "demo-e2e-upload.pdf";
  let documentCard = page.locator(".document-card").filter({ hasText: documentName });
  if (await documentCard.count() === 0) {
    const uploadResponse = page.waitForResponse((response) =>
      response.url().includes("/api/documents") && response.request().method() === "POST",
    );
    await page.locator('input[type="file"]').setInputFiles({
      name: documentName,
      mimeType: "application/pdf",
      buffer: fixture,
    });
    expect((await uploadResponse).status()).toBe(201);
    documentCard = page.locator(".document-card").filter({ hasText: documentName });
  }
  await expect(documentCard.first()).toBeVisible();
  await documentCard.first().getByRole("button", { name: "Details" }).click();
  await expect(page.getByTitle(`Preview ${documentName}`)).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  const prescription = page.locator(".document-card").filter({ hasText: "demo-historical-prescription.pdf" });
  const extractionResponse = page.waitForResponse((response) =>
    response.url().includes("/api/documents/")
      && response.url().endsWith("/extraction")
      && response.request().method() === "GET",
  );
  await prescription.getByRole("button", { name: "Details" }).click();
  const review = page.locator(".review-box");
  await expect(review.locator(".demo-extraction-note")).toBeVisible();
  const extraction = await (await extractionResponse).json() as {
    status: string;
    demo_simulation: boolean;
  };
  expect(extraction.demo_simulation).toBe(true);
  if (extraction.status === "needs_review") {
    const medication = review.locator(".candidate").filter({ has: page.getByLabel("Medication text") });
    await medication.getByRole("button", { name: "Accept", exact: true }).click();
    const patientName = review.locator(".candidate").filter({ has: page.getByLabel("Patient name text") });
    await patientName.getByRole("button", { name: "Reject", exact: true }).click();
    const confirm = review.getByRole("button", { name: "Add 1 accepted to timeline" });
    await expect(confirm).toBeEnabled();
    const confirmResponse = page.waitForResponse((response) =>
      response.url().includes("/extraction/confirm") && response.request().method() === "POST",
    );
    await confirm.click();
    const result = await (await confirmResponse).json() as { created_events: number; skipped_duplicates: number };
    expect(result.created_events + result.skipped_duplicates).toBe(1);
    await expect(review.getByRole("status").filter({ hasText: "added to your timeline" })).toBeVisible();
  } else {
    expect(extraction.status).toBe("confirmed");
  }

  await page.getByRole("button", { name: "Close" }).click();
  await page.goto("/timeline");
  await expect(page.getByRole("heading", { name: "Medical timeline" })).toBeVisible();
  await expect(page.getByText("Diagnosis: Seasonal allergic rhinitis")).toBeVisible();

  await page.goto("/family");
  await expect(page.locator(".share-row").filter({ hasText: "Ira Mehta" }).first()).toBeVisible();
  const profileSwitcher = page.getByLabel("Switch patient profile");
  await profileSwitcher.selectOption({ label: "Ira Mehta · owner" });
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Welcome, Ira Mehta" })).toBeVisible();
  await page.getByLabel("Switch patient profile").selectOption("");
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Welcome, Aarav Mehta" })).toBeVisible();

  await page.goto("/settings/account");
  await expect(page.getByRole("heading", { name: "My consents" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent account activity" })).toBeVisible();
  const fhirDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download FHIR Bundle" }).click();
  expect((await fhirDownload).suggestedFilename()).toBe("medical-passport-fhir-r4-aligned.json");

  await page.getByRole("combobox", { name: "Language" }).selectOption("hi");
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");
  await page.getByRole("combobox", { name: "भाषा" }).selectOption("en");

  await page.goto("/emergency");
  await page.locator("#share-label").fill("Demo E2E verification");
  await page.getByRole("checkbox", { name: /I understand anyone with this QR link/ }).check();
  await page.getByRole("button", { name: "Create emergency QR" }).click();
  await expect(page.getByAltText("Emergency access QR code")).toBeVisible();
  const publicLink = await page.locator(".qr-result a[href]").first().getAttribute("href");
  expect(publicLink).toBeTruthy();
  const publicUrl = new URL(new URL(publicLink!).pathname, page.url()).toString();

  const publicContext = await browser.newContext();
  const publicPage = await publicContext.newPage();
  await publicPage.goto(publicUrl);
  await expect(publicPage.getByRole("heading", { name: "Aarav Mehta" })).toBeVisible();
  await expect(publicPage.getByText("SYNTHETIC DEMO DATA — NOT A REAL PATIENT")).toBeVisible();
  await expect(publicPage.getByRole("heading", { name: "Allergies / एलर्जी" })).toBeVisible();
  await expect(publicPage.getByText("Cetirizine", { exact: false })).toHaveCount(0);

  await page.reload();
  const shareRow = page.locator(".share-row").filter({ hasText: "Demo E2E verification" }).first();
  await expect(shareRow).toBeVisible();
  await expect(shareRow.getByText(/viewed 1×/)).toBeVisible();
  await shareRow.getByRole("button", { name: "Who viewed" }).click();
  await expect(page.locator(".access-log")).toContainText("network");
  await shareRow.getByRole("button", { name: "Revoke" }).click();
  await publicPage.reload();
  await expect(publicPage.getByRole("heading", { name: "Link unavailable" })).toBeVisible();
  await publicContext.close();
});
