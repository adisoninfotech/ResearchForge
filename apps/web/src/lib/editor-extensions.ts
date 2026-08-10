import { Node, mergeAttributes } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';

const FigurePlaceholder = Node.create({
  name: 'figurePlaceholder',
  group: 'block',
  atom: true,
  addAttributes() {
    return {
      caption: { default: 'Figure placeholder' },
      stableId: { default: null },
      number: { default: null },
      source: { default: null },
      provenance: { default: null },
      altText: { default: null },
      title: { default: null },
      isConceptual: { default: false },
    };
  },
  parseHTML() {
    return [{ tag: 'div[data-type="figure-placeholder"]' }];
  },
  renderHTML({ HTMLAttributes }) {
    const label = HTMLAttributes.caption || 'Figure placeholder';
    const provenance = HTMLAttributes.provenance ? ` [${HTMLAttributes.provenance}]` : '';
    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'figure-placeholder',
        'data-stable-id': HTMLAttributes.stableId || undefined,
        class: 'rf-figure-placeholder',
        role: 'img',
        'aria-label': HTMLAttributes.altText || label,
      }),
      ['span', {}, `${label}${provenance}`],
    ];
  },
});

const EquationPlaceholder = Node.create({
  name: 'equationPlaceholder',
  group: 'block',
  atom: true,
  addAttributes() {
    return {
      latex: { default: 'E = mc^2' },
    };
  },
  parseHTML() {
    return [{ tag: 'div[data-type="equation-placeholder"]' }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'equation-placeholder',
        class: 'rf-equation-placeholder',
      }),
      ['code', {}, HTMLAttributes.latex || 'equation'],
    ];
  },
});

const CitationNode = Node.create({
  name: 'citation',
  group: 'inline',
  inline: true,
  atom: true,
  addAttributes() {
    return {
      citeKey: { default: 'author2024' },
    };
  },
  parseHTML() {
    return [{ tag: 'span[data-type="citation"]' }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'citation',
        class: 'rf-citation',
      }),
      `[${HTMLAttributes.citeKey || 'cite'}]`,
    ];
  },
});

const CommentPlaceholder = Node.create({
  name: 'commentPlaceholder',
  group: 'inline',
  inline: true,
  atom: true,
  addAttributes() {
    return {
      note: { default: 'Comment' },
    };
  },
  parseHTML() {
    return [{ tag: 'span[data-type="comment-placeholder"]' }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-type': 'comment-placeholder',
        class: 'rf-comment-placeholder',
      }),
      `[note: ${HTMLAttributes.note || 'Comment'}]`,
    ];
  },
});

/** Simple table as HTML table node without extra TipTap table package. */
const SimpleTable = Node.create({
  name: 'simpleTable',
  group: 'block',
  content: 'text*',
  addAttributes() {
    return {
      stableId: { default: null },
      number: { default: null },
      caption: { default: null },
      source: { default: null },
      provenance: { default: null },
      title: { default: null },
    };
  },
  parseHTML() {
    return [{ tag: 'table' }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'table',
      mergeAttributes(HTMLAttributes, {
        class: 'rf-simple-table',
        'data-stable-id': HTMLAttributes.stableId || undefined,
      }),
      ['tbody', {}, ['tr', {}, ['td', {}, 0]]],
    ];
  },
});

export const manuscriptExtensions = [
  StarterKit.configure({
    heading: { levels: [1, 2, 3] },
  }),
  FigurePlaceholder,
  EquationPlaceholder,
  CitationNode,
  CommentPlaceholder,
  SimpleTable,
];

export function emptyDoc() {
  return {
    type: 'doc',
    content: [{ type: 'paragraph' }],
  };
}

export function docToPlain(doc: Record<string, unknown>): string {
  const walk = (node: unknown): string => {
    if (!node || typeof node !== 'object') return '';
    const n = node as { type?: string; text?: string; content?: unknown[] };
    if (n.type === 'text') return n.text || '';
    if (Array.isArray(n.content)) return n.content.map(walk).join(' ');
    return '';
  };
  return walk(doc).replace(/\s+/g, ' ').trim();
}
