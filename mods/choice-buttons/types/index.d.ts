/** One button: what it shows and what pressing it sends as the person's answer. */
export type Option = { label: string; send: string }

/** The choice the last answer asked for; null when there is nothing to answer. */
export type Choice = { options: Option[] }

declare module 'claude-code' {
  interface PluginState {
    'choice-buttons': {
      choice: Choice | null
    }
  }
}
