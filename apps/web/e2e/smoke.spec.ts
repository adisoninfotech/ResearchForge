import { expect, test } from '@playwright/test';

test('landing and guest workspace smoke', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('link', { name: 'ResearchForge home' })).toBeVisible();
  await expect(page.getByText('ResearchForge').first()).toBeVisible();

  await page.getByRole('link', { name: 'Open guest workspace' }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await expect(
    page.getByText('Your draft stays in this browser until you sign in', { exact: false }),
  ).toBeVisible();
  await expect(page.getByLabel('Paper title')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Generate Outline' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();

  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('dialog', { name: 'Sign in to continue' })).toBeVisible();
});
