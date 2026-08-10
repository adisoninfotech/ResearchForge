import { expect, test } from '@playwright/test';

test('guest draft save, register, transfer, logout/login persistence', async ({ page }) => {
  const email = `guest-${Date.now()}@example.com`;
  const password = 'Password123!';

  await page.goto('/workspace');
  await page.getByLabel('Paper title').fill('Guest Evidence Paper');
  await page.getByLabel('Research area').fill('Computer Science');
  await page.getByLabel('Research problem').fill('Authors need grounded drafts');
  await page.getByLabel('Proposed contribution').fill('A private conversion workflow');

  await page.getByRole('button', { name: 'Save' }).click();
  const authDialog = page.getByRole('dialog', { name: 'Sign in to continue' });
  await expect(authDialog).toBeVisible();
  await authDialog.getByRole('link', { name: 'Create account' }).click();

  await expect(page).toHaveURL(/\/register/);
  await page.getByLabel('Display name').fill('Guest User');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.locator('#main').getByRole('button', { name: 'Create account' }).click();

  await expect(page).toHaveURL(/\/dashboard/);
  await expect(
    page.getByRole('dialog', { name: 'Save your temporary draft as a new project?' }),
  ).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: 'Save as project' }).click();
  await expect(
    page.getByRole('dialog', { name: 'Save your temporary draft as a new project?' }),
  ).toBeHidden({ timeout: 15_000 });
  await expect(page.getByRole('heading', { name: /Welcome/ })).toBeVisible();
  await expect(
    page.locator('#main').getByText('Guest Evidence Paper', { exact: true }),
  ).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page.getByRole('link', { name: 'Sign in' }).first()).toBeVisible();

  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.locator('#main').getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(
    page.locator('#main').getByText('Guest Evidence Paper', { exact: true }),
  ).toBeVisible({ timeout: 15_000 });
});
