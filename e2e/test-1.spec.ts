import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://localhost:8000/mcp/');
  await page.getByRole('button', { name: 'get_item_aspects_for_category' }).click();
  await page.getByRole('textbox', { name: 'category_id Required string' }).click();
  await page.getByRole('textbox', { name: 'category_id Required string' }).fill('4122');
  await page.getByRole('button', { name: ' Execute' }).click();
  await page.getByRole('button', { name: 'search_ebay_items Search' }).click();
  await page.getByRole('textbox', { name: 'query Required string' }).click();
  await page.getByRole('textbox', { name: 'query Required string' }).fill('adidas trainers camo');
  await page.getByLabel('search_ebay_items Search').getByRole('button', { name: ' Execute' }).click();
});