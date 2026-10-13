import { useEffect, useState } from 'react'
import {
  getPredictionFeasibility,
  trainPredictionModel,
  listPredictionModels,
  predictSingle,
  getLocalExplanation,
  getGlobalExplanation,
} from '../services/api'
import type {
  FeasibilityResponse,
  TargetCandidate,
  TrainResponse,
  PredictResponse,
  ModelListItem,
  LocalExplanationResponse,
  GlobalExplanationResponse,
} from '../types'
import CenterHeader from '../components/centers/CenterHeader'
import CenterNavTabs, { type CenterTabId } from '../components/centers/CenterNavTabs'
import PredictionConfigPanel from '../components/prediction/PredictionConfigPanel'
import PredictionOverviewTab from '../components/prediction/PredictionOverviewTab'
import PredictionAnalyticsTab from '../components/prediction/PredictionAnalyticsTab'
import PredictionAIExplanationTab from '../components/prediction/PredictionAIExplanationTab'
import PredictionTechnicalTab from '../components/prediction/PredictionTechnicalTab'

export default function PredictionPage() {
  const [datasetId, setDatasetId] = useState<string>('')
  const [activeTab, setActiveTab] = useState<CenterTabId>('overview')
  const [isConfigOpen, setIsConfigOpen] = useState<boolean>(true)

  // Feasibility & Target Setup
  const [feasibility, setFeasibility] = useState<FeasibilityResponse | null>(null)
  const [loadingFeasibility, setLoadingFeasibility] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const [selectedTarget, setSelectedTarget] = useState<string>('')
  const [targetCandidate, setTargetCandidate] = useState<TargetCandidate | null>(null)
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])
  const [excludedFeatures, setExcludedFeatures] = useState<string[]>([])
  const [cvFolds, setCvFolds] = useState<number>(5)
  const [validationStrategy, setValidationStrategy] = useState<string>('kfold')
  const [selectedGroupCol, setSelectedGroupCol] = useState<string>('')

  // Training state
  const [training, setTraining] = useState<boolean>(false)
  const [trainResult, setTrainResult] = useState<TrainResponse | null>(null)
  const [savedModels, setSavedModels] = useState<ModelListItem[]>([])
  const [activeModelId, setActiveModelId] = useState<string>('')

  // Inference state
  const [predictInputs, setPredictInputs] = useState<Record<string, any>>({})
  const [predicting, setPredicting] = useState<boolean>(false)
  const [predictResult, setPredictResult] = useState<PredictResponse | null>(null)

  // Explainability (XAI) state
  const [localExplanation, setLocalExplanation] = useState<LocalExplanationResponse | null>(null)
  const [loadingLocalExp, setLoadingLocalExp] = useState<boolean>(false)
  const [globalExplanation, setGlobalExplanation] = useState<GlobalExplanationResponse | null>(null)
  const [loadingGlobalExp, setLoadingGlobalExp] = useState<boolean>(false)

  // 1. Load feasibility and saved models on dataset change
  useEffect(() => {
    if (!datasetId) {
      setFeasibility(null)
      setTrainResult(null)
      setPredictResult(null)
      setLocalExplanation(null)
      setGlobalExplanation(null)
      setSavedModels([])
      return
    }

    setLoadingFeasibility(true)
    setError(null)
    setTrainResult(null)
    setPredictResult(null)
    setLocalExplanation(null)
    setGlobalExplanation(null)

    getPredictionFeasibility(datasetId)
      .then((data) => {
        setFeasibility(data)
        const defaultTarget =
          data.recommended_targets[0] ||
          data.regression_targets[0]?.name ||
          data.classification_targets[0]?.name ||
          ''
        setSelectedTarget(defaultTarget)
      })
      .catch((err) => {
        setError(err.message || 'Failed to check prediction feasibility.')
      })
      .finally(() => {
        setLoadingFeasibility(false)
      })

    listPredictionModels(datasetId)
      .then((res) => setSavedModels(res.models || []))
      .catch(() => setSavedModels([]))
  }, [datasetId])

  // 2. Update target candidate & features when target changes
  useEffect(() => {
    if (!feasibility || !selectedTarget) return

    const allCandidates = [
      ...feasibility.regression_targets,
      ...feasibility.classification_targets,
    ]

    const cand = allCandidates.find((t) => t.name === selectedTarget) || null
    setTargetCandidate(cand)

    const feats = allCandidates
      .map((f) => f.name)
      .filter((name) => name !== selectedTarget)
    setSelectedFeatures(feats)

    const excluded = (feasibility.columns_info || [])
      .map((c) => c.name)
      .filter((name) => !feats.includes(name))
    setExcludedFeatures(excluded)
  }, [selectedTarget, feasibility])

  // 3. Train Model Action
  const handleTrain = async () => {
    if (!datasetId || !selectedTarget) return
    setTraining(true)
    setError(null)
    setPredictResult(null)
    setLocalExplanation(null)
    setGlobalExplanation(null)

    try {
      const res = await trainPredictionModel({
        dataset_id: datasetId,
        target_column: selectedTarget,
        problem_type: targetCandidate?.problem_type,
        features: selectedFeatures,
        validation_strategy: validationStrategy,
        cv_folds: cvFolds,
        group_column: validationStrategy === 'group' ? selectedGroupCol : null,
      })

      setTrainResult(res)
      setActiveModelId(res.model_id)

      // Initialize default inputs with 0 or empty
      const initialInputs: Record<string, any> = {}
      res.selected_features.forEach((feat) => {
        initialInputs[feat] = ''
      })
      setPredictInputs(initialInputs)

      // Refresh saved models list
      const updatedList = await listPredictionModels(datasetId)
      setSavedModels(updatedList.models || [])
    } catch (err: any) {
      setError(err.message || 'Model training failed.')
    } finally {
      setTraining(false)
    }
  }

  // 4. Predict Single Action
  const handlePredict = async () => {
    const modelId = activeModelId || trainResult?.model_id
    if (!modelId) return

    setPredicting(true)
    setError(null)

    try {
      const res = await predictSingle(modelId, predictInputs)
      setPredictResult(res)

      // Automatically fetch local XAI feature contributions
      setLoadingLocalExp(true)
      try {
        const xaiRes = await getLocalExplanation({
          model_id: modelId,
          features: predictInputs,
        })
        setLocalExplanation(xaiRes)
      } catch (xaiErr: any) {
        console.warn('Local XAI calculation skipped or failed:', xaiErr)
      } finally {
        setLoadingLocalExp(false)
      }
    } catch (err: any) {
      setError(err.message || 'Prediction failed. Check input values.')
    } finally {
      setPredicting(false)
    }
  }

  // 5. Load Global Explanation
  const handleLoadGlobalExplanation = async () => {
    const modelId = activeModelId || trainResult?.model_id
    if (!modelId) return

    setLoadingGlobalExp(true)
    try {
      const res = await getGlobalExplanation(modelId, 100)
      setGlobalExplanation(res)
    } catch (err: any) {
      console.warn('Global explanation failed:', err)
    } finally {
      setLoadingGlobalExp(false)
    }
  }

  // 6. Reset Scenario Inputs
  const handleResetInputs = () => {
    if (!trainResult) return
    const initialInputs: Record<string, any> = {}
    trainResult.selected_features.forEach((feat) => {
      initialInputs[feat] = ''
    })
    setPredictInputs(initialInputs)
    setPredictResult(null)
    setLocalExplanation(null)
  }

  // 7. Select Saved Model
  const handleSelectSavedModel = (modelId: string, targetCol: string) => {
    setActiveModelId(modelId)
    setSelectedTarget(targetCol)
  }

  const activeModelLabel = trainResult
    ? `${trainResult.best_model.algorithm} · ${trainResult.problem_type.toUpperCase()}`
    : savedModels.length > 0
    ? `${savedModels.length} Saved Models Available`
    : null

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Shared Enterprise Header */}
      <CenterHeader
        currentCenter="prediction"
        title="Prediction Center"
        subtitle="Predict business outcomes from your data."
        datasetId={datasetId}
        onDatasetChange={setDatasetId}
        activeModelLabel={activeModelLabel}
        badgeColor="emerald"
        actionSlot={
          trainResult && (
            <button
              type="button"
              onClick={() => setIsConfigOpen(!isConfigOpen)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 transition-colors shadow-2xs flex items-center gap-1.5 cursor-pointer"
            >
              <span>{isConfigOpen ? '◀ Hide Setup' : '⚙ Show Setup Panel'}</span>
            </button>
          )
        }
      />

      {/* Error Alert Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs shadow-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-rose-500 hover:text-rose-700 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* 2. Top 4-Tab Navigation */}
      <CenterNavTabs
        activeTab={activeTab}
        onChange={setActiveTab}
        disabledTabs={!trainResult ? ['analytics', 'explanation', 'technical'] : []}
      />

      {/* 3. Main Center Workspace */}
      {datasetId ? (
        <div className={`grid grid-cols-1 ${isConfigOpen ? 'lg:grid-cols-12' : 'lg:grid-cols-1'} gap-6 items-start`}>
          {/* Left Configuration Panel (Collapsible) */}
          {isConfigOpen && (
            <div className="lg:col-span-4 xl:col-span-3">
              <PredictionConfigPanel
                feasibility={feasibility}
                loadingFeasibility={loadingFeasibility}
                selectedTarget={selectedTarget}
                onTargetChange={setSelectedTarget}
                targetCandidate={targetCandidate}
                selectedFeatures={selectedFeatures}
                onFeaturesChange={setSelectedFeatures}
                excludedFeatures={excludedFeatures}
                cvFolds={cvFolds}
                onCvFoldsChange={setCvFolds}
                validationStrategy={validationStrategy}
                onValidationStrategyChange={setValidationStrategy}
                selectedGroupCol={selectedGroupCol}
                onGroupColChange={setSelectedGroupCol}
                training={training}
                onTrain={handleTrain}
                savedModels={savedModels}
                activeModelId={activeModelId}
                onSelectSavedModel={handleSelectSavedModel}
              />
            </div>
          )}

          {/* Right Main Content Tabs (Preserves State) */}
          <div className={isConfigOpen ? 'lg:col-span-8 xl:col-span-9' : 'lg:col-span-1'}>
            {activeTab === 'overview' && (
              <PredictionOverviewTab
                trainResult={trainResult}
                targetCandidate={targetCandidate}
                feasibility={feasibility}
                predictInputs={predictInputs}
                onInputChange={(f, v) => setPredictInputs({ ...predictInputs, [f]: v })}
                predicting={predicting}
                onPredict={handlePredict}
                onResetInputs={handleResetInputs}
                predictResult={predictResult}
                localExplanation={localExplanation}
                loadingLocalExp={loadingLocalExp}
                onNavigateTab={(tab) => setActiveTab(tab)}
              />
            )}

            {activeTab === 'analytics' && (
              <PredictionAnalyticsTab
                trainResult={trainResult}
                feasibility={feasibility}
                targetCandidate={targetCandidate}
                localExplanation={localExplanation}
                globalExplanation={globalExplanation}
                loadingGlobalExp={loadingGlobalExp}
                onLoadGlobalExplanation={handleLoadGlobalExplanation}
              />
            )}

            {activeTab === 'explanation' && (
              <PredictionAIExplanationTab
                datasetId={datasetId}
                trainResult={trainResult}
                targetCandidate={targetCandidate}
                feasibility={feasibility}
                predictResult={predictResult}
                localExplanation={localExplanation}
                activeModelId={activeModelId}
              />
            )}

            {activeTab === 'technical' && (
              <PredictionTechnicalTab
                trainResult={trainResult}
                targetCandidate={targetCandidate}
              />
            )}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200/80 p-16 text-center shadow-sm space-y-3">
          <div className="text-4xl">📂</div>
          <h3 className="text-base font-bold text-slate-900">No Dataset Selected</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Please choose a standardized dataset from the active dataset selector above to configure and evaluate predictive machine learning models.
          </p>
        </div>
      )}
    </div>
  )
}
