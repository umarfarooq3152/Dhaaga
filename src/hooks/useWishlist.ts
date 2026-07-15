import { useCallback, useEffect, useState } from 'react';
import { addToWishlist, fetchWishlist, removeFromWishlist } from '../api/wishlist';
import { Product } from '../types';

interface UseWishlistResult {
  wishlist: string[];
  wishlistProducts: Product[];
  toggleWishlist: (productId: string) => void;
}

/** Server-backed wishlist, replacing the old pure-localStorage version.
 * Keeps the same `wishlist: string[]` shape existing components already
 * expect, plus hydrated `wishlistProducts` for the drawer.
 *
 * `authUserId` is only used to trigger a refetch on login/logout — the
 * backend itself decides device- vs account-scoped based on the bearer
 * token, but this hook has no other way to know that token state changed
 * and the account's (freshly-merged) wishlist should replace what's shown. */
export function useWishlist(deviceId: string | null, authUserId: string | null = null): UseWishlistResult {
  const [wishlistProducts, setWishlistProducts] = useState<Product[]>([]);

  useEffect(() => {
    if (!deviceId) return;
    let cancelled = false;

    fetchWishlist()
      .then((products) => {
        if (!cancelled) setWishlistProducts(products);
      })
      .catch((error) => {
        console.error('Failed to load wishlist:', error);
      });

    return () => {
      cancelled = true;
    };
  }, [deviceId, authUserId]);

  const toggleWishlist = useCallback(
    (productId: string) => {
      if (!deviceId) return;

      const isCurrentlySaved = wishlistProducts.some((p) => p.id === productId);

      if (isCurrentlySaved) {
        // Removal is instantly optimistic — we already have the full object.
        setWishlistProducts((prev) => prev.filter((p) => p.id !== productId));
        removeFromWishlist(productId).catch((error) => {
          console.error('Failed to remove from wishlist:', error);
          fetchWishlist().then(setWishlistProducts).catch(() => {});
        });
      } else {
        // Adding needs the hydrated Product back from the server (the
        // caller only passed an id) — sequenced, not fired in parallel,
        // so the refetch reliably reflects the completed add.
        addToWishlist(productId)
          .then(() => fetchWishlist())
          .then(setWishlistProducts)
          .catch((error) => {
            console.error('Failed to add to wishlist:', error);
          });
      }
    },
    [deviceId, wishlistProducts]
  );

  return {
    wishlist: wishlistProducts.map((p) => p.id),
    wishlistProducts,
    toggleWishlist,
  };
}
