import { expect, mock, test } from 'claude-code/testing'

const PANE = {
  component: 'Pane',
  requestId: 'control-panel',
  props: {
    title: 'コントロールパネル',
    isFocused: true,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

test('an idle session says nothing runs', async ($, on) => {
  mock.clock(on)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'control-panel', surface, ...PANE })
    expect(await ui.find({ text: /待機中/ })).toBeDefined()
    expect(await ui.find({ text: /▶ 実行中/ })).toBeUndefined()
    await ui.unmount()
  }
})

test('progress, history and tabs show on every surface', async ($, on) => {
  mock.clock(on)
  // Stand in for the engine's tools beneath the plugin.
  on('tool.call', () => ({ result: {} }))

  await $.tool.call({
    tool: 'TodoWrite',
    todos: [
      { content: '企画を作る', status: 'completed', activeForm: '企画を作成中' },
      { content: '台本を書く', status: 'in_progress', activeForm: '台本を執筆中' },
      { content: '動画を書き出す', status: 'pending', activeForm: '書き出し中' },
    ],
  })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'control-panel', surface, ...PANE })

    expect(await ui.find({ text: /1 \/ 3 完了/ })).toBeDefined()
    expect(await ui.find({ text: /台本を執筆中/ })).toBeDefined()
    // The running box is pinned above every tab.
    expect(await ui.find({ text: /▶ 実行中/ })).toBeDefined()
    expect(await ui.find({ text: /進行中のタスク/ })).toBeDefined()

    await ui.press({ key: 'tab-log' })
    expect(await ui.find({ text: /TodoWrite/ })).toBeDefined()

    expect(await ui.find({ text: /▶ 実行中/ })).toBeDefined()

    await ui.press({ key: 'tab-agents' })
    expect(await ui.find({ text: /まだ起動していません/ })).toBeDefined()
    expect(await ui.find({ text: /▶ 実行中/ })).toBeDefined()

    await ui.press({ key: 'tab-overview' })
    await ui.unmount()
  }
})
