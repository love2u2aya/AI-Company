import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const BAND = {
  component: 'AbovePrompt',
  requestId: 'above-prompt',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 20,
    bodyColumns: 80,
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

/** Stand in for the engine beneath the plugin at the turn's end. */
const engine = (on: On) => {
  mock.clock(on)
  on('turn.complete', (_$, e) => ({ text: e.answer }))
  // The engine's own band: empty.
  on('ui.render', ($, e) => {
    const { Box } = $.ui.resolve(e)
    return <Box />
  })
}

const finish = (answer: string) =>
  ({ answer, durationMs: 1000, isAborted: false, turnId: 't1', reason: 'answer' }) as const

test('a 選択肢 line becomes buttons, and pressing one sends it as the answer', async ($, on) => {
  engine(on)
  const sent: string[] = []
  on('prompt.submit', (_$, e) => {
    sent.push(e.text)
    return { text: e.text }
  })

  for (const surface of ['terminal', 'desktop'] as const) {
    await $.turn.complete(finish('台本の方向性を決めたいです。\n\n選択肢: A案でいく / B案でいく / もう少し考える'))
    const ui = await $.ui.mount({ plugin: 'choice-buttons', surface, ...BAND })

    expect(await ui.find({ key: 'option-1' })).toBeDefined()
    expect(await ui.find({ key: 'option-3' })).toBeDefined()
    expect(await ui.find({ text: /B案でいく/ })).toBeDefined()

    await ui.press({ key: 'option-2' })
    expect(sent.at(-1)).toBe('B案でいく')
    // Answered: the band is empty again.
    expect(await ui.find({ key: 'option-1' })).toBeUndefined()
    await ui.unmount()
  }
})

test('a closed question gets はい and いいえ', async ($, on) => {
  engine(on)
  const sent: string[] = []
  on('prompt.submit', (_$, e) => {
    sent.push(e.text)
    return { text: e.text }
  })

  await $.turn.complete(finish('サムネイルを作り直しました。\nこのままアップロードしてよいですか？'))
  const ui = await $.ui.mount({ plugin: 'choice-buttons', surface: 'terminal', ...BAND })
  expect(await ui.find({ text: /はい/ })).toBeDefined()
  expect(await ui.find({ text: /いいえ/ })).toBeDefined()
  await ui.press({ key: 'option-1' })
  expect(sent.at(-1)).toBe('はい')
  await ui.unmount()
})

test('a numbered list after a question becomes numbered buttons', async ($, on) => {
  engine(on)
  const sent: string[] = []
  on('prompt.submit', (_$, e) => {
    sent.push(e.text)
    return { text: e.text }
  })

  await $.turn.complete(finish('どちらで進めますか？\n\n1. **新NISA特集**\n   - 検索数が多い\n2. 年金の話\n3. 保険の見直し'))
  const ui = await $.ui.mount({ plugin: 'choice-buttons', surface: 'terminal', ...BAND })
  expect(await ui.find({ key: 'option-3' })).toBeDefined()
  expect(await ui.find({ key: 'option-4' })).toBeUndefined()
  await ui.press({ key: 'option-1' })
  expect(sent.at(-1)).toBe('1. 新NISA特集')
  await ui.unmount()
})

test('open questions, plain reports and running turns show no buttons', async ($, on) => {
  engine(on)
  for (const text of ['動画のテーマは何にしますか？', '書き出しが完了しました。']) {
    await $.turn.complete(finish(text))
    const ui = await $.ui.mount({ plugin: 'choice-buttons', surface: 'terminal', ...BAND })
    expect(await ui.find({ key: 'option-1' })).toBeUndefined()
    await ui.unmount()
  }

  await $.turn.complete(finish('進めてよいですか？'))
  const working = await $.ui.mount({
    plugin: 'choice-buttons',
    surface: 'terminal',
    ...BAND,
    props: { ...BAND.props, isWorking: true },
  })
  expect(await working.find({ key: 'option-1' })).toBeUndefined()
  await working.unmount()
})

test('閉じる and a typed answer both clear the buttons', async ($, on) => {
  engine(on)
  on('prompt.submit', (_$, e) => ({ text: e.text }))

  await $.turn.complete(finish('公開してよいですか？'))
  const ui = await $.ui.mount({ plugin: 'choice-buttons', surface: 'terminal', ...BAND })
  await ui.press({ key: 'dismiss' })
  expect(await ui.find({ key: 'option-1' })).toBeUndefined()
  await ui.unmount()

  await $.turn.complete(finish('公開してよいですか？'))
  await $.prompt.submit({ text: '明日にして', wait: false, origin: { kind: 'composer' } })
  const again = await $.ui.mount({ plugin: 'choice-buttons', surface: 'terminal', ...BAND })
  expect(await again.find({ key: 'option-1' })).toBeUndefined()
  await again.unmount()
})

test('the system prompt tells Claude how to offer buttons', async ($, on) => {
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'hi', scope: 'shared' }] }))
  const composed = await $.prompt.compose({
    model: 'm',
    promptModel: 'm',
    surfaces: ['terminal'],
    tools: [],
    outputStyle: null,
    traits: [],
  })
  expect(composed.sections.at(-1)?.text).toMatch(/選択肢: はい \/ いいえ/)
})
