import { expect, test } from "@playwright/test";

test("submits once and visibly replays the completed request", async ({ page }) => {
  const requestId = `playwright-replay-${Date.now()}`;
  await page.goto("/");
  await expect(page.getByText("Runtime connected")).toBeVisible();
  await page.getByLabel("Message").fill("Validate browser delivery.");
  await page.getByLabel("REQUEST ID").fill(requestId);
  await page.getByRole("button", { name: "Send to runtime" }).click();
  await expect(page.getByText("Worker received: Validate browser delivery.")).toBeVisible();
  await expect(page.getByText("New execution")).toBeVisible();

  await page.getByLabel("Message").fill("This text must not replace the first result.");
  await page.getByRole("button", { name: "Send to runtime" }).click();
  await expect(page.getByText("Completed response")).toBeVisible();
  await expect(page.getByText(/attempt 1 · replay/)).toBeVisible();
  await expect(page.getByText("Worker received: Validate browser delivery.")).toHaveCount(2);
});
