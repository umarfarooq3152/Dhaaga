import type { ProductResult, WorkerRequest } from '../shared/contracts';

function formatPrice(price: number, currency: string): string {
  if (currency === 'PKR') return `Rs. ${Math.round(price).toLocaleString('en-PK')}`;
  return `${currency} ${price.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

const LOWER_BODY_PRODUCT = /\b(?:jeans?|pants?|trousers?|chinos?|joggers?|leggings?|shorts?|skirts?|skorts?|culottes?|shalwars?|bottoms?)\b/i;

export function usesLowerImageFocus(title: string): boolean {
  return LOWER_BODY_PRODUCT.test(title);
}

function externalLinkIcon(): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('card-link-icon');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M14 5h5v5M19 5l-9 9M19 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5');
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', '1.8');
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  svg.append(path);
  return svg;
}

export function renderProductCard(
  product: ProductResult,
  index: number,
  sendMessage: (message: WorkerRequest) => Promise<unknown>,
): HTMLButtonElement {
  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'product-card';
  card.setAttribute('aria-label', `${product.title}, ${formatPrice(product.price, product.currency)}. Opens in a new tab.`);

  const media = document.createElement('span');
  media.className = 'product-media';
  if (usesLowerImageFocus(product.title)) media.classList.add('is-lower-body');
  const fallback = document.createElement('span');
  fallback.className = 'image-fallback';
  fallback.textContent = 'Image unavailable';
  const image = document.createElement('img');
  image.src = product.imageUrl;
  image.alt = '';
  image.loading = 'lazy';
  image.referrerPolicy = 'no-referrer';
  image.addEventListener('error', () => {
    image.hidden = true;
    fallback.classList.add('is-visible');
  }, { once: true });
  media.append(image, fallback);

  const body = document.createElement('span');
  body.className = 'product-body';
  if (index === 0) {
    const badge = document.createElement('span');
    badge.className = 'best-match';
    badge.textContent = 'Best match';
    body.append(badge);
  }
  const title = document.createElement('span');
  title.className = 'product-title';
  title.textContent = product.title;
  const price = document.createElement('span');
  price.className = 'product-price';
  price.textContent = formatPrice(product.price, product.currency);
  const reasonLabel = document.createElement('span');
  reasonLabel.className = 'reason-label';
  reasonLabel.textContent = 'Why it matches';
  const reason = document.createElement('span');
  reason.className = 'product-reason';
  reason.textContent = product.reason;
  body.append(title, price, reasonLabel, reason);

  card.append(media, body, externalLinkIcon());
  card.addEventListener('click', () => {
    void sendMessage({ type: 'OPEN_PRODUCT', productUrl: product.productUrl });
  });
  return card;
}
