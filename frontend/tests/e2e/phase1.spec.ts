import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";

async function getTestEmailLink(page: Page, purpose: "email_verification" | "password_reset") {
  const result = await page.evaluate(async (emailPurpose) => {
    const response = await fetch(`/api/auth/test/email-link?purpose=${emailPurpose}`);
    return { status: response.status, body: await response.json() as { url?: string } };
  }, purpose);
  expect(result.status).toBe(200);
  expect(result.body.url).toBeTruthy();
  const link = new URL(result.body.url!);
  return `${link.pathname}${link.search}`;
}

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      description: violation.description,
      nodes: violation.nodes.map((node) => ({ target: node.target, html: node.html, failureSummary: node.failureSummary })),
    })),
  ).toEqual([]);
}

test("registration, protected profile, persistence, logout, and login", async ({ page }) => {
  test.setTimeout(180000);
  const screenshotDir = process.env.E2E_SCREENSHOT_DIR
    ?? path.resolve(process.cwd(), "..", "docs", "demo-screenshots");
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
  const landingResponse = await page.goto("/");
  expect(landingResponse).not.toBeNull();
  const landingHeaders = landingResponse!.headers();
  expect(landingHeaders["cache-control"]).toContain("no-store");
  expect(landingHeaders["x-content-type-options"]).toBe("nosniff");
  expect(landingHeaders["x-frame-options"]).toBe("DENY");
  expect(landingHeaders["permissions-policy"]).toContain("microphone=()");
  expect(landingHeaders["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(landingHeaders["content-security-policy"]).toContain("frame-src 'self' blob:");
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
  await expectAccessible(page);
  await page.getByLabel("Email address").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Log in" })).toBeFocused();
  await page.screenshot({ path: path.join(screenshotDir, "login.png"), fullPage: true });

  const email = `patient-${Date.now()}@example.com`;
  const password = "Safe-demo-passphrase-42";
  await page.goto("/signup");
  await expectAccessible(page);
  await page.getByLabel("Full name").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email address")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("I agree to the Terms.")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Terms" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("I acknowledge the Privacy notice.")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Privacy notice" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Create account" })).toBeFocused();
  await page.getByLabel("Full name").fill("Test Patient");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("I agree to the Terms.").check();
  await page.getByLabel("I acknowledge the Privacy notice.").check();
  const registerResponse = page.waitForResponse((response) =>
    response.url().includes("/api/auth/register") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Create account" }).click();
  expect((await registerResponse).status()).toBe(201);
  expect(new URL(page.url()).search).toBe("");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Welcome, Test Patient" })).toBeVisible();
  await expect(page.locator(".first-run-list li")).toHaveCount(4);
  await expect(page.locator(".first-run-status")).toHaveText(["Not started", "Not started", "Not started", "Not started"]);
  await page.screenshot({ path: path.join(screenshotDir, "dashboard.png"), fullPage: true });

  const verificationPath = await getTestEmailLink(page, "email_verification");
  await page.goto(verificationPath);
  await page.getByRole("button", { name: "Verify email" }).click();
  await expect(page.getByRole("status")).toContainText("Your email is verified");
  await page.getByRole("link", { name: "Continue to Medical Passport" }).click();
  await expect(page.getByRole("heading", { name: "Welcome, Test Patient" })).toBeVisible();

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

  const replacementPassword = "New-safe-demo-passphrase-77";
  await page.goto("/forgot-password");
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Send reset instructions" }).click();
  await expect(page.getByRole("status")).toContainText("If an account exists");
  const resetPath = await getTestEmailLink(page, "password_reset");
  await page.goto(resetPath);
  await page.getByLabel("New password", { exact: true }).fill(replacementPassword);
  await page.getByLabel("Confirm new password", { exact: true }).fill(replacementPassword);
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByRole("status")).toContainText("Your password was changed");
  await page.getByRole("link", { name: "Continue to login" }).click();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(replacementPassword);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Review before it becomes history" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sharing should be deliberate" })).toBeVisible();
  await expect(page.getByText(/IN DEVELOPMENT/i)).toHaveCount(0);
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(replacementPassword);
  const loginResponse = page.waitForResponse((response) =>
    response.url().includes("/api/auth/login") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Log in" }).click();
  expect((await loginResponse).status()).toBe(200);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText(email)).toBeVisible();

  await page.getByRole("navigation", { name: "Account navigation" }).getByRole("link", { name: "Documents" }).click();
  await expect(page.getByRole("heading", { name: "Your documents" })).toBeVisible();
  await expectAccessible(page);
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
  await expect(page.getByRole("button", { name: "Close" })).toBeFocused();
  const sheetControls = page.locator(".document-sheet button:not(:disabled), .document-sheet a[href], .document-sheet input:not(:disabled), .document-sheet select:not(:disabled), .document-sheet textarea:not(:disabled), .document-sheet [tabindex='0']");
  const lastSheetControl = sheetControls.last();
  await page.keyboard.press("Shift+Tab");
  await expect(lastSheetControl).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Close" })).toBeFocused();
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
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Document details" })).toHaveCount(0, { timeout: 5000 });
  await expect(page.getByRole("button", { name: "Details" })).toBeFocused();
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
  await expectAccessible(page);
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
  const timelineFilters = page.getByRole("region", { name: "Timeline filters" });
  const sourceFilter = timelineFilters.getByLabel("All sources");
  await sourceFilter.selectOption({ label: "synthetic-lab-report.png" });
  await expect(sourceFilter).toHaveValue(/.+/);
  await expect(page.locator(".timeline-item").first()).toBeVisible();
  const categoryFilter = timelineFilters.getByLabel("Category");
  await categoryFilter.selectOption("Medical observation");
  await expect(page.getByRole("heading", { name: /Synthetic Lab Report/ })).toBeVisible();
  await sourceFilter.selectOption("");
  await categoryFilter.selectOption("");
  await page.getByLabel("Event title").fill("E2E timeline event");
  await page.getByLabel("Category").first().selectOption("Allergy");
  await page.getByLabel("Event date").fill("2025-04-12");
  await page.getByLabel("Review status").first().selectOption("conflict");
  await page.getByLabel("Conflict group").fill("e2e-conflict");
  await page.getByRole("button", { name: "Add event" }).click();
  await expect(page.getByRole("heading", { name: "E2E timeline event" })).toBeVisible();
  await categoryFilter.selectOption("Allergy");
  await expect(page.locator(".timeline-item")).toHaveCount(1);
  const e2eEvent = page.locator(".timeline-item").filter({ has: page.getByRole("heading", { name: "E2E timeline event" }) });
  await e2eEvent.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Event title").fill("E2E edited timeline event");
  await page.getByLabel("Review status").first().selectOption("uncertain");
  await page.getByLabel("Why is this uncertain?").fill("Synthetic test uncertainty.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("heading", { name: "E2E edited timeline event" })).toBeVisible();
  const reviewStatusFilter = timelineFilters.getByLabel("Review status");
  await reviewStatusFilter.selectOption("uncertain");
  await expect(page.getByText("Synthetic test uncertainty.")).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("heading", { name: "E2E edited timeline event" })).toHaveCount(0);
  await reviewStatusFilter.selectOption("");

  await page.goto("/emergency");
  await expect(page.getByLabel("Set an offline PIN (8 or more digits)")).toBeVisible();
  await expectAccessible(page);
  const offlineFields = page.getByRole("group", { name: "Choose fields for the offline card" });
  await offlineFields.getByLabel("Patient name").check();
  await offlineFields.getByLabel("Blood group").check();
  await offlineFields.getByLabel("Known allergies").check();
  await offlineFields.getByLabel("Emergency contacts").check();
  await page.getByLabel("Set an offline PIN (8 or more digits)").fill("13572468");
  await page.getByLabel("Confirm offline PIN").fill("13572468");
  await page.getByRole("checkbox", { name: /I understand this local copy/ }).check();
  await page.getByRole("button", { name: "Save encrypted card on this device" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Encrypted emergency card saved" })).toBeVisible();
  const offlineHref = await page.getByRole("link", { name: "Open offline card" }).getAttribute("href");
  expect(offlineHref).toBeTruthy();
  const offlineUrl = new URL(offlineHref!, page.url()).toString();
  const profileId = new URL(offlineUrl).searchParams.get("profile");
  expect(profileId).toBeTruthy();
  const storedCard = await page.evaluate(async (id) => {
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open("medical-passport-offline-v1", 1);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    try {
      const record = await new Promise<{ ciphertext: ArrayBuffer }>((resolve, reject) => {
        const request = database.transaction("cards", "readonly").objectStore("cards").get(id);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      const cleartext = new TextDecoder().decode(record.ciphertext);
      return {
        hasCiphertext: record.ciphertext instanceof ArrayBuffer,
        containsPatientData: cleartext.includes("Test Patient") || cleartext.includes("Patient reports penicillin allergy"),
      };
    } finally {
      database.close();
    }
  }, profileId!);
  expect(storedCard.hasCiphertext).toBe(true);
  expect(storedCard.containsPatientData).toBe(false);
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  const staticCache = await page.evaluate(async () => {
    const names = await caches.keys();
    const entries: string[] = [];
    for (const name of names) {
      const cache = await caches.open(name);
      for (const request of await cache.keys()) entries.push(new URL(request.url).pathname);
    }
    return { names, entries: entries.sort() };
  });
  expect(staticCache.names).toEqual(["medical-passport-static-shell-v1"]);
  expect(staticCache.entries).toEqual([
    "/icons/medical-passport.svg",
    "/manifest.webmanifest",
    "/offline-card-crypto.js",
    "/offline-card.css",
    "/offline-card.html",
    "/offline-card.js",
  ]);
  expect(staticCache.entries.some((entry) => entry.startsWith("/api/") || entry.startsWith("/emergency/"))).toBe(false);
  await page.context().setOffline(true);
  const offlinePage = await page.context().newPage();
  await offlinePage.goto(offlineUrl);
  await offlinePage.getByLabel("PIN · पिन").fill("00000000");
  await offlinePage.getByRole("button", { name: "Unlock · खोलें" }).click();
  await expect(offlinePage.getByRole("status")).toContainText("PIN did not match");
  await expect(offlinePage.getByRole("heading", { name: "Test Patient" })).toHaveCount(0);
  await offlinePage.getByLabel("PIN · पिन").fill("13572468");
  await offlinePage.getByRole("button", { name: "Unlock · खोलें" }).click();
  await expect(offlinePage.getByRole("heading", { name: "Test Patient" })).toBeVisible();
  await expect(offlinePage.getByText("Patient reports penicillin allergy")).toBeVisible();
  await expect(offlinePage.locator("#last-synced")).toContainText("Last synced");
  await offlinePage.once("dialog", (dialog) => dialog.accept());
  await offlinePage.getByRole("button", { name: "Remove from this device" }).click();
  await expect(offlinePage.getByRole("status")).toContainText("removed from this device");
  await offlinePage.close();
  await page.context().setOffline(false);

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

  await page.goto("/dashboard");
  await expect(page.locator(".first-run-status")).toHaveText(["Complete", "Complete", "Complete", "Complete"]);
  await page.goto("/emergency");

  const publicContext = await page.context().browser()!.newContext();
  const publicPage = await publicContext.newPage();
  monitor(publicPage);
  const publicResponse = await publicPage.goto(publicUrl);
  expect(publicResponse).not.toBeNull();
  expect(publicResponse!.headers()["cache-control"]).toContain("no-store");
  expect(publicResponse!.headers()["referrer-policy"]).toBe("no-referrer");
  await expect(publicPage.getByRole("heading", { name: "Test Patient" })).toBeVisible();
  await expectAccessible(publicPage);
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
  await familyPage.getByLabel("I agree to the Terms.").check();
  await familyPage.getByLabel("I acknowledge the Privacy notice.").check();
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
  await expect(familyPage.getByAltText("Preview of synthetic-lab-report.png")).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "Export my data" })).toBeVisible();
  await expectAccessible(page);
  const exportDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download export" }).click();
  expect((await exportDownload).suggestedFilename()).toBe("medical-passport-export.json");
  await page.getByLabel("Password").fill(replacementPassword);
  await page.getByLabel("Type DELETE to confirm").fill("DELETE");
  await page.getByRole("button", { name: "Delete account permanently" }).click();
  await expect(page).toHaveURL(/\/$/);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(apiFailures).toEqual([]);
});
