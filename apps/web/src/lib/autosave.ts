'use client';

import type { ManuscriptSection, SaveState } from '@researchforge/shared-types';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api } from './api-client';
import { dueSaves, enqueueSave, markRetry, removeQueuedSave } from './offline-queue';

const DEBOUNCE_MS = 1500;

export interface ConflictPayload {
  serverRevision: number;
  clientRevision: number;
  serverPlainText: string;
  serverStructuredContent: Record<string, unknown>;
  serverUpdatedAt: string;
}

interface UseAutosaveOptions {
  projectId: string;
  section: ManuscriptSection | null;
  onSectionUpdated: (section: ManuscriptSection, meta?: { completion?: number }) => void;
}

export function useAutosave({ projectId, section, onSectionUpdated }: UseAutosaveOptions) {
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [conflict, setConflict] = useState<ConflictPayload | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingContent = useRef<Record<string, unknown> | null>(null);
  const sectionRef = useRef(section);
  sectionRef.current = section;

  const flush = useCallback(
    async (reason: string, content?: Record<string, unknown>) => {
      const current = sectionRef.current;
      const structured = content ?? pendingContent.current;
      if (!current || !structured) return;
      if (timer.current) {
        clearTimeout(timer.current);
        timer.current = null;
      }

      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        enqueueSave({
          projectId,
          sectionId: current.id,
          payload: {
            structured_content: structured,
            expected_revision: current.revision_number,
            reason,
          },
          etag: current.etag,
        });
        setSaveState('offline');
        return;
      }

      setSaveState('saving');
      setErrorMessage(null);
      try {
        const result = await api.saveSection(
          projectId,
          current.id,
          {
            structured_content: structured,
            expected_revision: current.revision_number,
            reason,
            create_snapshot:
              reason === 'shortcut' || reason === 'before_ai' || reason === 'after_ai',
          },
          current.etag,
        );
        pendingContent.current = null;
        setConflict(null);
        setSaveState('saved');
        setLastSavedAt(new Date().toISOString());
        onSectionUpdated(result.section, { completion: result.completion_percent });
      } catch (err) {
        if (err instanceof ApiError && err.status === 409 && err.code === 'conflict') {
          setSaveState('conflict');
          setConflict({
            serverRevision: Number(err.details.server_revision ?? 0),
            clientRevision: Number(err.details.client_revision ?? current.revision_number),
            serverPlainText: String(err.details.server_plain_text ?? ''),
            serverStructuredContent: (err.details.server_structured_content ?? {}) as Record<
              string,
              unknown
            >,
            serverUpdatedAt: String(err.details.server_updated_at ?? ''),
          });
          return;
        }
        if (typeof navigator !== 'undefined' && !navigator.onLine) {
          enqueueSave({
            projectId,
            sectionId: current.id,
            payload: {
              structured_content: structured,
              expected_revision: current.revision_number,
              reason,
            },
            etag: current.etag,
          });
          setSaveState('offline');
          return;
        }
        setSaveState('error');
        setErrorMessage(err instanceof Error ? err.message : 'Save failed');
      }
    },
    [onSectionUpdated, projectId],
  );

  const schedule = useCallback(
    (content: Record<string, unknown>) => {
      pendingContent.current = content;
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        void flush('autosave', content);
      }, DEBOUNCE_MS);
    },
    [flush],
  );

  const saveNow = useCallback(
    (reason: string, content?: Record<string, unknown>) => flush(reason, content),
    [flush],
  );

  const acceptServer = useCallback(() => {
    if (!conflict || !sectionRef.current) return;
    onSectionUpdated({
      ...sectionRef.current,
      revision_number: conflict.serverRevision,
      plain_text: conflict.serverPlainText,
      structured_content: conflict.serverStructuredContent,
      updated_at: conflict.serverUpdatedAt,
      etag: `W/"${sectionRef.current.id}:${conflict.serverRevision}"`,
    });
    setConflict(null);
    setSaveState('saved');
    pendingContent.current = null;
  }, [conflict, onSectionUpdated]);

  const overwriteServer = useCallback(async () => {
    if (!conflict || !sectionRef.current || !pendingContent.current) return;
    // Align revision to server then retry with client content (explicit user choice).
    const aligned = {
      ...sectionRef.current,
      revision_number: conflict.serverRevision,
      etag: `W/"${sectionRef.current.id}:${conflict.serverRevision}"`,
    };
    sectionRef.current = aligned;
    onSectionUpdated(aligned);
    setConflict(null);
    await flush('shortcut', pendingContent.current);
  }, [conflict, flush, onSectionUpdated]);

  useEffect(() => {
    const onOnline = () => {
      void (async () => {
        for (const item of dueSaves()) {
          try {
            const result = await api.saveSection(
              item.projectId,
              item.sectionId,
              item.payload,
              item.etag,
            );
            removeQueuedSave(item.id);
            if (item.sectionId === sectionRef.current?.id) {
              onSectionUpdated(result.section, { completion: result.completion_percent });
              setSaveState('saved');
              setLastSavedAt(new Date().toISOString());
            }
          } catch (err) {
            const status = err instanceof ApiError ? err.status : 0;
            if (status === 409) {
              // Conflict: drop stale offline revision — never silently overwrite.
              removeQueuedSave(item.id);
              if (item.sectionId === sectionRef.current?.id) {
                const details =
                  err instanceof ApiError
                    ? (err.details as Record<string, unknown> | undefined)
                    : undefined;
                setSaveState('conflict');
                setConflict({
                  serverRevision: Number(
                    details?.server_revision ?? item.payload.expected_revision,
                  ),
                  clientRevision: item.payload.expected_revision,
                  serverPlainText: String(details?.server_plain_text ?? ''),
                  serverStructuredContent: (details?.server_structured_content || {}) as Record<
                    string,
                    unknown
                  >,
                  serverUpdatedAt: String(details?.server_updated_at ?? ''),
                });
                setErrorMessage(
                  'Offline save conflicted with a newer server revision. Choose Accept server or Overwrite.',
                );
              }
              continue;
            }
            markRetry(item.id);
            setSaveState('offline');
          }
        }
      })();
    };
    window.addEventListener('online', onOnline);
    const interval = setInterval(onOnline, 5000);
    return () => {
      window.removeEventListener('online', onOnline);
      clearInterval(interval);
    };
  }, [onSectionUpdated]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        void saveNow('shortcut');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [saveNow]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return {
    saveState,
    lastSavedAt,
    errorMessage,
    conflict,
    schedule,
    saveNow,
    acceptServer,
    overwriteServer,
  };
}
