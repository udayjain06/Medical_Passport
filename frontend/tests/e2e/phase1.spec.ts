import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

test("registration, protected profile, persistence, logout, and login", async ({ page }) => {
  test.setTimeout(180000);
  const screenshotDir = path.resolve(process.cwd(), "..", "docs", "demo-screenshots");
  await mkdir(screenshotDir, { recursive: true });
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const apiFailures: string[] = [];
  function monitor(target: Page) {
    target.on("pageerror", (error) => pageErrors.push(error.message));
    target.on("console", (message) => {
      const url = message.location().url;
      const expectedUnavailableState = url.includes("/api/documents/") && url.endsWith("/extraction") || url.includes("/api/public/emergency/");
      if (message.type() === "error" && !expectedUnavailableState) consoleErrors.push(`${message.text()} @ ${url}`);
    });
    target.on("response", (response) => {
      if (response.url().includes("/api/") && response.status() >= 500) apiFailures.push(`${response.status()} ${response.url()}`);
    });
    target.on("requestfailed", (request) => {
      if (request.url().includes("/api/") && request.failure()?.errorText !== "net::ERR_ABORTED") {
        apiFailures.push(`network failure ${request.url()} (${request.failure()?.errorText ?? "unknown"})`);
      }
    });
  }
  monitor(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "When you cannot speak, your history should speak for you." })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "landing.png"), fullPage: true });

  const noJavaScriptContext = await page.context().browser()!.newContext({ javaScriptEnabled: false });
  const noJavaScriptPage = await noJavaScriptContext.newPage();
  await noJavaScriptPage.goto("/signup");
  await expect(noJavaScriptPage.getByRole("button", { name: "Create account" })).toBeDisabled();
  expect(await noJavaScriptPage.locator("form").getAttribute("method")).toBe("post");
  await noJavaScriptContext.close();

  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await page.screenshot({ path: path.join(screenshotDir, "login.png"), fullPage: true });

  const email = `patient-${Date.now()}@example.com`;
  const password = "Safe-demo-passphrase-42";
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Test Patient");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  const registerResponse = page.waitForResponse((response) =>
    response.url().includes("/api/auth/register") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Create account" }).click();
  expect((await registerResponse).status()).toBe(201);
  expect(new URL(page.url()).search).toBe("");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Welcome, Test Patient" })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, "dashboard.png"), fullPage: true });

  await page.getByRole("link", { name: "Review or edit profile" }).click();
  await page.getByLabel("Known allergies").fill("Patient reports penicillin allergy");
  await page.getByLabel("Blood group").selectOption("O+");
  await page.getByLabel("Contact name").fill("Emergency Contact");
  await page.getByLabel("Contact phone").fill("+91 98765 43210");
  await page.getByLabel("Relationship (optional)").fill("Sibling");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("status")).toHaveText("Profile saved.");
  await page.reload();
  await expect(page.getByLabel("Known allergies")).toHaveValue("Patient reports penicillin allergy");
  await expect(page.getByLabel("Blood group")).toHaveValue("O+");

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Review before it becomes history" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sharing should be deliberate" })).toBeVisible();
  await expect(page.getByText(/IN DEVELOPMENT/i)).toHaveCount(0);
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes("/api/auth/login") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Log in" }).click();
  expect((await loginResponse).status()).toBe(200);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(email)).toBeVisible();

  await page.getByRole("link", { name: "Documents" }).click();
  const fixture = Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF");
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-lab-report.pdf",
    mimeType: "application/pdf",
    buffer: fixture,
  });
  await expect(page.getByText("synthetic-lab-report.pdf")).toBeVisible();
  const detailsButton = page.getByRole("button", { name: "Details" });
  await detailsButton.scrollIntoViewIfNeeded();
  const detailsButtonBox = await detailsButton.boundingBox();
  expect(detailsButtonBox).not.toBeNull();
  await page.mouse.move(detailsButtonBox!.x + detailsButtonBox!.width / 2, detailsButtonBox!.y + detailsButtonBox!.height / 2);
  await page.mouse.down();
  const reducedMotion = await detailsButton.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches);
  if (reducedMotion) {
    await expect.poll(() => detailsButton.evaluate((element) => getComputedStyle(element).opacity), { timeout: 1000 }).toBe("0.78");
  } else {
    await expect.poll(() => detailsButton.evaluate((element) => getComputedStyle(element).transform), { timeout: 1000 }).toBe("matrix(0.97, 0, 0, 0.97, 0, 0)");
  }
  await page.mouse.up();
  await expect(page.getByRole("dialog", { name: "Document details" })).toBeVisible();
  await expect(page.locator(".document-sheet")).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)", { timeout: 5000 });
  const glassSurface = await page.locator(".account-header").evaluate((element) => ({
    filter: getComputedStyle(element).backdropFilter,
    reducedTransparency: matchMedia("(prefers-reduced-transparency: reduce)").matches,
    forcedColors: matchMedia("(forced-colors: active)").matches,
  }));
  if (glassSurface.reducedTransparency || glassSurface.forcedColors) expect(glassSurface.filter).toBe("none");
  else expect(glassSurface.filter).toContain("blur");
  const dragHandle = page.locator(".sheet-drag-handle");
  const dragHandleBox = await dragHandle.boundingBox();
  expect(dragHandleBox).not.toBeNull();
  await page.mouse.move(dragHandleBox!.x + dragHandleBox!.width / 2, dragHandleBox!.y + dragHandleBox!.height / 2);
  await page.mouse.down();
  await page.mouse.move(dragHandleBox!.x + dragHandleBox!.width / 2, dragHandleBox!.y + 170, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole("dialog", { name: "Document details" })).toHaveCount(0, { timeout: 5000 });
  await page.getByRole("button", { name: "Details" }).click();
  await expect(page.getByTitle("Preview synthetic-lab-report.pdf")).toBeVisible();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog", { name: "Document details" })).toHaveCount(0, { timeout: 2000 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.getByRole("button", { name: "Details" }).click();
  await expect(page.getByRole("button", { name: "Delete document" })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete document" }).click();
  await expect(page.getByText("Your vault is ready")).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles("tests/e2e/fixtures/synthetic-lab-report.png");
  await expect(page.getByText("synthetic-lab-report.png")).toBeVisible();
  await page.getByRole("button", { name: "Details" }).click();
  await page.getByRole("button", { name: "Run OCR and extraction" }).click();
  await expect(page.getByText("needs review")).toBeVisible({ timeout: 60000 });
  await expect(page.locator(".review-box textarea").first()).toHaveValue(/Synthetic Lab Report/);
  // Nothing can be confirmed until the patient accepts at least one suggestion.
  await expect(page.getByRole("button", { name: /Add 0 accepted/ })).toBeDisabled();
  const timelineCandidate = page.locator(".candidate").filter({
    hasText: /Diagnosis|Condition|Allergy|Medication|Procedure|Lab result|Admission date|Discharge date|Follow-up date|Unstructured text/,
  }).first();
  await timelineCandidate.getByRole("button", { name: "Accept", exact: true }).click();
  await page.getByRole("button", { name: /Add 1 accepted/ }).click();
  await expect(page.getByRole("status").filter({ hasText: "added to your" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await page.goto("/timeline");
  await expect(page.getByText("Source Text", { exact: false })).toBeVisible();
  const sourceFilter = page.getByLabel("Filter source document");
  await sourceFilter.selectOption({ label: "synthetic-lab-report.png" });
  await expect(sourceFilter).toHaveValue(/.+/);
  await expect(page.locator(".timeline-item").first()).toBeVisible();
  await page.getByLabel("Filter category").selectOption("Medical observation");
  await expect(page.getByRole("heading", { name: /Synthetic Lab Report/ })).toBeVisible();
  await page.getByLabel("Filter source document").selectOption("");
  await page.getByLabel("Filter category").selectOption("");
  await page.getByLabel("Event title").fill("E2E timeline event");
  await page.getByLabel("Event category").selectOption("Allergy");
  await page.getByLabel("Event date").fill("2025-04-12");
  await page.getByLabel("Event review status").selectOption("conflict");
  await page.getByLabel("Conflict group").fill("e2e-conflict");
  await page.getByRole("button", { name: "Add event" }).click();
  await expect(page.getByRole("heading", { name: "E2E timeline event" })).toBeVisible();
  await page.getByLabel("Filter category").selectOption("Allergy");
  await expect(page.locator(".timeline-item")).toHaveCount(1);
  const e2eEvent = page.locator(".timeline-item").filter({ has: page.getByRole("heading", { name: "E2E timeline event" }) });
  await e2eEvent.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Event title").fill("E2E edited timeline event");
  await page.getByLabel("Event review status").selectOption("uncertain");
  await page.getByLabel("Why is this uncertain?").fill("Synthetic test uncertainty.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("heading", { name: "E2E edited timeline event" })).toBeVisible();
  await page.getByLabel("Filter review status").selectOption("uncertain");
  await expect(page.getByText("Synthetic test uncertainty.")).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("heading", { name: "E2E edited timeline event" })).toHaveCount(0);
  await page.getByLabel("Filter review status").selectOption("");

  await page.goto("/emergency");
  await page.locator("#share-expiry").selectOption("8760");
  await page.locator("#share-label").fill("Wallet card");
  await page.getByText("I understand anyone with this QR link can view the selected information.").click();
  await page.getByRole("button", { name: "Create emergency QR" }).click();
  const publicLink = await page.locator(".qr-result a").first().getAttribute("href");
  expect(publicLink).toBeTruthy();
  const publicUrl = new URL(new URL(publicLink!).pathname, page.url()).toString();
  await expect(page.getByAltText("Emergency access QR code")).toBeVisible();
  await expect(page.getByText(/cannot be shown again/)).toBeVisible();
  const qrDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download QR" }).click();
  expect((await qrDownload).suggestedFilename()).toBe("medical-passport-emergency-qr.png");
  await page.evaluate(() => {
    const testWindow = window as Window & { __walletPrintCalled?: boolean };
    testWindow.print = () => { testWindow.__walletPrintCalled = true; };
  });
  await page.getByRole("button", { name: "Print wallet card" }).click();
  expect(await page.evaluate(() => (window as Window & { __walletPrintCalled?: boolean }).__walletPrintCalled)).toBe(true);
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".wallet-card")).toBeVisible();
  await page.emulateMedia({ media: "screen" });

  const publicContext = await page.context().browser()!.newContext();
  const publicPage = await publicContext.newPage();
  monitor(publicPage);
  await publicPage.goto(publicUrl);
  await expect(publicPage.getByRole("heading", { name: "Test Patient" })).toBeVisible();
  await expect(publicPage.getByText("Test Patient", { exact: false }).first()).toBeVisible();
  await page.goto("/emergency");
  await expect(page.getByText(/viewed 1×/)).toBeVisible();
  await page.getByRole("button", { name: "Who viewed" }).click();
  await expect(page.locator(".access-log")).toContainText("network");
  await page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Renew" }).first().click();
  const renewedLink = await page.locator(".qr-result a").first().getAttribute("href");
  expect(renewedLink).toBeTruthy();
  const renewedUrl = new URL(new URL(renewedLink!).pathname, page.url()).toString();
  await publicPage.goto(publicUrl);
  await expect(publicPage.getByRole("heading", { name: "Link unavailable" })).toBeVisible();
  await publicPage.goto(renewedUrl);
  await expect(publicPage.getByRole("heading", { name: "Test Patient" })).toBeVisible();
  const activeShare = page.locator(".share-row").first();
  await activeShare.getByRole("button", { name: "Revoke" }).click();
  await publicPage.reload();
  await expect(publicPage.getByRole("heading", { name: "Link unavailable" })).toBeVisible();
  await publicContext.close();

  await page.goto("/family");
  await page.getByLabel("Dependent full name").fill("Synthetic Dependent");
  await page.getByText("I have consent or lawful authority").click();
  await page.getByRole("button", { name: "Add dependent" }).click();
  await expect(page.getByRole("status")).toContainText("Dependent profile created");
  await page.reload();
  await page.getByLabel("Switch patient profile").selectOption({ label: "Synthetic Dependent · owner" });
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Welcome, Synthetic Dependent" })).toBeVisible();
  await page.goto("/documents");
  const dependentFilename = `dependent-only-${Date.now()}.pdf`;
  const dependentUpload = page.waitForResponse((response) =>
    response.url().includes("/api/documents") && response.request().method() === "POST",
    { timeout: 20000 },
  );
  await expect(page.locator('input[type="file"]')).toHaveCount(1);
  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Choose a file" }).click();
  await (await chooserPromise).setFiles({ name: dependentFilename, mimeType: "application/pdf", buffer: fixture });
  expect((await dependentUpload).status()).toBe(201);
  await expect(page.getByText(dependentFilename)).toBeVisible();
  await page.getByLabel("Switch patient profile").selectOption("");
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Welcome, Test Patient" })).toBeVisible();
  await page.goto("/documents");
  await expect(page.getByText(dependentFilename)).toHaveCount(0);
  await page.goto("/family");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Archive profile" }).click();
  await expect(page.getByRole("status")).toContainText("was archived");
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Welcome, Test Patient" })).toBeVisible();

  const familyContext = await page.context().browser()!.newContext();
  const familyPage = await familyContext.newPage();
  monitor(familyPage);
  const familyEmail = `family-${Date.now()}@example.com`;
  await familyPage.goto("/signup");
  await familyPage.getByLabel("Full name").fill("Family Member");
  await familyPage.getByLabel("Email address").fill(familyEmail);
  await familyPage.getByLabel("Password").fill(password);
  await familyPage.getByRole("button", { name: "Create account" }).click();
  await expect(familyPage).toHaveURL(/\/dashboard$/);
  await page.goto("/family");
  await page.getByLabel("Profile to share").selectOption({ label: "Test Patient" });
  await page.getByLabel("Family member account email").fill(familyEmail);
  await page.getByRole("button", { name: "Grant access" }).click();
  await expect(page.getByRole("status")).toContainText("Access granted");
  await familyPage.goto("/dashboard");
  await familyPage.getByLabel("Switch patient profile").selectOption({ label: "Test Patient · viewer" });
  await expect(familyPage.getByRole("heading", { name: "Welcome, Test Patient" })).toBeVisible();
  await familyPage.goto("/documents");
  await expect(familyPage.getByText("synthetic-lab-report.png")).toBeVisible();
  await expect(familyPage.getByRole("button", { name: "Choose a file" })).toHaveCount(0);
  await familyPage.getByRole("button", { name: "Details" }).click();
  await expect(familyPage.getByTitle("Preview synthetic-lab-report.png")).toBeVisible();
  await expect(familyPage.getByRole("button", { name: "Delete document" })).toHaveCount(0);
  await familyPage.goto("/timeline");
  await expect(familyPage.getByText(/This profile is read-only/)).toBeVisible();
  await expect(familyPage.getByRole("button", { name: "Add event" })).toHaveCount(0);
  await familyContext.close();

  await page.goto("/settings/abha");
  await expect(page.getByText("externally blocked")).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  for (const route of ["/", "/login", "/signup", "/dashboard", "/documents", "/timeline", "/emergency", "/family", "/profile", "/settings/abha", "/settings/account"]) {
    await page.goto(route);
    const layout = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      offenders: [...document.querySelectorAll<HTMLElement>("body *")]
        .map((el) => ({ tag: el.tagName, className: String(el.className), text: el.innerText?.slice(0, 60), right: Math.round(el.getBoundingClientRect().right), width: Math.round(el.getBoundingClientRect().width) }))
        .filter((el) => el.right > window.innerWidth + 1)
        .slice(0, 8),
    }));
    expect(layout.width <= 375, `${route} mobile overflow: ${JSON.stringify(layout)}`).toBe(true);
  }
  await page.goto("/settings/account");
  const exportDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download export" }).click();
  expect((await exportDownload).suggestedFilename()).toBe("medical-passport-export.json");
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Type DELETE to confirm").fill("DELETE");
  await page.getByRole("button", { name: "Delete account permanently" }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(apiFailures).toEqual([]);
});
