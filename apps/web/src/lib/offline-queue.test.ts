import { beforeEach, describe, expect, it } from 'vitest';
import {
  backoffMs,
  enqueueSave,
  listQueuedSaves,
  markRetry,
  removeQueuedSave,
} from './offline-queue';

describe('offline queue', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('enqueues and dedupes by section', () => {
    enqueueSave({
      projectId: 'p1',
      sectionId: 's1',
      payload: {
        structured_content: { type: 'doc' },
        expected_revision: 1,
      },
    });
    enqueueSave({
      projectId: 'p1',
      sectionId: 's1',
      payload: {
        structured_content: { type: 'doc', content: [] },
        expected_revision: 1,
      },
    });
    expect(listQueuedSaves()).toHaveLength(1);
  });

  it('retries with exponential backoff and drops after max attempts', () => {
    enqueueSave({
      projectId: 'p1',
      sectionId: 's1',
      payload: {
        structured_content: { type: 'doc' },
        expected_revision: 1,
      },
    });
    const id = listQueuedSaves()[0]!.id;
    expect(backoffMs(0)).toBe(500);
    expect(backoffMs(3)).toBe(4000);
    for (let i = 0; i < 8; i += 1) {
      markRetry(id);
    }
    expect(listQueuedSaves()).toHaveLength(0);
  });

  it('removes queued items', () => {
    enqueueSave({
      projectId: 'p1',
      sectionId: 's1',
      payload: {
        structured_content: { type: 'doc' },
        expected_revision: 1,
      },
    });
    const id = listQueuedSaves()[0]!.id;
    removeQueuedSave(id);
    expect(listQueuedSaves()).toHaveLength(0);
  });
});
