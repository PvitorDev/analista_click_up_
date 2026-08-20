'use client'

import { type ReactNode } from 'react'

function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g
  let last = 0
  let i = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith('**')) {
      parts.push(
        <strong key={i} className="font-semibold">
          {tok.slice(2, -2)}
        </strong>,
      )
    } else if (tok.startsWith('`')) {
      parts.push(
        <code
          key={i}
          className="rounded bg-black/25 px-1 py-0.5 font-mono text-[0.85em]"
        >
          {tok.slice(1, -1)}
        </code>,
      )
    } else {
      parts.push(
        <em key={i} className="italic">
          {tok.slice(1, -1)}
        </em>,
      )
    }
    i += 1
    last = m.index + tok.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

const HEADING_CLASS: Record<number, string> = {
  1: 'text-base font-semibold tracking-tight',
  2: 'text-[0.95rem] font-semibold tracking-tight',
  3: 'text-sm font-semibold',
  4: 'text-sm font-medium text-foreground/90',
}

export function ChatMarkdown({ text }: { text: string }) {
  const lines = (text || '').replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let list: { kind: 'ul' | 'ol'; items: string[] } | null = null
  let para: string[] = []

  function flushPara() {
    if (!para.length) return
    blocks.push(
      <p key={`p-${blocks.length}`} className="whitespace-pre-wrap break-words">
        {inline(para.join('\n'))}
      </p>,
    )
    para = []
  }

  function flushList() {
    if (!list) return
    const Tag = list.kind === 'ol' ? 'ol' : 'ul'
    const cls = list.kind === 'ol' ? 'list-decimal' : 'list-disc'
    blocks.push(
      <Tag key={`l-${blocks.length}`} className={`${cls} space-y-1 pl-4`}>
        {list.items.map((item, i) => (
          <li key={i} className="break-words">
            {inline(item)}
          </li>
        ))}
      </Tag>,
    )
    list = null
  }

  for (const line of lines) {
    const heading = line.match(/^(#{1,4})\s+(.+)\s*$/)
    if (heading) {
      flushPara()
      flushList()
      const level = heading[1].length
      const Tag = `h${level}` as 'h1' | 'h2' | 'h3' | 'h4'
      blocks.push(
        <Tag key={`h-${blocks.length}`} className={HEADING_CLASS[level]}>
          {inline(heading[2])}
        </Tag>,
      )
      continue
    }
    if (/^\s*-{3,}\s*$/.test(line)) {
      flushPara()
      flushList()
      blocks.push(
        <hr key={`hr-${blocks.length}`} className="my-1 border-white/15" />,
      )
      continue
    }
    const ul = line.match(/^\s*[-•]\s+(.+)/)
    const starList = line.match(/^\s*\*\s+(.+)/)
    const ol = line.match(/^\s*\d+[.)]\s+(.+)/)
    const item = ul?.[1] ?? starList?.[1]
    if (item) {
      flushPara()
      if (!list || list.kind !== 'ul') {
        flushList()
        list = { kind: 'ul', items: [] }
      }
      list.items.push(item)
      continue
    }
    if (ol) {
      flushPara()
      if (!list || list.kind !== 'ol') {
        flushList()
        list = { kind: 'ol', items: [] }
      }
      list.items.push(ol[1])
      continue
    }
    flushList()
    if (!line.trim()) {
      flushPara()
    } else {
      para.push(line)
    }
  }
  flushList()
  flushPara()

  if (!blocks.length) return null
  return <div className="grid gap-2 text-[0.9375rem] leading-6">{blocks}</div>
}
