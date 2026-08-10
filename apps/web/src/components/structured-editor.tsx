'use client';

import type { ManuscriptSection } from '@researchforge/shared-types';
import { EditorContent, useEditor } from '@tiptap/react';
import { useEffect } from 'react';
import { docToPlain, emptyDoc, manuscriptExtensions } from '@/lib/editor-extensions';

interface StructuredEditorProps {
  section: ManuscriptSection;
  onChange: (structured: Record<string, unknown>, plain: string) => void;
  disabled?: boolean;
}

export function StructuredEditor({ section, onChange, disabled }: StructuredEditorProps) {
  const editor = useEditor({
    extensions: manuscriptExtensions,
    content: (section.structured_content as object) || emptyDoc(),
    editable: !disabled,
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          'prose prose-sm max-w-none min-h-[280px] rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-4 py-3 focus:outline-none',
        'aria-label': section.title,
      },
    },
    onUpdate: ({ editor: current }) => {
      const json = current.getJSON() as Record<string, unknown>;
      const withPlain = { ...json, plain_text: docToPlain(json) };
      onChange(withPlain, withPlain.plain_text as string);
    },
  });

  useEffect(() => {
    if (!editor) return;
    const current = JSON.stringify(editor.getJSON());
    const incoming = JSON.stringify(section.structured_content || emptyDoc());
    if (current !== incoming) {
      editor.commands.setContent((section.structured_content as object) || emptyDoc(), false);
    }
  }, [editor, section.id, section.revision_number, section.structured_content]);

  useEffect(() => {
    editor?.setEditable(!disabled);
  }, [disabled, editor]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <ToolbarButton
          label="H2"
          onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
        />
        <ToolbarButton label="Bold" onClick={() => editor?.chain().focus().toggleBold().run()} />
        <ToolbarButton
          label="Italic"
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        />
        <ToolbarButton
          label="List"
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        />
        <ToolbarButton
          label="Ordered"
          onClick={() => editor?.chain().focus().toggleOrderedList().run()}
        />
        <ToolbarButton
          label="Figure"
          onClick={() =>
            editor
              ?.chain()
              .focus()
              .insertContent({ type: 'figurePlaceholder', attrs: { caption: 'Figure' } })
              .run()
          }
        />
        <ToolbarButton
          label="Equation"
          onClick={() =>
            editor
              ?.chain()
              .focus()
              .insertContent({ type: 'equationPlaceholder', attrs: { latex: 'E = mc^2' } })
              .run()
          }
        />
        <ToolbarButton
          label="Citation"
          onClick={() =>
            editor
              ?.chain()
              .focus()
              .insertContent({ type: 'citation', attrs: { citeKey: 'author2024' } })
              .run()
          }
        />
        <ToolbarButton
          label="Comment"
          onClick={() =>
            editor
              ?.chain()
              .focus()
              .insertContent({ type: 'commentPlaceholder', attrs: { note: 'Review' } })
              .run()
          }
        />
        <ToolbarButton
          label="Table"
          onClick={() =>
            editor
              ?.chain()
              .focus()
              .insertContent({
                type: 'simpleTable',
                content: [{ type: 'text', text: 'Col A | Col B' }],
              })
              .run()
          }
        />
      </div>
      <EditorContent editor={editor} />
      <p className="text-xs text-[var(--rf-muted)]">{section.word_count} words in this section</p>
    </div>
  );
}

function ToolbarButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="rounded border border-[var(--rf-border)] px-2 py-1 text-xs hover:bg-[var(--rf-surface-2)]"
      onClick={onClick}
    >
      {label}
    </button>
  );
}
