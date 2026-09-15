import React, { useState, useEffect, useCallback } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Header } from './components/Header';
import { PipelineStepper } from './components/PipelineStepper';
import { AgentWorkspace } from './components/agent/AgentWorkspace';
import { ArtifactInspector } from './components/inspector/ArtifactInspector';
import { ReviewSignOffModal } from './components/agent/ReviewSignOffModal';

import {
  Scenario,
  TelemetryData,
  SpectrumData,
  TopologyData,
  RCAState,
  LatestIncident,
} from './types';

import {
  fetchHealth,
  fetchScenarios,
  fetchTelemetry,
  fetchSpectrum,
  fetchTopology,
  fetchRCAState,
  runRCAPipeline,
  submitHumanReview,
  fetchLatestIncident,
  subscribeTelemetryEvents,
} from './api';

export function App() {
  const [inspectorTab, setInspectorTab] = useState<string>('telemetry');
  const [activeScenarioId, setActiveScenarioId] = useState<string>('live_stream');
  const [deepseekModel, setDeepseekModel] = useState<string>('deepseek-chat');
  const [isReviewModalOpen, setIsReviewModalOpen] = useState<boolean>(false);

  // Application Data States
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [spectrum, setSpectrum] = useState<SpectrumData | null>(null);
  const [topology, setTopology] = useState<TopologyData | null>(null);
  const [rcaState, setRcaState] = useState<RCAState | null>(null);
  const [latestIncident, setLatestIncident] = useState<LatestIncident | null>(null);

  // Status flags
  const [apiOnline, setApiOnline] = useState<boolean>(true);
  const [_isLoading, setIsLoading] = useState<boolean>(true);
  const [isPipelineRunning, setIsPipelineRunning] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [activeThreadId, setActiveThreadId] = useState<string>(
    `rca-gui-${Date.now()}`
  );

  // Initialize and load base data
  const loadInitialData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage(null);

      // 1. Health check
      try {
        await fetchHealth();
        setApiOnline(true);
      } catch {
        setApiOnline(false);
      }

      // 2. Fetch scenarios
      const scList = await fetchScenarios();
      setScenarios(scList);

      // 3. Fetch latest HIL incident
      try {
        const inc = await fetchLatestIncident();
        setLatestIncident(inc);
      } catch (e) {
        console.warn('Failed to fetch latest incident:', e);
      }

      // 4. Fetch Topology
      const topo = await fetchTopology('VFD_VM_01');
      setTopology(topo);
    } catch (err: any) {
      console.error('Initialization error:', err);
      setErrorMessage(err.message || 'Failed to connect to Industrial RCA backend.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load telemetry, spectrum, and run/load RCA for selected scenario
  const loadScenarioData = useCallback(
    async (scenarioId: string, threadId: string) => {
      try {
        setIsPipelineRunning(true);
        setErrorMessage(null);

        // Target asset determination based on active scenario
        const targetAssetId = 'VFD_VM_01';

        // Fetch timeseries, spectrum, and topology for target asset
        const [telData, specData, topoData] = await Promise.all([
          fetchTelemetry(scenarioId),
          fetchSpectrum(scenarioId),
          fetchTopology(targetAssetId),
        ]);
        setTelemetry(telData);
        setSpectrum(specData);
        setTopology(topoData);

        // Run LangGraph pipeline for this scenario & thread
        await runRCAPipeline({
          dataset_id: scenarioId,
          asset_id: targetAssetId,
          thread_id: threadId,
          use_deepseek: true,
          deepseek_model: deepseekModel,
        });

        // Fetch full RCA state
        const state = await fetchRCAState(threadId);
        setRcaState(state);
      } catch (err: any) {
        console.error('Scenario load error:', err);
        setErrorMessage(err.message || 'Failed to load telemetry data.');
      } finally {
        setIsPipelineRunning(false);
      }
    },
    [deepseekModel]
  );

  // Mount effect
  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Load scenario when scenarioId or threadId changes
  useEffect(() => {
    if (activeScenarioId) {
      loadScenarioData(activeScenarioId, activeThreadId);
    }
  }, [activeScenarioId, activeThreadId, loadScenarioData]);

  // Reactive SSE listener for live edge HIL events
  useEffect(() => {
    const unsubscribe = subscribeTelemetryEvents(
      (eventData) => {
        if (eventData.event === 'hil_incident_detected') {
          const incData = eventData.data;
          setLatestIncident({
            has_incident: true,
            incident_data: incData,
            received_at: new Date().toLocaleTimeString(),
            pipeline_status: 'TRIGGERED',
          });
          // Refresh scenario list
          fetchScenarios().then(setScenarios).catch(console.error);

          // Hands-free auto-switch to the live incident
          if (incData?.dataset_id) {
            setActiveScenarioId(incData.dataset_id);
            setActiveThreadId(`rca-live-${incData.incident_id || Date.now()}`);
            setInspectorTab('telemetry');
          }
        } else if (eventData.event === 'hil_pipeline_completed') {
          if (latestIncident?.incident_data) {
            setLatestIncident((prev) =>
              prev ? { ...prev, pipeline_status: 'ANALYSIS_COMPLETE' } : null
            );
          }
        }
      },
      (err) => {
        console.warn('SSE event stream disconnected:', err);
      }
    );

    return () => unsubscribe();
  }, [latestIncident]);

  // 1-Click Load Incident handler
  const handleLoadLiveIncident = () => {
    if (latestIncident?.incident_data?.dataset_id) {
      const hilDsId = latestIncident.incident_data.dataset_id;
      setActiveScenarioId(hilDsId);
      setInspectorTab('telemetry');
    }
  };

  // Reset Pipeline
  const handleResetPipeline = () => {
    const newThread = `rca-gui-${Date.now()}`;
    setActiveThreadId(newThread);
    loadScenarioData(activeScenarioId, newThread);
  };

  // Submit Human Review from Modal
  const handleSubmitReview = async (params: {
    action: string;
    reviewer: string;
    notes: string;
    override_root_cause?: string;
  }) => {
    try {
      setIsPipelineRunning(true);
      await submitHumanReview({
        thread_id: activeThreadId,
        action: params.action,
        reviewer: params.reviewer,
        notes: params.notes,
        override_root_cause: params.override_root_cause,
      });

      // Reload state after resume
      const updatedState = await fetchRCAState(activeThreadId);
      setRcaState(updatedState);

      if (params.action === 'approve' || params.action === 'override') {
        // Jump directly to Deliverables tab!
        setInspectorTab('deliverables');
      }
    } catch (err: any) {
      console.error('Review submission failed:', err);
      throw err;
    } finally {
      setIsPipelineRunning(false);
    }
  };

  const activeScenario = scenarios.find((s) => s.id === activeScenarioId);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 flex flex-col font-sans selection:bg-teal-500/20 selection:text-teal-900">
      {/* Top Header Navbar */}
      <Header
        scenarios={scenarios}
        activeScenarioId={activeScenarioId}
        onSelectScenario={(sId) => setActiveScenarioId(sId)}
        apiOnline={apiOnline}
        latestIncident={latestIncident}
        onLoadIncident={handleLoadLiveIncident}
        onResetPipeline={handleResetPipeline}
        deepseekModel={deepseekModel}
        onToggleModel={setDeepseekModel}
        isPipelineRunning={isPipelineRunning}
      />

      {/* 7-Step Macro Stepper */}
      <PipelineStepper
        currentStep={rcaState?.current_step || 1}
        isPausedAtHitl={rcaState?.is_paused_at_hitl || false}
        pipelineStatus={rcaState?.pipeline_status || 'READY'}
      />

      {/* Error Alert Banner */}
      {errorMessage && (
        <div className="bg-rose-50 border-b border-rose-200 px-4 py-2 flex items-center justify-between text-xs font-mono text-rose-700">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => loadInitialData()}
            className="flex items-center space-x-1 px-2.5 py-1 bg-white border border-rose-200 rounded text-rose-700 hover:bg-rose-100 shadow-xs cursor-pointer"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {/* Agent-First Split Workspace Layout */}
      <main className="flex-1 max-w-[1720px] w-full mx-auto p-4 flex flex-col lg:flex-row gap-4 min-h-0">
        {/* Left Pane: Agent Workspace (~48-50% width) */}
        <section className="w-full lg:w-[48%] flex flex-col h-auto lg:h-[calc(100vh-140px)] min-h-[620px] lg:min-h-0">
          <AgentWorkspace
            rcaState={rcaState}
            apiOnline={apiOnline}
            deepseekModel={deepseekModel}
            onSelectInspectorTab={(tabId) => setInspectorTab(tabId)}
            onOpenReviewModal={() => setIsReviewModalOpen(true)}
            activeScenarioName={activeScenario?.name}
            isPipelineRunning={isPipelineRunning}
          />
        </section>

        {/* Right Pane: Artifact Inspector (~50-52% width) */}
        <section className="w-full lg:w-[52%] flex flex-col h-auto lg:h-[calc(100vh-140px)] min-h-[620px] lg:min-h-0">
          <ArtifactInspector
            activeTab={inspectorTab}
            onSelectTab={(tabId) => setInspectorTab(tabId)}
            telemetry={telemetry}
            spectrum={spectrum}
            topology={topology}
            rcaState={rcaState}
            activeScenarioId={activeScenarioId}
          />
        </section>
      </main>

      {/* Sign-Off & Authorization Modal */}
      <ReviewSignOffModal
        isOpen={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        rcaState={rcaState}
        onSubmitReview={handleSubmitReview}
      />

      {/* Minimal Footer */}
      <footer className="border-t border-slate-200 bg-white py-2 px-4 text-center text-slate-500 font-mono text-[11px] flex flex-wrap items-center justify-between gap-2 max-w-[1720px] mx-auto w-full">
        <div>
          Global PetroChem Refining Corp · Machinery Reliability Center of Excellence
        </div>
        <div className="flex items-center space-x-3">
          <span>Standards: ISA-95 · ISO 14224 · ISO 10816 · Global 8D</span>
          <span>·</span>
          <span>Orchestration: LangGraph & DeepSeek AI</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
