import { useEffect, useState } from 'react'
import type {
  AIExplanationResponse,
  AIProviderInfo,
  PredictionAIExplanationRequest,
  ForecastAIExplanationRequest,
} from '../../types'
import {
  getAIExplanationStatus,
  explainPredictionWithAI,
  explainForecastWithAI,
} from '../../services/api'

interface AIExplanationCardProps {
  type: 'prediction' | 'forecast'
  predictionPayload?: PredictionAIExplanationRequest
  forecastPayload?: ForecastAIExplanationRequest
  className?: string
}

export default function AIExplanationCard({
  type,
  predictionPayload,
  forecastPayload,
  className = '',
}: AIExplanationCardProps) {
  const [providers, setProviders] = useState<AIProviderInfo[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>('ollama')
  const [selectedModel, setSelectedModel] = useState<string>('llama3.2')
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<AIExplanationResponse | null>(null)
  const [showRawEvidence, setShowRawEvidence] = useState<boolean>(false)

  // 1. Fetch available LLM providers on mount
  useEffect(() => {
    let mounted = true
    getAIExplanationStatus()
      .then((status) => {
        if (!mounted) return
        setProviders(status.providers)
        // Prefer ollama if available, otherwise first configured or deterministic_fallback
        const ollama = status.providers.find((p) => p.provider_id === 'ollama')
        const firstConfigured = status.providers.find((p) => p.available)
        if (ollama) {
          setSelectedProvider('ollama')
          setSelectedModel(ollama.default_model || 'llama3.2')
        } else if (firstConfigured) {
          setSelectedProvider(firstConfigured.provider_id)
          setSelectedModel(firstConfigured.default_model)
        } else {
          setSelectedProvider('deterministic_fallback')
          setSelectedModel('rules_engine_v1')
        }
      })
      .catch(() => {
        // Fallback default list if status call fails
        if (!mounted) return
        setProviders([
          { provider_id: 'ollama', display_name: 'Ollama (Local)', available: true, default_model: 'llama3.2' },
          { provider_id: 'openai', display_name: 'OpenAI', available: false, default_model: 'gpt-4o-mini' },
          { provider_id: 'deterministic_fallback', display_name: 'Deterministic Rules (No LLM)', available: true, default_model: 'rules_engine_v1' },
        ])
      })

    return () => {
      mounted = false
    }
  }, [])

  // Update selected model when provider changes
  const handleProviderChange = (newProviderId: string) => {
    setSelectedProvider(newProviderId)
    const match = providers.find((p) => p.provider_id === newProviderId)
    if (match) {
      setSelectedModel(match.default_model)
    } else if (newProviderId === 'deterministic_fallback') {
      setSelectedModel('rules_engine_v1')
    }
  }

  // Format raw technical errors into helpful business-friendly guidance
  const formatUserFacingError = (raw: string): string => {
    if (!raw) return 'Explanation generation is currently unavailable.'
    const lower = raw.toLowerCase()
    if (lower.includes('unreachable') || lower.includes('cannot connect') || lower.includes('connection refused')) {
      return 'The selected local AI service (Ollama) is not currently running. You can start it via `ollama serve` or use the verified deterministic engine.'
    }
    if (lower.includes('timeout') || lower.includes('timed out')) {
      return 'The AI provider request timed out. You can retry or switch to the deterministic rules engine.'
    }
    if (lower.includes('api key') || lower.includes('unauthorized') || lower.includes('401')) {
      return 'The configured API key was rejected or unauthorized. Please verify your provider settings.'
    }
    if (lower.includes('rate limit') || lower.includes('429')) {
      return 'The AI provider rate limit was reached. Please wait a moment before retrying.'
    }
    if (lower.includes('missing input payload')) {
      return 'Required model evidence is not yet available. Please complete model training or inference first.'
    }
    return 'The AI explanation service could not complete the request. You can switch to the verified deterministic engine for instant analysis.'
  }

  // Generate explanation
  const handleGenerate = async (bypassCache = false) => {
    setLoading(true)
    setError(null)

    try {
      let resp: AIExplanationResponse
      if (type === 'prediction') {
        if (!predictionPayload) {
          throw new Error('Missing input payload for prediction explanation.')
        }
        resp = await explainPredictionWithAI({
          ...predictionPayload,
          provider: selectedProvider === 'deterministic_fallback' ? undefined : selectedProvider,
          model: selectedModel,
          force_fallback: selectedProvider === 'deterministic_fallback',
          bypass_cache: bypassCache,
        })
      } else if (type === 'forecast') {
        if (!forecastPayload) {
          throw new Error('Missing input payload for forecast explanation.')
        }
        resp = await explainForecastWithAI({
          ...forecastPayload,
          provider: selectedProvider === 'deterministic_fallback' ? undefined : selectedProvider,
          model: selectedModel,
          force_fallback: selectedProvider === 'deterministic_fallback',
          bypass_cache: bypassCache,
        })
      } else {
        throw new Error('Missing input payload for AI explanation generation.')
      }

      setExplanation(resp)
    } catch (err: any) {
      setError(err?.message || 'Failed to generate AI explanation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`p-5 rounded-xl bg-slate-900 border border-indigo-500/30 space-y-5 shadow-lg shadow-indigo-950/20 ${className}`}>
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 text-lg border border-indigo-500/20">
            ✨
          </span>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span>AI Business Explanation</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 font-mono font-normal lowercase">
                verified evidence only
              </span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Structured, plain-English business interpretation translated directly from authoritative ML calculations.
            </p>
          </div>
        </div>

        {/* Action Controls & Provider Selection */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Provider selector */}
          <select
            value={selectedProvider}
            onChange={(e) => handleProviderChange(e.target.value)}
            disabled={loading}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
          >
            <option value="ollama">Ollama (Local - llama3.2)</option>
            <option value="openai">OpenAI (gpt-4o-mini)</option>
            <option value="groq">Groq (Fast Cloud)</option>
            <option value="gemini">Google Gemini</option>
            <option value="anthropic">Anthropic Claude</option>
            <option value="custom">Custom Endpoint</option>
            <option value="deterministic_fallback">Deterministic Engine (Local Fallback)</option>
          </select>

          {/* Action button */}
          <button
            type="button"
            onClick={() => handleGenerate(Boolean(explanation))}
            disabled={loading}
            className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-xs transition-all flex items-center gap-1.5 shadow-md shadow-indigo-600/20 cursor-pointer"
          >
            {loading ? (
              <>
                <span className="inline-block animate-spin">⚙</span>
                <span>Generating...</span>
              </>
            ) : explanation ? (
              <>
                <span>🔄</span>
                <span>Regenerate</span>
              </>
            ) : (
              <>
                <span>✨</span>
                <span>Generate Explanation</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs flex items-start gap-2.5">
          <span className="text-base leading-none">ℹ️</span>
          <div className="flex-1 space-y-1">
            <div className="font-semibold text-amber-300">Explanation Service Notice</div>
            <p className="text-slate-300">{formatUserFacingError(error)}</p>
            <div className="pt-1.5 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  setSelectedProvider('deterministic_fallback')
                  handleGenerate(true)
                }}
                className="px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-[11px] transition-colors cursor-pointer"
              >
                Use Deterministic Rules Fallback →
              </button>
              <button
                type="button"
                onClick={() => handleGenerate(true)}
                className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-[11px] transition-colors cursor-pointer"
              >
                Retry Request
              </button>
            </div>
          </div>
        </div>
      )}


      {/* Empty Prompt Before User Initiates */}
      {!explanation && !loading && !error && (
        <div className="p-6 rounded-lg bg-slate-950/40 border border-dashed border-slate-800 text-center space-y-2">
          <div className="text-2xl">💡</div>
          <div className="text-xs font-medium text-slate-300">
            Generate an AI-Powered Narrative for this {type === 'prediction' ? 'Prediction' : 'Forecast'}
          </div>
          <p className="text-[11px] text-slate-400 max-w-md mx-auto">
            Translates mathematical feature attributions, cross-validation metrics, and prediction intervals into executive plain English without hallucinated numbers.
          </p>
          <div className="pt-1">
            <button
              type="button"
              onClick={() => handleGenerate(false)}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-500/20 cursor-pointer"
            >
              Generate Business Explanation
            </button>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="p-6 rounded-lg bg-slate-950/40 border border-slate-800/80 space-y-4 animate-pulse">
          <div className="flex items-center gap-2 text-xs text-indigo-400">
            <span className="inline-block animate-spin">⚙</span>
            <span>Synthesizing evidence and translating model metrics via {selectedProvider}...</span>
          </div>
          <div className="h-4 bg-slate-800 rounded w-3/4"></div>
          <div className="h-3 bg-slate-800/60 rounded w-full"></div>
          <div className="h-3 bg-slate-800/60 rounded w-5/6"></div>
          <div className="grid grid-cols-2 gap-3 pt-2">
            <div className="h-16 bg-slate-800/40 rounded"></div>
            <div className="h-16 bg-slate-800/40 rounded"></div>
          </div>
        </div>
      )}

      {/* Rendered Explanation Output */}
      {explanation && !loading && (
        <div className="space-y-4">
          {/* Metadata Badges */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 pb-2 border-b border-slate-800/60">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-mono">
                Provider: <strong className="text-white">{explanation.provider}</strong> ({explanation.model})
              </span>
              {explanation.cache_hit ? (
                <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-mono flex items-center gap-1">
                  <span>⚡</span> Cached Response
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-mono">
                  ● Freshly Generated
                </span>
              )}
              {explanation.is_fallback && (
                <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 font-mono">
                  Deterministic Rules Fallback
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={() => setShowRawEvidence(!showRawEvidence)}
              className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span>{showRawEvidence ? '▼ Hide Evidence Audit' : '▶ Inspect Evidence Audit'}</span>
            </button>
          </div>

          {/* Section 1: Executive Summary */}
          <div className="p-4 rounded-lg bg-indigo-500/5 border border-indigo-500/20 space-y-1.5">
            <div className="text-[11px] font-bold text-indigo-400 uppercase tracking-wider">
              Executive Summary
            </div>
            <p className="text-xs text-slate-200 leading-relaxed font-medium">
              {explanation.summary}
            </p>
          </div>

          {/* Section 2: What the Result Means */}
          <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-1.5">
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              Operational Meaning
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              {explanation.what_the_result_means}
            </p>
          </div>

          {/* Section 3: Supporting Evidence & Drivers */}
          {explanation.supporting_evidence && explanation.supporting_evidence.length > 0 && (
            <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>📈</span>
                <span>Supporting Quantitative Evidence:</span>
              </div>
              <ul className="space-y-1.5">
                {explanation.supporting_evidence.map((ev, idx) => (
                  <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                    <span className="text-indigo-400 text-sm leading-none">•</span>
                    <span>{ev}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Section 4: Model Quality & Trust */}
          {explanation.evaluation_quality && (
            <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800/80 text-xs text-slate-400 space-y-1">
              <span className="font-semibold text-slate-300 uppercase tracking-wider text-[10px] block">
                Model Evaluation Context:
              </span>
              <p>{explanation.evaluation_quality}</p>
            </div>
          )}

          {/* Section 5 & 6: Limitations & Action Checklist Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Limitations & Caveats */}
            {explanation.uncertainty_and_limitations && explanation.uncertainty_and_limitations.length > 0 && (
              <div className="p-4 rounded-lg bg-amber-500/5 border border-amber-500/25 space-y-2">
                <div className="text-xs font-bold text-amber-400 flex items-center gap-1.5 uppercase tracking-wider">
                  <span>⚠️</span>
                  <span>Uncertainty & Boundaries:</span>
                </div>
                <ul className="space-y-1.5">
                  {explanation.uncertainty_and_limitations.map((lim, idx) => (
                    <li key={idx} className="text-xs text-amber-200/90 leading-relaxed flex items-start gap-1.5">
                      <span className="text-amber-400">•</span>
                      <span>{lim}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Suggested Verifications Checklist */}
            {explanation.suggested_verifications && explanation.suggested_verifications.length > 0 && (
              <div className="p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/25 space-y-2">
                <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5 uppercase tracking-wider">
                  <span>✓</span>
                  <span>Recommended Action Verifications:</span>
                </div>
                <ul className="space-y-1.5">
                  {explanation.suggested_verifications.map((veri, idx) => (
                    <li key={idx} className="text-xs text-emerald-200/90 leading-relaxed flex items-start gap-1.5">
                      <span className="text-emerald-400">□</span>
                      <span>{veri}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Collapsible Audit Drawer */}
          {showRawEvidence && (
            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2 text-xs font-mono">
              <div className="flex justify-between items-center text-slate-400">
                <span>Evidence SHA-256 Fingerprint:</span>
                <span className="text-slate-200 select-all">{explanation.evidence_fingerprint}</span>
              </div>
              <div className="flex justify-between items-center text-slate-400">
                <span>Generation Timestamp:</span>
                <span className="text-slate-200">{explanation.generated_at}</span>
              </div>
              {explanation.raw_evidence && (
                <div className="pt-2 border-t border-slate-800">
                  <div className="text-slate-400 mb-1">Normalized Evidence Payload:</div>
                  <pre className="p-2.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-300 overflow-x-auto max-h-48 overflow-y-auto">
                    {JSON.stringify(explanation.raw_evidence, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
