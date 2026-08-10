import { afterEach, describe, expect, it } from 'vitest';
import { GUEST_STORAGE_KEY } from '@researchforge/shared-types';
import {
  clearGuestDraft,
  emptyGuestDraft,
  guestDraftToTransferPayload,
  loadGuestDraft,
  saveGuestDraft,
} from './guest-storage';

describe('guest storage', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('returns empty draft when nothing stored', () => {
    const draft = loadGuestDraft();
    expect(draft.title).toBe('');
    expect(draft.outline).toEqual([]);
    expect(draft.conversionKey).toBeTruthy();
  });

  it('persists and reloads a draft', () => {
    const draft = {
      ...emptyGuestDraft(),
      title: 'Test paper',
      researchArea: 'Biology',
      sectionContent: '<p>Hello</p>',
    };
    saveGuestDraft(draft);
    expect(window.localStorage.getItem(GUEST_STORAGE_KEY)).toContain('Test paper');
    const loaded = loadGuestDraft();
    expect(loaded.title).toBe('Test paper');
    expect(loaded.researchArea).toBe('Biology');
    expect(loaded.conversionKey).toBe(draft.conversionKey);
  });

  it('clears temporary draft', () => {
    saveGuestDraft({ ...emptyGuestDraft(), title: 'X' });
    clearGuestDraft();
    expect(window.localStorage.getItem(GUEST_STORAGE_KEY)).toBeNull();
  });

  it('maps draft to transfer payload with conversion key', () => {
    const draft = { ...emptyGuestDraft(), title: 'Mapped', conversionKey: 'key-12345678' };
    const payload = guestDraftToTransferPayload(draft);
    expect(payload.guest_conversion_key).toBe('key-12345678');
    expect(payload.title).toBe('Mapped');
  });
});
