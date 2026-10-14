import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Choice, Option } from '../types'

const choice = atom({ plugin: 'choice-buttons', key: 'choice' } as const, null)

/** Hotkeys are one digit each, so at most nine buttons. */
const MAX_OPTIONS = 9
const LABEL_MAX = 30

/** The line Claude writes when it asks for a choice: `選択肢: はい / いいえ`. */
const MARKER = /^(?:[-*>]\s*)?\**(?:選択肢|choices?)\**\s*[:：]\s*\**(.+?)\**$/i
const SEPARATOR = /\s*[/／|｜]\s*/
/** A numbered option: `1. A案`, `2) B案`, `③ C案`. */
const NUMBERED = /^\s*(?:[-*]\s*)?\**\s*(?:(\d{1,2})\s*[.)．、:：]|([①-⑨]))\s*\**\s*(.+)$/
const QUESTION = /[?？]\s*\**\s*$/
/** Words that make a question open (what, which, how...), so はい／いいえ would not answer it. */
const OPEN_QUESTION = /何|なに|どれ|どの|どこ|どう|どんな|どちら|いつ|誰|だれ|なぜ|いくつ|いくら|教えて|\b(what|which|how|when|where|who|why)\b/i
const YES_NO_EN = /^(should|shall|do|does|did|is|are|can|could|would|will|want|may)\b/i

const SYSTEM_GUIDE = [
  '# 選択肢ボタン（choice-buttons mod）',
  '社長（ユーザー）に選択を求めて返答を終えるときは、返答の最後の行を次の形にする。',
  'プロンプトの上にボタンが出て、社長は押すだけで答えられる。',
  '',
  '選択肢: はい / いいえ',
  '',
  '- 選択肢は2〜9個、それぞれ20文字以内で、「/」で区切る。押した選択肢の文字がそのまま社長の返答になる。',
  '- 選択を求めないときはこの行を書かない。AskUserQuestion ツールで聞くときも書かない。',
].join('\n')

type Dollar = EngineInterface

// ---------- reading the choice out of an answer ----------

const tidy = (text: string) => text.replace(/\*\*|__|`/g, '').replace(/\s+/g, ' ').trim()

const clip = (text: string) => (text.length > LABEL_MAX ? `${text.slice(0, LABEL_MAX - 1)}…` : text)

const toOptions = (texts: string[]): Option[] =>
  texts.slice(0, MAX_OPTIONS).map(text => ({ label: clip(text), send: text }))

/** The `選択肢:` line among the last few lines. */
const fromMarker = (lines: string[]): Choice | null => {
  for (const line of lines.slice(-3).reverse()) {
    const m = MARKER.exec(line)
    if (m === null) continue
    const texts = (m[1] ?? '').split(SEPARATOR).map(tidy).filter(Boolean)
    if (texts.length >= 2) return { options: toOptions(texts) }
  }
  return null
}

/** The last numbered list, when a question comes right before it or ends the answer. */
const fromNumbered = (lines: string[]): Choice | null => {
  let end = -1
  for (let i = lines.length - 1; i >= Math.max(0, lines.length - 15); i--) {
    if (NUMBERED.test(lines[i] ?? '')) {
      end = i
      break
    }
  }
  if (end < 0) return null

  // Walk up the list; a line that is not an item (an option's own detail) is passed over.
  const items: string[] = []
  let start = end
  for (let i = end; i >= 0; i--) {
    const line = lines[i] ?? ''
    const m = NUMBERED.exec(line)
    if (m !== null) {
      items.unshift(tidy(m[3] ?? ''))
      start = i
      if (m[1] === '1' || m[2] === '①') break
    } else if (!/^\s|^[-*・]/.test(line)) {
      break
    }
  }
  if (items.length < 2) return null

  const before = lines[start - 1] ?? ''
  const isAsked = QUESTION.test(before) || QUESTION.test(lines.at(-1) ?? '')
  if (!isAsked) return null

  return { options: toOptions(items.map((text, i) => `${i + 1}. ${text}`)) }
}

/** A closed question at the very end: はい／いいえ. */
const fromYesNo = (lines: string[]): Choice | null => {
  const last = tidy(lines.at(-1) ?? '')
  if (!QUESTION.test(last) || OPEN_QUESTION.test(last)) return null
  const isClosed = /か[?？]$/.test(last) || YES_NO_EN.test(last)
  return isClosed ? { options: toOptions(['はい', 'いいえ']) } : null
}

export const choiceIn = (answer: string): Choice | null => {
  const lines = answer.split('\n').map(line => line.trimEnd()).filter(line => line.trim() !== '')
  if (lines.length === 0) return null
  const trimmed = lines.map(line => line.trim())
  return fromMarker(trimmed) ?? fromNumbered(lines) ?? fromYesNo(trimmed)
}

// ---------- answering ----------

const answer = async ($: Dollar, option: Option) => {
  await update($, choice, () => null)
  await $.prompt.submit({ text: option.send, asUser: true })
}

const dismiss = ($: Dollar) => update($, choice, () => null)

// ---------- hooks ----------

export const register: Register = on => {
  on('prompt.compose', async ($, e, next) => {
    const composed = await next(e)
    return {
      sections: [...composed.sections, { id: 'choice-buttons:guide', text: SYSTEM_GUIDE, scope: 'session' }],
    }
  })

  // Whatever the person sends next (typed or a button), the old choice is answered.
  on('prompt.submit', async ($, e, next) => {
    if (!e.isMeta) await update($, choice, () => null)
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      const found = e.reason === 'answer' ? choiceIn(e.answer) : null
      await update($, choice, () => found)
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const current = await read($, choice)
    if (current === null || e.props.hasSurvey || e.props.isWorking) {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)

    return (
      <Box flexDirection="column">
        <Text dimColor>押して答える（入力欄が空なら数字キーでも押せます）</Text>
        <Box flexDirection="row" flexWrap="wrap" columnGap={1}>
          {current.options.map((option, i) => (
            <Button
              key={`option-${i + 1}`}
              label={`${i + 1} ${option.label}`}
              hotkey={String(i + 1)}
              variant={i === 0 ? 'primary' : undefined}
              onPress={() => answer($, option)}
            />
          ))}
          <Button key="dismiss" label="閉じる" role="dismiss" dimColor onPress={() => dismiss($)} />
        </Box>
      </Box>
    )
  })
}
