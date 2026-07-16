import { describe, expect, it, vi } from 'vitest';

import { renderProductCard } from '../src/ui/product-card';

describe('product card', () => {
  it('renders fetched strings as text and sends a safe open request', async () => {
    const send = vi.fn().mockResolvedValue({ ok: true });
    const card = renderProductCard({
      id: '1',
      title: '<img src=x onerror=alert(1)> Core Shirt',
      price: 2999,
      currency: 'PKR',
      imageUrl: 'https://cdn.example.com/1.jpg',
      productUrl: 'https://outfitters.com.pk/products/core-shirt',
      score: 9,
      reason: '<script>bad()</script> Clean casual metadata.',
    }, 0, send);

    document.body.append(card);
    expect(card.querySelectorAll('script')).toHaveLength(0);
    expect(card.querySelector('.product-title')?.textContent).toContain('<img');
    expect(card.querySelector('.product-reason')?.textContent).toContain('<script>');
    expect(card.textContent).toContain('Best match');
    card.click();
    expect(send).toHaveBeenCalledWith({
      type: 'OPEN_PRODUCT',
      productUrl: 'https://outfitters.com.pk/products/core-shirt',
    });
  });

  it('uses an accessible external-tab label', () => {
    const card = renderProductCard({
      id: '2', title: 'Olive Shirt', price: 2500, currency: 'PKR',
      imageUrl: 'https://cdn.example.com/2.jpg',
      productUrl: 'https://outfitters.com.pk/products/olive-shirt',
      score: 8, reason: 'Olive metadata supports an earthy look.',
    }, 1, vi.fn());
    expect(card.getAttribute('aria-label')).toContain('Opens in a new tab');
    expect(card.textContent).not.toContain('Best match');
  });

  it('focuses lower in catalog images for lower-body garments', () => {
    const pants = renderProductCard({
      id: '3', title: 'Relaxed Fit Trousers', price: 3500, currency: 'PKR',
      imageUrl: 'https://cdn.example.com/3.jpg',
      productUrl: 'https://outfitters.com.pk/products/relaxed-trousers',
      score: 9, reason: 'Matches trousers.',
    }, 2, vi.fn());
    const shirt = renderProductCard({
      id: '4', title: 'Oxford Shirt', price: 3000, currency: 'PKR',
      imageUrl: 'https://cdn.example.com/4.jpg',
      productUrl: 'https://outfitters.com.pk/products/oxford-shirt',
      score: 9, reason: 'Matches shirt.',
    }, 3, vi.fn());

    expect(pants.querySelector('.product-media')?.classList).toContain('is-lower-body');
    expect(shirt.querySelector('.product-media')?.classList).not.toContain('is-lower-body');
  });

  it('shows verified facts and warns when the preview is not color-specific', () => {
    const card = renderProductCard({
      id: '5', title: 'Baggy Jeans', price: 4500, currency: 'PKR',
      imageUrl: 'https://cdn.example.com/generic.jpg',
      productUrl: 'https://outfitters.com.pk/products/baggy-jeans',
      score: 10, reason: 'Matches the requested details.',
      matchDetails: {
        colors: ['Black'], sizes: ['32'], fit: 'baggy', occasion: null,
        audience: 'men', imageMatchesColor: false,
      },
    }, 0, vi.fn());

    expect(card.querySelector('.verified-facts')?.textContent).toContain('Black');
    expect(card.querySelector('.verified-facts')?.textContent).toContain('baggy fit');
    expect(card.querySelector('.image-color-notice')?.textContent).toContain('preview image may differ');
  });
});
