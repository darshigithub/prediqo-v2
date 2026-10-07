import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  addToDashboard,
  askAIAnalyst,
  getAISuggestions,
  getDefaultDashboard,
  getProviders,
} from '../services/api'
import type { AIAnalyzeResponse, LLMProviderInfo } from '../types'
import ChartCard from '../components/ChartCard'
import DatasetPicker from '../components/DatasetPicker'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content?: string
  response?: AIAnalyzeResponse
  timestamp: string
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'number') {
    return v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  return String(v)
}

export default function AnalystPage() {
  const [datasetId, setDatasetId] = useState('')
  const [question, setQuestion] = useState('')
  const [conversationId, setConversationId] = useState<string | undefined>(undefined)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [useFallback, setUseFallback] = useState(false)
  const [showPlanFor, setShowPlanFor] = useState<string | null>(null)
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({})

  // Multi-provider state
  const [providers, setProviders] = useState<LLMProviderInfo[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>('openai')
  const [selectedModel, setSelectedModel] = useState<string>('')

  const chatEndRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  // Load available LLM providers on mount
  useEffect(() => {
    getProviders()
      .then((data) => {
        setProviders(data.providers || [])
        if (data.active_provider) {
          setSelectedProvider(data.active_provider)
          const activeP = data.providers.find((p) => p.id === data.active_provider)
          if (activeP) {
            setSelectedModel(activeP.default_model)
          }
        }
      })
      .catch((err) => {
        console.warn('Could not fetch LLM providers:', err)
      })
  }, [])

  // When selected provider changes, update default model
  const handleProviderChange = (newProvider: string) => {
    setSelectedProvider(newProvider)
    const p = providers.find((pr) => pr.id === newProvider)
    if (p) {
      setSelectedModel(p.default_model)
    }
  }

  // Fetch dynamic suggestions whenever dataset changes
  useEffect(() => {
    if (!datasetId) {
      setSuggestions([])
      setMessages([])
      setConversationId(undefined)
      return
    }

    let isMounted = true
    setLoadingSuggestions(true)
    setError(null)
    setMessages([])
    setConversationId(undefined)

    getAISuggestions(datasetId)
      .then((res) => {
        if (isMounted) {
          setSuggestions(res.suggestions || [])
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.warn('Could not fetch suggestions:', err)
          setSuggestions([
            'What is the total revenue?',
            'Which product category generates the most revenue?',
            'What are the top 10 products by sales?',
            'How does revenue change over time?',
            'Which city has the highest revenue?',
          ])
        }
      })
      .finally(() => {
        if (isMounted) setLoadingSuggestions(false)
      })

    return () => {
      isMounted = false
    }
  }, [datasetId])

  // Scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  const ask = async (q?: string, forceFallback?: boolean) => {
    const query = (q ?? question).trim()
    if (!query || !datasetId || busy) return

    const effectiveFallback = forceFallback !== undefined ? forceFallback : useFallback

    const userMsgId = `user_${Date.now()}`
    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    const newMessages: ChatMessage[] = [
      ...messages,
      {
        id: userMsgId,
        role: 'user',
        content: query,
        timestamp: nowStr,
      },
    ]

    setMessages(newMessages)
    setQuestion('')
    setBusy(true)
    setError(null)

    try {
      const res = await askAIAnalyst(
        datasetId,
        query,
        conversationId,
        effectiveFallback,
        selectedProvider,
        selectedModel || undefined
      )

      if (res.conversation_id) {
        setConversationId(res.conversation_id)
      }

      const assistantMsgId = `asst_${Date.now()}`
      setMessages([
        ...newMessages,
        {
          id: assistantMsgId,
          role: 'assistant',
          response: res,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e)
      setError(errMsg)
    } finally {
      setBusy(false)
    }
  }

  const handleAddToDashboard = async (msgId: string, resp: AIAnalyzeResponse) => {
    if (!datasetId) return
    try {
      const dash = await getDefaultDashboard()
      await addToDashboard(dash.id, {
        dataset_id: datasetId,
        question: resp.question,
        chart_type: resp.chart.type,
        result: resp.result.rows,
        insight: resp.insight,
        chart_spec: {
          dataset_id: datasetId,
          type: resp.chart.type as any,
          dimension: (resp.chart.x || resp.result.dimension) ?? null,
          metric: (resp.chart.y || resp.result.metric) ?? null,
          aggregation: resp.query_plan.metrics[0]?.aggregation || 'sum',
          filters: [],
          sort: resp.query_plan.sort[0]?.direction.toLowerCase() || 'desc',
          top_n: resp.query_plan.limit ?? null,
          title: resp.question,
        },
      })
      setAddedIds((prev) => ({ ...prev, [msgId]: true }))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleClearConversation = () => {
    setMessages([])
    setConversationId(undefined)
    setError(null)
  }

  const currentProviderInfo = providers.find((p) => p.id === selectedProvider)

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>AI Analyst</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200">
              Multi-LLM Engine
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Supports OpenAI, Anthropic Claude, Google Gemini, Groq, and custom endpoints.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Provider Selector */}
          <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs shadow-sm">
            <span className="text-slate-400 font-medium">LLM:</span>
            <select
              className="bg-transparent font-medium text-slate-700 focus:outline-none cursor-pointer"
              value={selectedProvider}
              onChange={(e) => handleProviderChange(e.target.value)}
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} {p.configured ? '✓' : '(No Key)'}
                </option>
              ))}
            </select>
          </div>

          {/* Model Selector if available */}
          {currentProviderInfo && currentProviderInfo.models.length > 0 && (
            <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs shadow-sm">
              <span className="text-slate-400 font-medium">Model:</span>
              <select
                className="bg-transparent font-medium text-slate-700 focus:outline-none cursor-pointer"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {currentProviderInfo.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Dataset Picker */}
          <div className="w-full sm:w-64">
            <DatasetPicker value={datasetId} onChange={setDatasetId} />
          </div>
        </div>
      </div>

      {/* Main Split Layout: Left Suggestions | Right Chat */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Suggestions */}
        <div className="lg:col-span-4 flex flex-col gap-3">
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-700">Suggestions</span>
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 font-medium">
                  {suggestions.length}
                </span>
              </div>
              {datasetId && (
                <button
                  className="text-xs text-slate-400 hover:text-brand-600 transition-colors"
                  title="Refresh suggestions"
                  onClick={() => {
                    setLoadingSuggestions(true)
                    getAISuggestions(datasetId)
                      .then((r) => setSuggestions(r.suggestions || []))
                      .finally(() => setLoadingSuggestions(false))
                  }}
                >
                  ↻ Refresh
                </button>
              )}
            </div>

            <p className="text-xs text-slate-500 mb-3">
              Questions automatically tailored to this dataset’s schema and metrics:
            </p>

            {loadingSuggestions ? (
              <div className="space-y-2 py-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-9 bg-slate-100 animate-pulse rounded-lg" />
                ))}
              </div>
            ) : suggestions.length > 0 ? (
              <div className="flex flex-col gap-2">
                {suggestions.map((sug, idx) => {
                  const qLower = sug.toLowerCase()
                  let tag: { label: string; color: string } | null = null
                  if (qLower.includes('revenue') || qLower.includes('sales') || qLower.includes('amount')) {
                    tag = { label: 'Revenue', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' }
                  } else if (qLower.includes('order')) {
                    tag = { label: 'Orders', color: 'bg-blue-50 text-blue-700 border-blue-200' }
                  } else if (qLower.includes('delivery') || qLower.includes('shipping')) {
                    tag = { label: 'Delivery', color: 'bg-amber-50 text-amber-700 border-amber-200' }
                  } else if (qLower.includes('rating') || qLower.includes('satisfaction') || qLower.includes('customer')) {
                    tag = { label: 'Customer', color: 'bg-purple-50 text-purple-700 border-purple-200' }
                  } else if (qLower.includes('product') || qLower.includes('category')) {
                    tag = { label: 'Catalog', color: 'bg-indigo-50 text-indigo-700 border-indigo-200' }
                  } else if (qLower.includes('city') || qLower.includes('location')) {
                    tag = { label: 'Geography', color: 'bg-teal-50 text-teal-700 border-teal-200' }
                  }

                  return (
                    <button
                      key={idx}
                      disabled={!datasetId || busy}
                      onClick={() => ask(sug)}
                      className="text-left text-xs text-slate-700 bg-slate-50 hover:bg-brand-50 hover:text-brand-700 border border-slate-200 hover:border-brand-200 p-2.5 rounded-lg transition-all duration-150 flex items-start gap-2 group"
                    >
                      <span className="text-slate-400 group-hover:text-brand-500 shrink-0 mt-0.5">✦</span>
                      <span className="flex-1 font-medium">{sug}</span>
                      {tag && (
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border shrink-0 ${tag.color}`}>
                          {tag.label}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className="text-xs text-slate-400 text-center py-6">
                {datasetId ? 'No suggestions available.' : 'Select a connected dataset above.'}
              </div>
            )}
          </div>

          {/* Engine Settings card */}
          <div className="card p-3 text-xs bg-slate-50/70 border border-slate-200 space-y-2">
            <div className="flex items-center justify-between text-slate-600">
              <span className="font-medium">Active Provider:</span>
              <span className="font-mono text-[11px] font-semibold text-brand-700 capitalize">
                {selectedProvider} {currentProviderInfo?.configured ? '(Key Set)' : '(Not Set)'}
              </span>
            </div>
            <div className="flex items-center justify-between text-slate-600">
              <span className="font-medium">Execution Engine:</span>
              <span className="font-mono text-[11px] text-slate-500">DuckDB + Pandas</span>
            </div>
            <div className="flex items-center justify-between text-slate-600 pt-1 border-t border-slate-200/60">
              <span className="font-medium">Offline parser:</span>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useFallback}
                  onChange={(e) => setUseFallback(e.target.checked)}
                  className="rounded text-brand-600 focus:ring-brand-500"
                />
                <span className="text-slate-500 text-[11px]">Use local engine</span>
              </label>
            </div>
          </div>
        </div>

        {/* Right Column: Chat Stream */}
        <div className="lg:col-span-8 flex flex-col h-[750px] card overflow-hidden">
          {/* Chat Header */}
          <div className="p-3.5 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-semibold text-slate-700">Analyst Conversation</span>
              {conversationId && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200 text-slate-600">
                  {conversationId}
                </span>
              )}
            </div>

            {messages.length > 0 && (
              <button
                onClick={handleClearConversation}
                className="text-xs text-slate-400 hover:text-red-600 transition-colors"
              >
                Clear Chat
              </button>
            )}
          </div>

          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-5 bg-slate-50/30">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center p-6">
                <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center text-xl mb-3">
                  💬
                </div>
                <h3 className="text-base font-semibold text-slate-700 mb-1">
                  Ask anything about your data
                </h3>
                <p className="text-xs text-slate-400 max-w-sm">
                  Click a suggestion on the left, or type a question like{' '}
                  <span className="text-slate-600 font-mono">"Show revenue by city"</span> or{' '}
                  <span className="text-slate-600 font-mono">"Top 5 products by revenue"</span>.
                </p>
              </div>
            )}

            {messages.map((msg) => {
              if (msg.role === 'user') {
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-xl bg-brand-600 text-white rounded-2xl rounded-tr-none px-4 py-2.5 text-sm shadow-sm">
                      <p>{msg.content}</p>
                      <span className="block text-[10px] text-brand-200 text-right mt-1">
                        {msg.timestamp}
                      </span>
                    </div>
                  </div>
                )
              }

              // Assistant message card
              const resp = msg.response
              if (!resp) return null
              const isPlanOpen = showPlanFor === msg.id
              const isAdded = !!addedIds[msg.id]
              const providerLabel = resp.provider || resp.parser_used

              return (
                <div key={msg.id} className="flex flex-col gap-3">
                  <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-4">
                    {/* Header info */}
                    <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-800">AI Analyst Result</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-brand-50 text-brand-700 font-mono border border-brand-200 capitalize">
                          {providerLabel}
                        </span>
                        {resp.timing && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono flex items-center gap-1">
                            {resp.cache_hit || resp.timing.cache_hit ? (
                              <span className="text-emerald-600 font-bold">⚡ Cache Hit</span>
                            ) : (
                              <span>DuckDB: {resp.timing.duckdb_ms ?? 0}ms</span>
                            )}
                            <span>·</span>
                            <span>Total: {resp.timing.total_ms ?? 0}ms</span>
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-slate-400">{msg.timestamp}</span>
                    </div>


                    {/* Query Plan summary badge */}
                    <div className="flex items-center justify-between bg-slate-50 rounded-lg p-2.5 text-xs text-slate-700">
                      <div className="font-mono text-[11px] text-slate-600 truncate flex-1">
                        <span className="font-bold text-brand-700">
                          {resp.query_plan.intent.toUpperCase()}:
                        </span>{' '}
                        {resp.query_plan.metrics[0]?.aggregation || 'SUM'}(
                        {resp.query_plan.metrics[0]?.column || '*'})
                        {resp.query_plan.dimensions.length > 0 && (
                          <> GROUP BY {resp.query_plan.dimensions.join(', ')}</>
                        )}
                        {resp.query_plan.limit && <> LIMIT {resp.query_plan.limit}</>}
                      </div>
                      <button
                        onClick={() => setShowPlanFor(isPlanOpen ? null : msg.id)}
                        className="text-[11px] text-brand-600 hover:text-brand-800 font-medium ml-2 shrink-0"
                      >
                        {isPlanOpen ? 'Hide Plan' : 'View Plan'}
                      </button>
                    </div>

                    {/* Collapsible Plan & SQL details */}
                    {isPlanOpen && (
                      <div className="bg-slate-900 text-slate-100 rounded-lg p-3 text-xs font-mono space-y-2">
                        <div>
                          <span className="text-slate-400 block mb-1">DuckDB SQL:</span>
                          <code className="text-emerald-400">{resp.result.sql}</code>
                        </div>
                        <div>
                          <span className="text-slate-400 block mb-1">Structured QueryPlan:</span>
                          <pre className="text-slate-300 text-[11px] overflow-auto max-h-40">
                            {JSON.stringify(resp.query_plan, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}

                    {/* Table & Chart display */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Result Table */}
                      <div className="border border-slate-100 rounded-lg p-3 flex flex-col">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold text-slate-700">Data Table</span>
                          <span className="text-[11px] text-slate-400">
                            {resp.result.row_count} rows
                          </span>
                        </div>
                        <div className="overflow-auto max-h-64 flex-1">
                          <table className="min-w-full text-xs">
                            <thead>
                              <tr className="bg-slate-50 text-left text-slate-500 sticky top-0">
                                {resp.result.columns.map((col) => (
                                  <th key={col} className="px-2.5 py-1.5 font-medium whitespace-nowrap">
                                    {col.replace(/_/g, ' ')}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {resp.result.rows.map((row, rIdx) => (
                                <tr key={rIdx} className="border-t border-slate-100 hover:bg-slate-50">
                                  {resp.result.columns.map((col, cIdx) => (
                                    <td key={cIdx} className="px-2.5 py-1.5 whitespace-nowrap">
                                      {fmt(row[col])}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Result Chart */}
                      <div className="border border-slate-100 rounded-lg p-1">
                        <ChartCard
                          title={`${resp.chart.type.toUpperCase()} Chart`}
                          chartType={resp.chart.type}
                          data={resp.result.rows}
                          dimension={resp.chart.x || resp.result.dimension}
                          metric={resp.chart.y || resp.result.metric}
                          height={230}
                        />
                      </div>
                    </div>

                    {/* Insight Box */}
                    {resp.insight && (
                      <div className="rounded-xl bg-amber-50/80 border border-amber-200/80 p-3.5 flex items-start gap-3">
                        <span className="text-amber-600 text-lg leading-none">💡</span>
                        <div className="flex-1 text-xs text-amber-950">
                          <span className="font-bold text-amber-900 block mb-0.5">Analyst Insight:</span>
                          <p className="leading-relaxed">{resp.insight}</p>
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center justify-between pt-1">
                      <div className="flex flex-wrap gap-1.5">
                        <span className="text-[11px] text-slate-400 self-center mr-1">Follow-up:</span>
                        <button
                          onClick={() => ask('Only top 5')}
                          className="px-2 py-0.5 rounded-full text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-600 transition"
                        >
                          Top 5 only
                        </button>
                        <button
                          onClick={() => ask('Show as bar chart')}
                          className="px-2 py-0.5 rounded-full text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-600 transition"
                        >
                          Bar chart
                        </button>
                        <button
                          onClick={() => ask('Show as line chart')}
                          className="px-2 py-0.5 rounded-full text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-600 transition"
                        >
                          Line chart
                        </button>
                      </div>

                      <div className="flex gap-2">
                        <button
                          disabled={isAdded}
                          onClick={() => handleAddToDashboard(msg.id, resp)}
                          className="btn-secondary text-xs px-2.5 py-1"
                        >
                          {isAdded ? '✓ Added' : '+ Add to Dashboard'}
                        </button>
                        <button
                          onClick={() => navigate('/')}
                          className="btn-primary text-xs px-2.5 py-1"
                        >
                          Dashboard
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}

            {busy && (
              <div className="flex items-center gap-3 text-xs text-slate-500 py-3 px-4 bg-white rounded-xl border border-slate-100 shadow-sm w-fit animate-pulse">
                <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                <span>
                  Querying {selectedProvider} ({selectedModel || 'default model'}), running DuckDB query, and generating insights…
                </span>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mx-4 mb-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between">
              <div>
                <span className="font-semibold">Notice: </span>
                {error}
              </div>
              <button
                onClick={() => {
                  setUseFallback(true)
                  setError(null)
                  if (messages.length > 0 && messages[messages.length - 1].role === 'user') {
                    ask(messages[messages.length - 1].content, true)
                  }
                }}
                className="ml-3 px-2 py-1 bg-red-600 text-white rounded text-[11px] font-medium hover:bg-red-700 transition shrink-0"
              >
                Run with Local Engine
              </button>
            </div>
          )}

          {/* Chat Input Bar */}
          <div className="p-3 border-t border-slate-200 bg-white">
            <div className="flex items-center gap-2">
              <input
                className="input flex-1 text-sm py-2"
                placeholder={
                  datasetId
                    ? `Ask ${selectedProvider} anything about your data (e.g. Show revenue by city, top 5 products...)`
                    : 'Please select a dataset above first...'
                }
                value={question}
                disabled={!datasetId || busy}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    ask()
                  }
                }}
              />
              <button
                className="btn-primary px-4 py-2 text-sm shrink-0"
                disabled={!question.trim() || !datasetId || busy}
                onClick={() => ask()}
              >
                {busy ? 'Analyzing…' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
