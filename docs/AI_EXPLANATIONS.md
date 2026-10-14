# Prediqo — AI-Powered Business Explanation Layer

## 1. Architectural Role and System Boundaries

The **AI-Powered Business Explanation Layer** translates mathematically verified Machine Learning predictions and time-series forecasts into executive-ready, natural-language business narratives.

### Core Philosophy: Strict Translation, Never Source of Truth
1. **Zero Hallucination Policy:** The LLM is strictly a translation and synthesis component. It is never the authoritative source of metrics, predictions, probabilities, or attributions.
2. **Authoritative Evidence Pipeline:** All numbers rendered in explanations originate exclusively from validated upstream services:
   - Supervised ML holdout evaluation & cross-validation metrics (`MAE`, `RMSE`, `R²`, `F1-macro`, `ROC-AUC`).
   - Mathematically verified local feature attributions from the Explainable AI (XAI) engine (`backend/app/explainability`).
   - Chronological rolling-origin backtesting metrics (`WAPE`, `MAPE`, directional accuracy).
   - Empirical prediction intervals (`80%` and `95%` uncertainty bounds).
3. **Non-Causal Relationship Safeguard:** Statistical feature attributions are explicitly disclosed as associative drivers across the training dataset, never direct causal control levers.
4. **Scale & Margin Caveats:** Classification attributions computed in log-odds decision margin space are explicitly labeled, preventing confusing log-odds with linear probability percentages. Uncalibrated scoring values are flagged with calibration caveats.
5. **Non-Guaranteed Forecast Intervals:** Forecast intervals are described as statistical dispersion bounds under historical distributional assumptions, never as guaranteed future ranges.

---

## 2. Multi-Provider Architecture & Local Ollama

Prediqo provides multi-provider LLM support with first-class local Ollama capability:

| Provider | Endpoint | Default Model | Configuration Requirement |
| :--- | :--- | :--- | :--- |
| **Ollama (Local)** | `http://localhost:11434/v1` | `llama3.2` | Runs locally via `ollama serve` (zero API keys) |
| **OpenAI** | Official API | `gpt-4o-mini` | `OPENAI_API_KEY` |
| **Groq** | Fast Cloud API | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| **Google Gemini** | Google AI Studio | `gemini-1.5-flash` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| **Anthropic** | Anthropic API | `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| **Custom / OpenAI-Compatible** | Configurable URL | `default` | `LLM_BASE_URL`, optional `LLM_API_KEY` |
| **Deterministic Fallback** | In-Process Engine | `rules_engine_v1` | None (100% offline, zero network dependencies) |

### Setting Up Local Ollama
To use Ollama without any cloud dependencies:
```powershell
# 1. Download and start Ollama
ollama serve

# 2. Pull the recommended compact model
ollama run llama3.2

# 3. Optional: Customize base URL via environment variable
$env:OLLAMA_BASE_URL = "http://localhost:11434/v1"
```
When Ollama is unreachable, Prediqo catches connection refusals and returns actionable error guidance while automatically offering instant fallback to the deterministic rules engine.

---

## 3. Context-Aware Semantic Validation Engine

Prediqo applies a multi-stage semantic integrity validator (`backend/app/ai/explanation_validator.py`) to every generated narrative before rendering it to end users:

### Negation-Aware Non-Guarantee Policy
Previous naive substring matching flagged legitimate disclaimers (e.g. `"Forecast intervals represent statistical bounds, not a guaranteed outcome"`) because it matched the literal string `"guaranteed outcome"`.

The validator now operates at the **syntactic clause level**:
1. **Sentence & Clause Splitting:** Sentences are split on punctuation and conjunctions (`;`, `,`, `but`, `although`, `however`, `while`).
2. **Negation & Disclaimer Scope Detection:** Each clause is tested against negative/hedging markers:
   - Explicit negation: `not`, `no`, `never`, `cannot`, `is not a`, `does not imply`.
   - Disclaimer prefixes: `statistical bounds rather than`, `estimates based on`, `uncertainty bounds rather than`, `actual outcomes may differ`.
3. **Contextual Evaluation:**
   - **Legitimate Disclaimers Allowed:** If a clause contains a negation marker alongside a term like `"guaranteed outcome"`, it is recognized as a valid disclaimer (e.g., *"This prediction is an estimate, not a guaranteed outcome"*).
   - **Positive Assertions Rejected:** If a clause positively asserts certainty or deterministic outcomes without negation (e.g., *"This is a guaranteed outcome"* or *"100% certain"*), validation fails.
4. **Causal Language Enforcement:** Positive causal claims (e.g., *"Feature X directly causes target Y"*, *"proven to drive"*, *"guaranteed increase"*) are strictly prohibited, ensuring feature importance is accurately communicated as statistical association.

---

## 4. Unified Shared Pipeline & Corrective Retries

Both Prediction and Forecasting explanation workflows run through a single, shared execution engine (`run_shared_explanation_pipeline` in `backend/app/ai/explanation_service.py`):

```
User Request
     │
     ▼
[ SHA-256 Fingerprint Check ] ────► Cache Hit? ───► Return Cached Explanation
     │ (Miss)
     ▼
[ Attempt 1: Initial Prompt ]
     │
     ▼
[ Provider Execution (Ollama/Cloud) ]
     │
     ▼
[ Semantic Integrity Validator ]
     ├──► Passed? ───► Cache & Return Narrative
     │
     ▼ Failed
[ Bounded Corrective Retry Loop (Max 2 Retries / 3 Total Attempts) ]
     │
     ├──► Inject Specific Validation Error as Corrective Feedback
     ├──► Re-prompt LLM with Guided Constraints
     └──► Re-validate Response
          ├──► Passed? ───► Cache & Return Narrative
          │
          ▼ Failed all attempts or Provider Error
[ Deterministic Fallback Engine ] ───► Return Safe Rule-Based Narrative
                                       (with is_fallback=True, 0 Error Leaks)
```

### Corrective Feedback Mechanism
When an initial response fails validation, the retry does not blindly repeat the same prompt. Instead, the exact validation failure reason is structured into a corrective guidance block:
```
CORRECTION REQUIRED FROM PREVIOUS ATTEMPT:
Your previous response failed integrity validation with error:
- Violated non-guarantee policy by asserting certainty: 'guaranteed return'

You MUST correct this in your revised response:
- Remove all positive guarantee claims, certainty promises, and causal assertions.
- Frame all findings strictly as statistical estimates and correlations based on historical data.
```

---

## 5. High-Performance Deterministic Fallback Engine

If no LLM provider is configured, the local server is offline, network requests timeout, or all LLM retry attempts fail validation, Prediqo's **Deterministic Fallback Engine** (`generate_deterministic_prediction_explanation` and `generate_deterministic_forecast_explanation`) produces structured business narratives using verified mathematical templates:
- Reconstructs actual predictions and baseline shifts with precise units.
- Categorizes top positive and negative drivers with formatted contributions.
- Synthesizes holdout performance metrics and naive-baseline improvement.
- Enforces non-causal disclosures, scale notices, and operational verifications.
- Guarantees 100% platform availability without external API dependencies.
- Sets `is_fallback: true` so the UI transparently signals fallback generation without presenting raw error messages.

---

## 6. Evidence Fingerprinting & Cache Architecture

To eliminate redundant LLM API costs and deliver sub-millisecond response times for identical predictions:
1. **Canonical JSON Serialization:** Canonical evidence dictionaries are serialized with sorted keys.
2. **SHA-256 Fingerprinting:** A deterministic hash is computed:
   $$\text{Fingerprint} = \text{SHA256}(\text{CanonicalEvidenceJSON})$$
3. **Compound Cache Key:**
   $$\text{CacheKey} = \text{type}:\text{Fingerprint}:\text{Provider}:\text{Model}:\text{PromptVersion}$$
4. **Thread-Safe In-Memory Cache:** Handled by `ExplanationCache` with LRU eviction and thread synchronization.
5. **Bypass Option:** Users can trigger explicit regeneration via `bypass_cache=true`.

---

## 7. API Endpoints

### 1. `GET /api/v1/ai/explain/status` (alias `/api/ai/explain/status`)
Returns provider configuration status, model defaults, prompt version, and cached item count:
```json
{
  "cached_explanations_count": 4,
  "providers": [
    {
      "provider_id": "ollama",
      "display_name": "Ollama (Local)",
      "available": true,
      "default_model": "llama3.2"
    }
  ],
  "prompt_version": "v1.1"
}
```

### 2. `POST /api/v1/ai/explain/prediction` (alias `/api/ai/explain/prediction`)
Generates structured narrative for a tabular ML prediction:
```json
{
  "target_name": "monthly_sales",
  "problem_type": "regression",
  "unit": "USD",
  "prediction": 45200.50,
  "baseline_reference_value": 38000.0,
  "decomposition_space": "ORIGINAL_TARGET_SPACE",
  "contributions": [
    { "feature": "marketing_spend", "contribution": 5200.50, "raw_value": 12000 }
  ],
  "metrics": { "r2": 0.88, "mae": 1200.0 },
  "provider": "ollama",
  "model": "llama3.2",
  "bypass_cache": false
}
```

### 3. `POST /api/v1/ai/explain/forecast` (alias `/api/ai/explain/forecast`)
Generates structured narrative for a time-series forecast.

### Response Schema (`AIExplanationResponse`):
```json
{
  "summary": "The model predicts monthly_sales will be 45,200.50 USD...",
  "what_the_result_means": "In an operational context, an estimated monthly_sales of 45,200.50 USD...",
  "supporting_evidence": [
    "Positive Driver: Feature 'marketing_spend' increased prediction by +5,200.50 USD..."
  ],
  "evaluation_quality": "Trained using Supervised ML. Holdout/CV R² is 0.88...",
  "uncertainty_and_limitations": [
    "Non-Causal Relationship: Feature attributions represent statistical associations..."
  ],
  "suggested_verifications": [
    "Verify that current input parameters reflect real operational conditions..."
  ],
  "provider": "ollama",
  "model": "llama3.2",
  "generated_at": "2026-10-12T16:51:57Z",
  "is_fallback": false,
  "cache_hit": true,
  "evidence_fingerprint": "ac4b5c1a009deb75fc81b61a914f67ad12a9317bca088e2ff28cefa5a8a56b13",
  "raw_evidence": { ... }
}
```

---

## 8. Frontend UI Integration

The `AIExplanationCard` component (`frontend/src/components/business/AIExplanationCard.tsx`) is seamlessly integrated into both enterprise centers:
- **`PredictionPage.tsx` (Prediction Center)**: Rendered inside the dedicated **`AI Explanation`** tab, following `PredictionInsightCard` and `HumanReadableXAICard`.
- **`ForecastingPage.tsx` (Forecasting Center)**: Rendered inside the dedicated **`AI Explanation`** tab, following `ForecastInsightCard`.

### UI Features:
- **Provider Selector:** Instant switching between Ollama (Local), Cloud LLMs (OpenAI, Groq, Gemini, Claude), and Deterministic Fallback.
- **On-Demand Generation:** User-initiated generation with loading skeleton and regeneration controls.
- **Integrity Pill Badges:** Provider badge, cache indicator (`⚡ Cached` vs `● Freshly Generated`), and fallback indicator (`Rules-Based Engine`).
- **Risk & Action Callouts:** High-contrast amber limitations card and emerald verification checklist.
- **User-Facing Error Shields:** Provider errors and technical failures are translated to clean business guidance with immediate fallback activation, preventing raw error message leaks.
- **Evidence Audit Drawer:** Collapsible panel exposing the SHA-256 fingerprint, generation timestamp, and normalized JSON evidence payload.

---

## 9. Verification and Testing

### Backend Test Suite (34 Dedicated AI Tests, 156 Total Tests):
```powershell
$env:PYTHONPATH="backend"
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_ai_explanations.py -v
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/ -q
```
Covers:
- **Clause-Level Semantic Integrity:** Distinguishes un-negated positive certainty assertions (rejected) from valid disclaimers (e.g. `"Forecast intervals represent statistical bounds, not a guaranteed outcome"`, accepted).
- **Prohibited Causal Language Rejection:** Rejects unwarranted claims like `"directly causes"` or `"guaranteed return"`.
- **Corrective Retry Pipeline:** Verifies bounded retries (default 2 retries, 3 attempts total) passing actionable feedback to the model.
- **Guaranteed Deterministic Fallback:** Verifies that persistent validation failures, network timeouts, or authentication errors fallback cleanly without 500 crashes.
- **Local Ollama Support:** Dynamic model fallback and graceful offline degradation.
- **Evidence Fingerprinting & Caching:** SHA-256 canonical hashing and deterministic cache hits across identical evidence.
- **Dual-Mounted FastAPI Endpoints:** Verified on both `/api/ai/explain` and `/api/v1/ai/explain`.

### Frontend Test Suite (4 Dedicated AI Tests, 29 Total Tests):
```powershell
npx tsx --test frontend/tests/aiExplanation.test.ts
npm --prefix frontend run build
```
Covers:
- AI explanation contract validation (`frontend/tests/aiExplanation.test.ts`).
- Normalized feature contributions and units mapping.
- Clean production Vite bundling with 0 TypeScript compilation errors.



