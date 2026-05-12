export type NavigationOriginState = {
  from: string;
  backLabel: string;
  scrollKey?: string;
  itemId?: number;
};

export type NavigationRestoreState = {
  restoreScrollKey?: string;
  restoreItemId?: number;
};

type StoredScrollPosition = {
  top: number;
  itemId?: number;
};

const SCROLL_STORAGE_PREFIX = "clinical-data-scroll:";

function storageKey(scrollKey: string) {
  return `${SCROLL_STORAGE_PREFIX}${scrollKey}`;
}

export function buildRestoreState(origin?: NavigationOriginState | null): NavigationRestoreState | undefined {
  if (!origin?.scrollKey) return undefined;
  return {
    restoreScrollKey: origin.scrollKey,
    restoreItemId: origin.itemId,
  };
}

export function saveScrollPosition(scrollKey: string, itemId?: number) {
  if (typeof window === "undefined") return;
  const payload: StoredScrollPosition = {
    top: window.scrollY,
    itemId,
  };
  window.sessionStorage.setItem(storageKey(scrollKey), JSON.stringify(payload));
}

export function restoreScrollPosition(scrollKey: string, itemId?: number) {
  if (typeof window === "undefined") return;
  const raw = window.sessionStorage.getItem(storageKey(scrollKey));
  window.sessionStorage.removeItem(storageKey(scrollKey));
  const fallbackItemId = itemId;
  if (!raw) {
    if (fallbackItemId) {
      document.getElementById(`subject-item-${fallbackItemId}`)?.scrollIntoView({ block: "center" });
    }
    return;
  }
  try {
    const payload = JSON.parse(raw) as StoredScrollPosition;
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: payload.top, behavior: "auto" });
      const targetItemId = payload.itemId ?? fallbackItemId;
      if (targetItemId) {
        document.getElementById(`subject-item-${targetItemId}`)?.scrollIntoView({ block: "center" });
      }
    });
  } catch {
    if (fallbackItemId) {
      document.getElementById(`subject-item-${fallbackItemId}`)?.scrollIntoView({ block: "center" });
    }
  }
}
