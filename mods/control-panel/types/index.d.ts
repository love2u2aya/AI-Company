export type Usage = {
  tokens: number | null
  window: number
  percent: number | null
  costUsd: number | null
  rateLimits: { kind: string; percentUsed: number }[]
}

export type AgentRow = {
  id: string
  description: string
  type: string
  status: string
  parentId?: string
}

export type TaskStatus = 'pending' | 'in_progress' | 'completed'

export type TaskRow = { id: string; subject: string; status: TaskStatus }

export type LogKind = 'prompt' | 'tool' | 'agent' | 'done' | 'error'

export type LogRow = { at: number; kind: LogKind; text: string; agentId?: string }

export type Turn = {
  isRunning: boolean
  startedAt: number
  prompt: string
  tools: number
  turns: number
}

export type Tab = 'overview' | 'agents' | 'tasks' | 'log'

declare module 'claude-code' {
  interface PluginState {
    'control-panel': {
      usage: Usage | null
      agents: AgentRow[]
      tasks: TaskRow[]
      log: LogRow[]
      turn: Turn
      tab: Tab
    }
  }
}
