'use client';

import { useRef, useState } from 'react';
import { Button, Input, Textarea } from '@researchforge/ui';

const CONTACT_ADDRESS = 'info@adisoninfotech.co.uk';
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1';

// Mirrors ATTACHMENT_TYPES in app/api/v1/contact.py. Checked here too so the
// user gets an instant answer instead of waiting for a round trip.
const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
];
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ContactForm() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  // Honeypot. Hidden from humans, so anything here means a bot filled it.
  const [website, setWebsite] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  // Attachment: picked in the browser, uploaded on demand, and only then
  // referenced by storage key when the message is submitted.
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState<{ key: string; filename: string } | null>(null);

  function pickFile(selected: File | null) {
    setUploaded(null);
    if (!selected) return setFile(null);
    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setFile(null);
      return setError('Please choose a PDF or Word document.');
    }
    if (selected.size > MAX_ATTACHMENT_BYTES) {
      setFile(null);
      return setError(`That file is ${formatSize(selected.size)}. The limit is 10 MB.`);
    }
    setError(null);
    setFile(selected);
  }

  async function uploadFile() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await fetch(`${API_PREFIX}/contact/attachment`, {
        method: 'POST',
        body: form,
      });
      if (!response.ok) throw new Error('Upload failed. Please try again.');
      const data = (await response.json()) as { key: string; filename: string };
      setUploaded({ key: data.key, filename: data.filename });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError('Please enter your name.');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      return setError('Please enter a valid email address so we can reply.');
    }
    if (message.trim().length < 10) {
      return setError('Please tell us a little more — at least a sentence.');
    }

    setError(null);
    setSending(true);
    try {
      const response = await fetch(`${API_PREFIX}/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          message: message.trim(),
          website,
          attachment_key: uploaded?.key ?? null,
          attachment_name: uploaded?.filename ?? null,
        }),
      });
      if (!response.ok) {
        throw new Error(
          response.status === 429
            ? 'Too many messages sent from here. Please try again shortly.'
            : 'We could not send your message.',
        );
      }
      setSent(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} You can email us directly at ${CONTACT_ADDRESS}.`
          : `Something went wrong. Please email us at ${CONTACT_ADDRESS}.`,
      );
    } finally {
      setSending(false);
    }
  }

  if (sent) {
    return (
      <div
        role="status"
        className="mx-auto max-w-xl rounded-lg border border-[var(--rf-accent)] bg-[var(--rf-surface)] p-8 text-center"
      >
        <p className="rf-display text-2xl text-[var(--rf-accent)]">Message sent</p>
        <p className="mt-3 text-[var(--rf-muted)]">
          Thanks {name.trim().split(' ')[0]} — we&rsquo;ve got your message and will reply to{' '}
          <span className="font-medium text-[var(--rf-fg)]">{email.trim()}</span>.
        </p>
        <button
          type="button"
          onClick={() => {
            setSent(false);
            setName('');
            setEmail('');
            setMessage('');
          }}
          className="mt-5 text-sm text-[var(--rf-accent)] underline-offset-2 hover:underline"
        >
          Send another message
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto max-w-xl rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6 text-left"
      noValidate
    >
      <div className="space-y-4">
        <Input
          label="Your name"
          name="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Jane Okafor"
          autoComplete="name"
          disabled={sending}
        />
        <Input
          label="Your email"
          name="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jane@university.ac.uk"
          autoComplete="email"
          disabled={sending}
        />
        <Textarea
          label="How can we help?"
          name="message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Tell us about your research, your institution, or the plan you need…"
          rows={5}
          disabled={sending}
        />
      </div>

      <div className="mt-4 rounded-md border border-[var(--rf-border)] p-4">
        <p className="text-sm font-medium">Attach a document (optional)</p>
        <p className="mt-1 text-xs text-[var(--rf-muted)]">PDF or Word, up to 10 MB.</p>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="sr-only"
          onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          disabled={sending || uploading}
        />

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={sending || uploading}
          >
            Browse…
          </Button>

          <span className="min-w-0 flex-1 truncate text-sm text-[var(--rf-muted)]">
            {file ? `${file.name} (${formatSize(file.size)})` : 'No file chosen'}
          </span>

          {file && !uploaded ? (
            <Button size="sm" onClick={() => void uploadFile()} disabled={uploading}>
              {uploading ? 'Uploading…' : 'Upload'}
            </Button>
          ) : null}
        </div>

        {uploaded ? (
          <p className="mt-3 text-sm text-[var(--rf-accent)]" role="status">
            ✓ {uploaded.filename} attached
            <button
              type="button"
              className="ml-3 text-[var(--rf-muted)] underline-offset-2 hover:underline"
              onClick={() => {
                setUploaded(null);
                setFile(null);
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
            >
              Remove
            </button>
          </p>
        ) : null}
      </div>

      {/* Honeypot: off-screen rather than display:none, since some bots skip
          hidden inputs but not positioned ones. aria-hidden and tabIndex keep
          it away from screen readers and keyboard users. */}
      <div className="absolute left-[-9999px]" aria-hidden="true">
        <label htmlFor="website">Website</label>
        <input
          id="website"
          name="website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
        />
      </div>

      {error ? (
        <p role="alert" className="mt-4 text-sm text-[var(--rf-danger)]">
          {error}
        </p>
      ) : null}

      <div className="mt-5">
        <Button type="submit" size="lg" className="w-full" disabled={sending}>
          {sending ? 'Sending…' : 'Send message'}
        </Button>
      </div>

      <p className="mt-4 border-t border-[var(--rf-border)] pt-4 text-sm text-[var(--rf-muted)]">
        Or email us directly at{' '}
        <a
          href={`mailto:${CONTACT_ADDRESS}`}
          className="font-medium text-[var(--rf-accent)] hover:underline"
        >
          {CONTACT_ADDRESS}
        </a>
      </p>
    </form>
  );
}
