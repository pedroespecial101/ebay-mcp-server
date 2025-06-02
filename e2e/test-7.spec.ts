import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://localhost:8000/mcp/');
  await page.getByRole('button', { name: 'search_ebay_items Search' }).click();
  await page.getByRole('textbox', { name: 'query Required string' }).click();
  await page.getByRole('textbox', { name: 'query Required string' }).fill('trainers');
  await page.getByRole('button', { name: ' Execute' }).click();
  await page.getByText('[ "type=\'text\' text=\'{\\"href').click();
});