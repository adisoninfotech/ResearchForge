/** Browser offline queue for manuscript section saves with exponential backoff. */

export interface QueuedSave {
  id: string;
  projectId: string;
  sectionId: string;
  payload: {
    structured_content: Record<string, unknown>;
    expected_revision: number;
    title?: string;
    reason?: string;
    create_snapshot?: boolean;
    snapshot_summary?: string;
  };
  etag?: string;
  attempts: number;
  nextAttemptAt: number;
  createdAt: number;
}

const KEY = 'researchforge.offlineSaves.v1';
const MAX_ATTEMPTS = 8;

function readAll(): QueuedSave[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    return JSON.parse(raw) as QueuedSave[];
  } catch {
    return [];
  }
}

function writeAll(items: QueuedSave[]) {
  localStorage.setItem(KEY, JSON.stringify(items));
}

export function enqueueSave(
  item: Omit<QueuedSave, 'id' | 'attempts' | 'nextAttemptAt' | 'createdAt'>,
) {
  const queue = readAll().filter(
    (q) => !(q.projectId === item.projectId && q.sectionId === item.sectionId),
  );
  queue.push({
    ...item,
    id: `${item.sectionId}-${Date.now()}`,
    attempts: 0,
    nextAttemptAt: Date.now(),
    createdAt: Date.now(),
  });
  writeAll(queue);
}

export function listQueuedSaves(): QueuedSave[] {
  return readAll();
}

export function removeQueuedSave(id: string) {
  writeAll(readAll().filter((q) => q.id !== id));
}

export function backoffMs(attempts: number): number {
  return Math.min(60_000, 500 * 2 ** attempts);
}

export function markRetry(id: string) {
  const queue = readAll();
  const next = queue
    .map((q) => {
      if (q.id !== id) return q;
      const attempts = q.attempts + 1;
      if (attempts >= MAX_ATTEMPTS) return null;
      return {
        ...q,
        attempts,
        nextAttemptAt: Date.now() + backoffMs(attempts),
      };
    })
    .filter(Boolean) as QueuedSave[];
  writeAll(next);
}

export function dueSaves(now = Date.now()): QueuedSave[] {
  return readAll().filter((q) => q.nextAttemptAt <= now);
}
