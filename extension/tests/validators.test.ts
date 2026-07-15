import { describe, expect, it } from 'vitest';

import { getSupportedStore, isSafeProductUrl, normalizeBackendError } from '../src/shared/validators';

describe('store and URL validation', () => {
  it('accepts Outfitters pages and returns only their origin', () => {
    expect(getSupportedStore('https://www.outfitters.com.pk/collections/men?sort=latest')).toEqual({
      name: 'Outfitters',
      domain: 'www.outfitters.com.pk',
      origin: 'https://www.outfitters.com.pk',
    });
  });

  it.each([
    'http://outfitters.com.pk/products/x',
    'https://outfitters.com.pk.evil.example/products/x',
    'chrome://extensions',
    'javascript:alert(1)',
  ])('rejects unsupported active pages: %s', (url) => {
    expect(() => getSupportedStore(url)).toThrow();
  });

  it('opens only HTTPS product paths on the approved hosts', () => {
    expect(isSafeProductUrl('https://outfitters.com.pk/products/core-shirt')).toBe(true);
    expect(isSafeProductUrl('https://outfitters.com.pk/collections/men')).toBe(false);
    expect(isSafeProductUrl('javascript:alert(1)')).toBe(false);
    expect(isSafeProductUrl('https://evil.example/products/core-shirt')).toBe(false);
  });
});

describe('backend error normalization', () => {
  it('preserves known safe typed errors', () => {
    expect(normalizeBackendError(422, { detail: { code: 'EMPTY_INTENT', message: 'Add more detail.' } })).toMatchObject({
      code: 'EMPTY_INTENT',
      message: 'Add more detail.',
      retriable: false,
    });
  });

  it('maps unknown server failures to safe copy', () => {
    expect(normalizeBackendError(500, { detail: 'secret upstream trace' })).toMatchObject({
      code: 'PROVIDER_UNAVAILABLE',
      retriable: true,
    });
  });
});
