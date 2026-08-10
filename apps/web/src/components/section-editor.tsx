'use client';

import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { useEffect } from 'react';

interface SectionEditorProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
}

export function SectionEditor({
  value,
  onChange,
  label = 'Temporary section editor',
}: SectionEditorProps) {
  const editor = useEditor({
    extensions: [StarterKit],
    content: value || '<p></p>',
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          'prose prose-sm max-w-none min-h-40 rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3 py-2 focus:outline-none',
        'aria-label': label,
      },
    },
    onUpdate: ({ editor: current }) => {
      onChange(current.getHTML());
    },
  });

  useEffect(() => {
    if (!editor) return;
    if (value !== editor.getHTML()) {
      editor.commands.setContent(value || '<p></p>', false);
    }
  }, [editor, value]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded border border-[var(--rf-border)] px-2 py-1 text-xs"
          onClick={() => editor?.chain().focus().toggleBold().run()}
        >
          Bold
        </button>
        <button
          type="button"
          className="rounded border border-[var(--rf-border)] px-2 py-1 text-xs"
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        >
          Italic
        </button>
        <button
          type="button"
          className="rounded border border-[var(--rf-border)] px-2 py-1 text-xs"
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        >
          List
        </button>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
