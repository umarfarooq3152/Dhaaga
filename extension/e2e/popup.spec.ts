import { chromium, expect, test } from '@playwright/test';
import path from 'node:path';
import { readFile } from 'node:fs/promises';

test('loads the unpacked extension popup without a content script', async () => {
  const extensionPath = path.resolve('dist');
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium',
    headless: true,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
    ],
  });
  try {
    let worker = context.serviceWorkers()[0];
    if (!worker) worker = await context.waitForEvent('serviceworker');
    const extensionId = new URL(worker.url()).host;
    const page = await context.newPage();
    await page.goto(`chrome-extension://${extensionId}/popup.html`);
    // The fresh browser tab is about:blank, so the secure expected state is
    // the unsupported-page error—not the search composer.
    await expect(page.getByRole('heading', { name: 'Open a supported store' })).toBeVisible();
    await expect(page.locator('script')).toHaveCount(1);
    const manifest = JSON.parse(await readFile(path.join(extensionPath, 'manifest.json'), 'utf8'));
    expect(manifest.content_scripts).toBeUndefined();
    expect(manifest.host_permissions).toEqual(['http://localhost:8000/*']);
  } finally {
    await context.close();
  }
});

test('keeps products left and conversation right at both widths', async () => {
  const extensionPath = path.resolve('dist');
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium',
    headless: true,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
    ],
  });
  try {
    let worker = context.serviceWorkers()[0];
    if (!worker) worker = await context.waitForEvent('serviceworker');
    const extensionId = new URL(worker.url()).host;
    const page = await context.newPage();
    await page.goto(`chrome-extension://${extensionId}/popup.html`);
    await page.evaluate(() => {
      document.getElementById('blocking-view')!.hidden = true;
      document.getElementById('workspace-view')!.hidden = false;
    });

    const layout = async () => page.evaluate(() => {
      const products = document.querySelector('.products-pane')!.getBoundingClientRect();
      const chat = document.querySelector('.chat-pane')!.getBoundingClientRect();
      return {
        bodyWidth: document.body.getBoundingClientRect().width,
        productsRight: products.right,
        chatLeft: chat.left,
        productsBackground: getComputedStyle(document.querySelector('.products-pane')!).backgroundColor,
        chatBackground: getComputedStyle(document.querySelector('.chat-pane')!).backgroundColor,
      };
    });

    const expanded = await layout();
    expect(expanded.bodyWidth).toBe(800);
    expect(expanded.productsRight).toBeLessThanOrEqual(expanded.chatLeft + 1);
    expect(expanded.productsBackground).not.toBe('rgba(0, 0, 0, 0)');
    expect(expanded.chatBackground).not.toBe('rgba(0, 0, 0, 0)');

    await page.getByRole('button', { name: 'Use compact width' }).click();
    const compact = await layout();
    expect(compact.bodyWidth).toBe(640);
    expect(compact.productsRight).toBeLessThanOrEqual(compact.chatLeft + 1);
  } finally {
    await context.close();
  }
});

test('microphone setup can acquire and release an audio stream', async () => {
  const extensionPath = path.resolve('dist');
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium',
    headless: true,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
      '--use-fake-device-for-media-stream',
      '--use-fake-ui-for-media-stream',
    ],
  });
  try {
    let worker = context.serviceWorkers()[0];
    if (!worker) worker = await context.waitForEvent('serviceworker');
    const extensionId = new URL(worker.url()).host;
    const page = await context.newPage();
    await page.goto(`chrome-extension://${extensionId}/microphone.html`);
    const enableButton = page.getByRole('button', { name: 'Enable microphone' });
    if (await enableButton.isVisible()) await enableButton.click();
    await expect(page.getByRole('status')).toContainText('Microphone is ready');
  } finally {
    await context.close();
  }
});

test('appends more product cards as the products pane is scrolled', async () => {
  const extensionPath = path.resolve('dist');
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium',
    headless: true,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
    ],
  });
  try {
    let worker = context.serviceWorkers()[0];
    if (!worker) worker = await context.waitForEvent('serviceworker');
    const extensionId = new URL(worker.url()).host;
    const page = await context.newPage();
    await page.goto(`chrome-extension://${extensionId}/popup.html`);
    const products = Array.from({ length: 24 }, (_, index) => ({
      id: String(index + 1),
      title: `Polo ${index + 1}`,
      price: 2000 + index,
      currency: 'PKR',
      imageUrl: `https://cdn.example.com/${index + 1}.jpg`,
      productUrl: `https://outfitters.com.pk/products/polo-${index + 1}`,
      score: 10,
      reason: 'Matches polo.',
    }));
    await page.evaluate(async (storedProducts) => {
      await chrome.storage.local.set({
        dhaagaConversation: {
          messages: [{ id: 'welcome', role: 'assistant', text: 'Welcome' }],
          currentResult: {
            intent: { category: 'polo', color: null, size: null, priceMax: null, priceMin: null, descriptive: null },
            products: storedProducts,
            notice: null,
            meta: { storeDomain: 'outfitters.com.pk', fetchedCount: 500, catalogCapped: true, relaxed: false, relaxedFilters: [], durationMs: 100 },
          },
          lastQuery: 'polos',
          updatedAt: Date.now(),
        },
      });
    }, products);
    await page.reload();
    await page.evaluate(() => {
      document.getElementById('blocking-view')!.hidden = true;
      document.getElementById('workspace-view')!.hidden = false;
    });

    await expect(page.locator('.product-card')).toHaveCount(8);
    await page.locator('.products-pane').evaluate((pane) => {
      pane.scrollTop = pane.scrollHeight;
      pane.dispatchEvent(new Event('scroll'));
    });
    await expect(page.locator('.product-card')).toHaveCount(16);
    await expect(page.getByRole('status').filter({ hasText: 'Showing 16 of 24' })).toBeVisible();
  } finally {
    await context.close();
  }
});
