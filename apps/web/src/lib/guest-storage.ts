import {
  GUEST_PENDING_SAVE_KEY,
  GUEST_STORAGE_KEY,
  type GuestDraft,
  type OutlineSection,
} from '@researchforge/shared-types';

function newConversionKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export const emptyGuestDraft = (): GuestDraft => ({
  title: '',
  researchArea: '',
  targetFormat: 'IEEE',
  researchProblem: '',
  proposedContribution: '',
  outline: [],
  sectionContent: '',
  conversionKey: newConversionKey(),
  updatedAt: new Date().toISOString(),
});

export function loadGuestDraft(): GuestDraft {
  if (typeof window === 'undefined') return emptyGuestDraft();
  try {
    const raw = window.localStorage.getItem(GUEST_STORAGE_KEY);
    if (!raw) return emptyGuestDraft();
    const parsed = JSON.parse(raw) as Partial<GuestDraft>;
    return {
      ...emptyGuestDraft(),
      ...parsed,
      conversionKey: parsed.conversionKey || newConversionKey(),
      outline: Array.isArray(parsed.outline) ? (parsed.outline as OutlineSection[]) : [],
    };
  } catch {
    return emptyGuestDraft();
  }
}

export function saveGuestDraft(draft: GuestDraft): void {
  if (typeof window === 'undefined') return;
  const payload: GuestDraft = { ...draft, updatedAt: new Date().toISOString() };
  window.localStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(payload));
}

export function clearGuestDraft(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(GUEST_STORAGE_KEY);
}

export function markGuestSavePending(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(GUEST_PENDING_SAVE_KEY, '1');
}

export function clearGuestSavePending(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(GUEST_PENDING_SAVE_KEY);
}

export function isGuestSavePending(): boolean {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(GUEST_PENDING_SAVE_KEY) === '1';
}

export function guestDraftToTransferPayload(draft: GuestDraft): Record<string, unknown> {
  return {
    title: draft.title || 'Untitled manuscript',
    research_area: draft.researchArea,
    target_format: draft.targetFormat,
    research_problem: draft.researchProblem,
    proposed_contribution: draft.proposedContribution,
    outline: draft.outline,
    draft_content: { sectionContent: draft.sectionContent },
    contains_synthetic_data: false,
    guest_conversion_key: draft.conversionKey,
  };
}
