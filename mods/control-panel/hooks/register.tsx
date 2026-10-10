import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { ActiveCall, AgentRow, LogKind, LogRow, Tab, TaskRow, TaskStatus, Turn, Usage } from '../types'

const PANE = 'control-panel'
const TITLE = 'コントロールパネル'
const LOG_CAP = 500
const POLL_MS = 3000
/** The tool the model calls when asked to open the panel; the person's own way is /panel. */
const OPEN_TOOL = 'open_panel'
const OPEN_TOOL_FULL = `mcp__control-panel__${OPEN_TOOL}`

const usage = atom({ plugin: 'control-panel', key: 'usage' } as const, null)
const agents = atom({ plugin: 'control-panel', key: 'agents' } as const, [])
const tasks = atom({ plugin: 'control-panel', key: 'tasks' } as const, [])
const log = atom({ plugin: 'control-panel', key: 'log' } as const, [])
const turn = atom({ plugin: 'control-panel', key: 'turn' } as const, {
  isRunning: false,
  startedAt: 0,
  prompt: '',
  tools: 0,
  turns: 0,
})
const tab = atom({ plugin: 'control-panel', key: 'tab' } as const, 'overview')
const active = atom({ plugin: 'control-panel', key: 'active' } as const, [])
/** The clock as of the last tick; ticks only while something runs, so elapsed times move. */
const now = atom({ plugin: 'control-panel', key: 'now' } as const, 0)

const TABS: { id: Tab; label: string; hotkey: string }[] = [
  { id: 'overview', label: '概要', hotkey: '1' },
  { id: 'agents', label: 'サブエージェント', hotkey: '2' },
  { id: 'tasks', label: '進捗', hotkey: '3' },
  { id: 'log', label: '履歴', hotkey: '4' },
]

const FINISHED = new Set(['completed', 'failed', 'killed'])
/** Agent statuses that mean it is working now (an idle teammate waits for a message). */
const WORKING = new Set(['running', 'pending', 'waiting'])

type Dollar = EngineInterface

// ---------- helpers ----------

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

const clip = (text: string, n: number) => {
  const one = text.replace(/\s+/g, ' ').trim()
  return one.length > n ? `${one.slice(0, Math.max(0, n - 1))}…` : one
}

const pad2 = (n: number) => String(n).padStart(2, '0')

const hhmmss = (ms: number) => {
  const d = new Date(ms)
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

const kTokens = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(2)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)

const bar = (ratio: number, width: number) => {
  const w = Math.max(4, width)
  const filled = Math.round(Math.min(1, Math.max(0, ratio)) * w)
  return '█'.repeat(filled) + '░'.repeat(w - filled)
}

const seconds = (ms: number) => {
  const s = Math.round(ms / 1000)
  return s >= 60 ? `${Math.floor(s / 60)}分${s % 60}秒` : `${s}秒`
}

/** One line saying what a tool call is about. */
const describeCall = (e: { tool: string } & Record<string, unknown>) => {
  const s = (k: string) => (typeof e[k] === 'string' ? (e[k] as string) : undefined)
  const what =
    s('description') ??
    s('command') ??
    s('file_path') ??
    s('pattern') ??
    s('url') ??
    s('query') ??
    s('subject') ??
    s('skill') ??
    ''
  return what ? `${e.tool}: ${what}` : e.tool
}

const pushLog = ($: Dollar, row: LogRow) => update($, log, list => [...list, row].slice(-LOG_CAP))

const taskLabel = (t: TaskRow) => (t.status === 'in_progress' && t.activeForm ? t.activeForm : t.subject)

/** Puts a one-line summary of what runs on the status line, or clears it when idle. */
const refreshStatus = async ($: Dollar) => {
  const t = await read($, turn)
  const working = (await read($, agents)).filter(a => WORKING.has(a.status))
  const doing = (await read($, tasks)).filter(x => x.status === 'in_progress')
  if (!t.isRunning && working.length === 0) {
    $.ui.status(undefined)
    return
  }
  const parts = [
    doing[0] ? `▶ ${clip(taskLabel(doing[0]), 30)}` : t.isRunning ? '▶ 作業中' : '▶ サブエージェント稼働中',
    doing.length > 1 ? `他タスク${doing.length - 1}` : '',
    working.length ? `サブエージェント${working.length}` : '',
  ]
  $.ui.status(parts.filter(Boolean).join(' · '))
}


// ---------- polling ----------

const refreshUsage = async ($: Dollar) => {
  const u = await $.session.usage()
  const next: Usage = {
    tokens: u.context.tokens ?? null,
    window: u.context.window,
    percent: u.context.percent ?? null,
    costUsd: u.cost?.usd ?? null,
    rateLimits: u.rateLimits.map(r => ({ kind: r.kind, percentUsed: r.percentUsed })),
  }
  // Write only on a change, so the pane is not redrawn for nothing.
  if (!same(await read($, usage), next)) await update($, usage, () => next)
}

const refreshAgents = async ($: Dollar) => {
  const list = await $.agent.list()
  const rows: AgentRow[] = list.map(a => ({
    id: a.id,
    description: a.description,
    type: a.type,
    status: a.status,
    parentId: a.parentId,
  }))
  const before = await read($, agents)
  const at = await $.clock.now()
  for (const row of rows) row.startedAt = before.find(b => b.id === row.id)?.startedAt ?? at
  // Keep agents the engine stopped listing, so the panel remembers who worked.
  const merged = [...before.filter(old => !rows.some(r => r.id === old.id)), ...rows]
  for (const row of rows) {
    const old = before.find(b => b.id === row.id)
    if (FINISHED.has(row.status) && old && !FINISHED.has(old.status)) {
      await pushLog($, {
        at: await $.clock.now(),
        kind: row.status === 'completed' ? 'done' : 'error',
        text: `サブエージェント${row.status === 'completed' ? '完了' : '終了(' + row.status + ')'}: ${row.description}`,
        agentId: row.id,
      })
      await update($, active, list => list.filter(c => c.agentId !== row.id))
    }
  }
  if (!same(before, merged)) await update($, agents, () => merged)
}

/** Never rejects: it runs from timers and unawaited, where a failure has nobody to tell. */
const refreshAll = ($: Dollar) => refreshAllOnce($).catch(() => undefined)

const refreshAllOnce = async ($: Dollar) => {
  await Promise.allSettled([refreshUsage($), refreshAgents($)])
  const isBusy =
    (await read($, turn)).isRunning ||
    (await read($, agents)).some(a => WORKING.has(a.status)) ||
    (await read($, active)).length > 0
  if (isBusy) {
    const at = await $.clock.now()
    await update($, now, () => at)
  }
  await refreshStatus($)
}

// ---------- tasks ----------

const setTask = ($: Dollar, id: string, change: (t: TaskRow | undefined) => TaskRow | null) =>
  update($, tasks, list => {
    const i = list.findIndex(t => t.id === id)
    const next = change(i >= 0 ? list[i] : undefined)
    if (next === null) return list.filter(t => t.id !== id)
    return i >= 0 ? list.map((t, j) => (j === i ? next : t)) : [...list, next]
  })

// ---------- register ----------

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'panel',
      description: 'コントロールパネル(サブエージェント・進捗・トークン・履歴)を開く',
    })
    await $.tool.register({
      name: OPEN_TOOL,
      description:
        'Opens the control panel pane (subagents, running work, progress, tokens, history). ' +
        'Call it when the user asks to open or show the control panel / コントロールパネル.',
      inputSchema: { type: 'object', properties: {} },
      isDeferred: false,
    })
    void $.ui.open({ id: PANE, title: TITLE })
    void refreshAll($)
    $.clock.every(POLL_MS, () => void refreshAll($))

    return next(e)
  })

  on('command.run', { command: 'panel' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })
    void refreshAll($)

    return { text: 'コントロールパネルを開きました。' }
  })

  on('turn.start', async ($, e, next) => {
    const at = await $.clock.now()
    await update($, turn, t => ({
      isRunning: true,
      startedAt: at,
      prompt: e.text,
      tools: 0,
      turns: t.turns + 1,
    }))
    await update($, now, () => at)
    await pushLog($, { at, kind: 'prompt', text: e.text ? `指示: ${e.text}` : '(続行)' })
    void refreshStatus($).catch(() => undefined)

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      const at = await $.clock.now()
      await update($, turn, t => ({ ...t, isRunning: false }))
      await update($, active, list => list.filter(c => c.agentId !== undefined))
      const used = e.usage ? ` / 出力 ${kTokens(e.usage.output_tokens)} tok` : ''
      await pushLog($, {
        at,
        kind: e.reason === 'answer' ? 'done' : 'error',
        text:
          e.reason === 'answer'
            ? `ターン完了 (${seconds(e.durationMs)}${used})`
            : `ターン終了: ${e.reason} (${seconds(e.durationMs)})`,
      })
      void refreshAll($)
    }

    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    if (String(e.tool) === OPEN_TOOL_FULL) {
      const { isPlaced } = await $.ui.open({ id: PANE, title: TITLE })
      await refreshAll($)
      return {
        result: isPlaced
          ? 'The control panel is open.'
          : 'The control panel was opened, but no surface is drawing panes right now; the user can type /panel.',
      }
    }

    const at = await $.clock.now()
    const loose = e as unknown as { tool: string } & Record<string, unknown>
    if (e.agentId === undefined) await update($, turn, t => ({ ...t, tools: t.tools + 1 }))

    const kind: LogKind = e.tool === 'Agent' ? 'agent' : 'tool'
    await pushLog($, {
      at,
      kind,
      text: e.tool === 'Agent' ? `サブエージェント起動: ${describeCall(loose)}` : describeCall(loose),
      agentId: e.agentId,
    })

    // Track progress from the todo / task tools before the call runs …
    if (e.tool === 'TodoWrite') {
      const rows: TaskRow[] = e.todos.map((t, i) => ({
        id: `todo-${i}`,
        subject: t.content,
        status: t.status,
        activeForm: t.activeForm,
      }))
      await update($, tasks, () => rows)
    }
    if (e.tool === 'TaskUpdate' && e.status) {
      const status = e.status
      const subject = e.subject
      const activeForm = e.activeForm
      await setTask($, e.taskId, t =>
        status === 'deleted'
          ? null
          : {
              id: e.taskId,
              subject: subject ?? t?.subject ?? `#${e.taskId}`,
              status: status as TaskStatus,
              activeForm: activeForm ?? t?.activeForm,
            },
      )
    }
    const createdForm = e.tool === 'TaskCreate' ? e.activeForm : undefined

    const call: ActiveCall = { id: e.tool_use_id, text: describeCall(loose), agentId: e.agentId, startedAt: at }
    await update($, active, list => [...list, call].slice(-100))
    await update($, now, () => at)
    void refreshStatus($).catch(() => undefined)

    let ran: Awaited<ReturnType<typeof next>>
    try {
      ran = await next(e)
    } finally {
      await update($, active, list => list.filter(c => c.id !== call.id))
    }

    // … and from what it answered.
    if (e.tool === 'TaskCreate' && ran.result && !ran.isError) {
      const created = (ran.result as { task?: { id: string; subject: string } }).task
      if (created) {
        await setTask($, created.id, () => ({
          id: created.id,
          subject: created.subject,
          status: 'pending',
          activeForm: createdForm,
        }))
      }
    }
    if (e.tool === 'TodoWrite' || e.tool === 'TaskUpdate' || e.tool === 'TaskCreate') void refreshStatus($).catch(() => undefined)
    if (e.tool === 'Agent') void refreshAgents($)
    if (ran.isError) {
      await pushLog($, { at: await $.clock.now(), kind: 'error', text: `失敗: ${e.tool}`, agentId: e.agentId })
    }

    return ran
  })

  // ---------- drawing ----------

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const width = Math.max(20, e.props.bodyColumns)
    const current = await read($, tab)
    const u = await read($, usage)
    const t: Turn = await read($, turn)
    const agentList = await read($, agents)
    const taskList = await read($, tasks)
    const logList = await read($, log)
    const calls = await read($, active)
    const clockNow = await read($, now)

    const nameOf = (id?: string) => {
      if (!id) return ''
      const a = agentList.find(x => x.id === id)
      return a ? `[${clip(a.description, 14)}] ` : '[sub] '
    }

    const statusColor = (s: string) =>
      s === 'running' ? 'claude' : s === 'completed' ? 'success' : s === 'failed' || s === 'killed' ? 'error' : 'subtle'
    const statusMark = (s: string) =>
      s === 'running' ? '●' : s === 'completed' ? '✔' : s === 'failed' || s === 'killed' ? '✖' : '○'
    const taskMark = (s: TaskStatus) => (s === 'completed' ? '✔' : s === 'in_progress' ? '▶' : '○')
    const taskColor = (s: TaskStatus) => (s === 'completed' ? 'success' : s === 'in_progress' ? 'claude' : 'subtle')
    const logColor = (k: LogKind) =>
      k === 'prompt' ? 'suggestion' : k === 'agent' ? 'claude' : k === 'done' ? 'success' : k === 'error' ? 'error' : undefined

    // --- sections ---

    const tokenSection = () => {
      if (!u) return <Text dimColor>トークン情報を取得中…</Text>
      const used = u.tokens ?? 0
      const left = Math.max(0, u.window - used)
      const ratio = u.window > 0 ? used / u.window : 0
      const color = ratio >= 0.85 ? 'error' : ratio >= 0.6 ? 'warning' : 'success'
      return (
        <Box flexDirection="column">
          <Text bold>トークン</Text>
          <Text color={color}>{bar(ratio, width - 2)}</Text>
          <Text>
            残り <Text bold color={color}>{kTokens(left)}</Text> / {kTokens(u.window)}
            <Text dimColor>
              {'  '}(使用 {kTokens(used)} · {u.percent ?? Math.round(ratio * 100)}%)
            </Text>
          </Text>
          {u.costUsd !== null && <Text dimColor>コスト ${u.costUsd.toFixed(2)}</Text>}
          {u.rateLimits.map(r => (
            <Text dimColor>
              {r.kind}: {Math.round(r.percentUsed)}% 使用
            </Text>
          ))}
        </Box>
      )
    }

    const elapsed = (since?: number) => (since && clockNow >= since ? seconds(clockNow - since) : '')

    /** The box pinned above every tab: what runs right now, at a glance. */
    const runningSection = () => {
      const working = agentList.filter(a => WORKING.has(a.status))
      const doing = taskList.filter(x => x.status === 'in_progress')
      const mainCall = calls.filter(c => c.agentId === undefined).at(-1)
      const callOf = (id: string) => calls.filter(c => c.agentId === id).at(-1)
      const isBusy = t.isRunning || working.length > 0 || doing.length > 0
      const inner = Math.max(10, width - 4)

      if (!isBusy) {
        return (
          <Box borderStyle="round" borderDimColor flexDirection="column" paddingX={1} marginBottom={1}>
            <Text color="success" bold>
              ✔ 待機中
            </Text>
            <Text dimColor wrap="truncate-end">
              {t.turns === 0
                ? '実行中のタスクはありません。'
                : `実行中のタスクはありません(前回: #${t.turns} ${hhmmss(t.startedAt)}開始 · ツール${t.tools}回)`}
            </Text>
          </Box>
        )
      }

      const counts = [
        doing.length ? `タスク ${doing.length}` : '',
        working.length ? `サブエージェント ${working.length}` : '',
      ].filter(Boolean)

      return (
        <Box borderStyle="round" borderColor="claude" flexDirection="column" paddingX={1} marginBottom={1}>
          <Text bold color="claude">
            ▶ 実行中{counts.length ? <Text dimColor>{'  '}({counts.join(' · ')})</Text> : ''}
          </Text>

          {t.isRunning && (
            <Box flexDirection="column" marginTop={1}>
              <Text wrap="truncate-end">
                <Text bold>秘書(メイン) </Text>
                <Text dimColor>
                  経過 {elapsed(t.startedAt)} · ツール {t.tools}回
                </Text>
              </Text>
              {t.prompt && <Text wrap="truncate-end">　指示「{clip(t.prompt, inner * 2)}」</Text>}
              {mainCall && (
                <Text wrap="truncate-end" color="suggestion">
                  　⚙ {clip(mainCall.text, inner)}
                  <Text dimColor> ({elapsed(mainCall.startedAt)})</Text>
                </Text>
              )}
            </Box>
          )}

          {doing.length > 0 && (
            <Box flexDirection="column" marginTop={1}>
              <Text bold>進行中のタスク</Text>
              {doing.map(x => (
                <Text wrap="truncate-end" color="claude">
                  　▶ {taskLabel(x)}
                </Text>
              ))}
            </Box>
          )}

          {working.length > 0 && (
            <Box flexDirection="column" marginTop={1}>
              <Text bold>稼働中のサブエージェント</Text>
              {working.map(a => {
                const c = callOf(a.id)
                return (
                  <Box flexDirection="column">
                    <Text wrap="truncate-end">
                      <Text color="claude">　● </Text>
                      {a.description}
                      <Text dimColor>
                        {'  '}
                        {a.type} · 経過 {elapsed(a.startedAt)}
                      </Text>
                    </Text>
                    {c && (
                      <Text wrap="truncate-end" color="suggestion">
                        　　⚙ {clip(c.text, inner - 4)}
                        <Text dimColor> ({elapsed(c.startedAt)})</Text>
                      </Text>
                    )}
                  </Box>
                )
              })}
            </Box>
          )}
        </Box>
      )
    }

    const agentsSection = (limit: number) => {
      const running = agentList.filter(a => !FINISHED.has(a.status))
      const shown = current === 'agents' ? agentList : running.length ? running : agentList.slice(-limit)
      return (
        <Box flexDirection="column" marginTop={1}>
          <Text bold>
            サブエージェント{' '}
            <Text dimColor>
              (稼働 {running.length} / 全 {agentList.length})
            </Text>
          </Text>
          {shown.length === 0 && <Text dimColor>まだ起動していません。</Text>}
          {shown.slice(-limit).map(a => (
            <Text wrap="truncate-end">
              <Text color={statusColor(a.status)}>{statusMark(a.status)} </Text>
              {a.description}
              <Text dimColor>
                {'  '}
                {a.type} · {a.status}
                {a.parentId ? ' · 子' : ''}
              </Text>
            </Text>
          ))}
        </Box>
      )
    }

    const tasksSection = (limit: number) => {
      const done = taskList.filter(x => x.status === 'completed').length
      const active = taskList.filter(x => x.status === 'in_progress')
      const shown = current === 'tasks' ? taskList : [...active, ...taskList.filter(x => x.status === 'pending')]
      return (
        <Box flexDirection="column" marginTop={1}>
          <Text bold>
            進捗{' '}
            <Text dimColor>
              ({done} / {taskList.length} 完了)
            </Text>
          </Text>
          {taskList.length === 0 ? (
            <Text dimColor>タスクリストはまだありません。</Text>
          ) : (
            <Text color="success">{bar(done / taskList.length, width - 2)}</Text>
          )}
          {shown.slice(0, limit).map(x => (
            <Text wrap="truncate-end" dimColor={x.status === 'completed'}>
              <Text color={taskColor(x.status)}>{taskMark(x.status)} </Text>
              {x.subject}
            </Text>
          ))}
          {shown.length > limit && <Text dimColor>…ほか {shown.length - limit} 件</Text>}
        </Box>
      )
    }

    const logSection = (limit: number) => (
      <Box flexDirection="column" marginTop={1}>
        <Text bold>
          ここまでの作業 <Text dimColor>({logList.length} 件)</Text>
        </Text>
        {logList.length === 0 && <Text dimColor>まだ記録はありません。</Text>}
        {logList.slice(-limit).map(row => (
          <Text wrap="truncate-end">
            <Text dimColor>{hhmmss(row.at)} </Text>
            <Text dimColor>{nameOf(row.agentId)}</Text>
            <Text color={logColor(row.kind)}>{row.text}</Text>
          </Text>
        ))}
      </Box>
    )

    const tabs = (
      <Box flexDirection="row" flexWrap="wrap" columnGap={1} marginBottom={1}>
        {TABS.map(x => (
          <Button
            key={`tab-${x.id}`}
            label={x.label}
            hotkey={x.hotkey}
            variant={x.id === current ? 'primary' : 'secondary'}
            onPress={() => update($, tab, () => x.id)}
          />
        ))}
      </Box>
    )

    const body =
      current === 'agents' ? (
        agentsSection(200)
      ) : current === 'tasks' ? (
        tasksSection(200)
      ) : current === 'log' ? (
        logSection(LOG_CAP)
      ) : (
        <Box flexDirection="column">
          {tokenSection()}
          {agentsSection(5)}
          {tasksSection(6)}
          {logSection(8)}
        </Box>
      )

    return (
      <Box flexDirection="column">
        {tabs}
        {runningSection()}
        {body}
      </Box>
    )
  })
}
