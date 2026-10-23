import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Brain,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileCheck,
  Send,
  Sparkles,
  Loader2,
  Terminal,
  CheckCircle2,
  Bot,
  RotateCcw,
  Activity,
  Key,
} from 'lucide-react';
import { RCAState, ChatMessage, ToolExecutionItem, LatestIncident, LiveMetric, ApiKeyStatus } from '../../types';
import { streamCopilotChat, fetchLiveMetrics, subscribeLiveTelemetryStream } from '../../api';
import { PipelineStepper } from '../PipelineStepper';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MarkdownContent: React.FC<{ content: string }> = ({ content }) => {
  return (
    <div className="markdown-content text-slate-800 text-xs leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ ...props }) => (
            <div className="overflow-x-auto my-3 rounded-lg border border-slate-200 shadow-2xs bg-white">
              <table className="min-w-full divide-y divide-slate-200 text-xs text-left" {...props} />
            </div>
          ),
          thead: ({ ...props }) => (
            <thead className="bg-slate-50 font-mono text-[11px] text-slate-700 font-bold uppercase tracking-wider" {...props} />
          ),
          th: ({ ...props }) => (
            <th className="px-3 py-2 border-b border-slate-200 text-slate-700 font-semibold" {...props} />
          ),
          tbody: ({ ...props }) => (
            <tbody className="divide-y divide-slate-100 bg-white font-sans" {...props} />
          ),
          tr: ({ ...props }) => (
            <tr className="hover:bg-slate-50/70 transition-colors" {...props} />
          ),
          td: ({ ...props }) => (
            <td className="px-3 py-2 text-slate-700 text-xs align-top" {...props} />
          ),
          p: ({ ...props }) => (
            <p className="leading-relaxed mb-2 last:mb-0 text-xs text-slate-800" {...props} />
          ),
          strong: ({ ...props }) => (
            <strong className="font-semibold text-slate-900" {...props} />
          ),
          ul: ({ ...props }) => (
            <ul className="list-disc list-outside pl-4 space-y-1.5 my-2.5 text-slate-700 text-xs" {...props} />
          ),
          ol: ({ ...props }) => (
            <ol className="list-decimal list-outside pl-4 space-y-1.5 my-2.5 text-slate-700 text-xs" {...props} />
          ),
          li: ({ ...props }) => (
            <li className="leading-relaxed pl-0.5" {...props} />
          ),
          h1: ({ ...props }) => (
            <h1 className="text-sm font-bold text-slate-900 mt-3 mb-1.5" {...props} />
          ),
          h2: ({ ...props }) => (
            <h2 className="text-xs font-bold font-mono text-slate-900 mt-2.5 mb-1" {...props} />
          ),
          h3: ({ ...props }) => (
            <h3 className="text-xs font-semibold text-slate-800 mt-2 mb-1" {...props} />
          ),
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || '');
            const isInline = !match && typeof children === 'string' && !children.includes('\n');
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 font-mono text-[11px] border border-slate-200/80" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <pre className="p-3 my-2.5 rounded-lg bg-slate-900 text-slate-100 font-mono text-[11px] overflow-x-auto shadow-xs">
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            );
          },
          blockquote: ({ ...props }) => (
            <blockquote className="border-l border-teal-500 bg-teal-50/50 px-3 py-2 my-2.5 rounded-r text-xs text-teal-900" {...props} />
          ),
          hr: ({ ...props }) => (
            <hr className="my-3 border-slate-200" {...props} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

interface AgentWorkspaceProps {
  rcaState: RCAState | null;
  latestIncident?: LatestIncident | null;
  apiOnline: boolean;
  deepseekModel: string;
  onSelectInspectorTab: (tabId: string) => void;
  onOpenReviewModal: () => void;
  activeScenarioName?: string;
  isPipelineRunning?: boolean;
  apiKeyStatus?: ApiKeyStatus | null;
  onOpenApiKeyModal?: () => void;
}

export const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({
  rcaState,
  latestIncident,
  apiOnline: _apiOnline,
  deepseekModel,
  onSelectInspectorTab,
  onOpenReviewModal,
  activeScenarioName: _activeScenarioName = 'Emergency Trip (Strainer Clog)',
  isPipelineRunning = false,
  apiKeyStatus,
  onOpenApiKeyModal,
}) => {
  // Collapsible States for RCA Mission (Turn 1)
  const [isCoTExpanded, setIsCoTExpanded] = useState<boolean>(false);
  const [isToolsGroupExpanded, setIsToolsGroupExpanded] = useState<boolean>(true);
  const [expandedToolIds, setExpandedToolIds] = useState<Record<string, boolean>>({});

  // Collapsible States for Chat Message Items
  const [expandedChatCoT, setExpandedChatCoT] = useState<Record<string, boolean>>({});
  const [expandedChatTools, setExpandedChatTools] = useState<Record<string, boolean>>({});

  // Chat conversation state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [currentReasoning, setCurrentReasoning] = useState<string>('');
  const [currentContent, setCurrentContent] = useState<string>('');
  const [activeStreamingTools, setActiveStreamingTools] = useState<ToolExecutionItem[]>([]);
  const [liveMetric, setLiveMetric] = useState<LiveMetric | null>(null);

  useEffect(() => {
    fetchLiveMetrics().then(setLiveMetric).catch(() => {});
    const unsubscribe = subscribeLiveTelemetryStream((metric) => {
      setLiveMetric(metric);
    });
    return () => unsubscribe();
  }, []);

  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll when chat or streaming updates
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentContent, currentReasoning, isPipelineRunning]);

  const toggleToolExpanded = (id: string) => {
    setExpandedToolIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleChatToolExpanded = (id: string) => {
    setExpandedChatTools((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleChatCoT = (msgId: string) => {
    setExpandedChatCoT((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const isRigNominalRunning = Boolean(
    liveMetric &&
    liveMetric.telemetry_connected !== false &&
    liveMetric.status === 'RUNNING' &&
    liveMetric.fault_code === 0 &&
    (liveMetric.f_out > 0.5 || liveMetric.rpm > 10.0) &&
    !latestIncident?.has_incident
  );

  const rawFaultCode = latestIncident?.incident_data?.fault_code ?? rcaState?.fault_code ?? 0;

  const faultCode = isRigNominalRunning ? 0 : rawFaultCode;

  const isIncidentActive = Boolean(
    !isRigNominalRunning &&
    (latestIncident?.has_incident ||
     rcaState?.has_active_trip ||
     faultCode > 0)
  );

  // Render only tools actually executed by the backend investigation.
  const autonomousTools: ToolExecutionItem[] = useMemo(() =>
    (rcaState?.agent_observations || []).map((observation): ToolExecutionItem => ({
      id: observation.observation_id,
      name: observation.tool,
      args: observation.arguments,
      status: observation.error ? 'failed' : 'completed',
      duration_ms: observation.elapsed_ms,
      summary: observation.error || `${observation.source_type} observation`,
      output_details: JSON.stringify(observation.result ?? observation.error ?? 'No result', null, 2),
      inspector_tab: observation.tool === 'trace_topology' ? 'topology' : 'hypotheses',
      tab_label: 'Inspect evidence',
    })), [rcaState?.agent_observations]);

  // Follow-up chat explains current context; no client-side tool executions are invented.
  const handleSendChat = (promptText?: string) => {
    const text = promptText || inputPrompt;
    if (!text.trim() || isStreaming) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setInputPrompt('');
    setIsStreaming(true);
    setCurrentReasoning('');
    setCurrentContent('');

    const chatTools: ToolExecutionItem[] = [];
    setActiveStreamingTools([]);

    const assistantMsgId = `asst-${Date.now()}`;
    let accumulatedContent = '';
    let accumulatedReasoning = '';
    const streamStartTime = Date.now();

    streamCopilotChat(
      newHistory.map((m) => ({ role: m.role, content: m.content })),
      deepseekModel,
      (delta) => {
        if (delta.reasoning_content) {
          accumulatedReasoning += delta.reasoning_content;
          setCurrentReasoning(accumulatedReasoning);
        }
        if (delta.content) {
          accumulatedContent += delta.content;
          setCurrentContent(accumulatedContent);
        }
      },
      () => {
        const elapsedSec = Math.max(0.1, Number(((Date.now() - streamStartTime) / 1000).toFixed(1)));
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content: accumulatedContent || 'The model returned no answer. Please try again.',
            reasoning_content: accumulatedReasoning || undefined,
            elapsed_time_sec: elapsedSec,
            tools: chatTools,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        setCurrentReasoning('');
        setCurrentContent('');
        setActiveStreamingTools([]);
        setIsStreaming(false);
      },
      (err) => {
        console.error('Chat error:', err);
        const elapsedSec = Math.max(0.1, Number(((Date.now() - streamStartTime) / 1000).toFixed(1)));
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content:
              `${accumulatedContent ? accumulatedContent + '\n\n' : ''}Copilot unavailable: ${err.message}. Check the API settings and try again.`,
            reasoning_content: accumulatedReasoning || undefined,
            elapsed_time_sec: elapsedSec,
            tools: chatTools,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        setCurrentReasoning('');
        setCurrentContent('');
        setActiveStreamingTools([]);
        setIsStreaming(false);
      },
      rcaState?.thread_id || latestIncident?.incident_data?.thread_id
    );
  };

  const handleClearChat = () => {
    setMessages([]);
    setCurrentReasoning('');
    setCurrentContent('');
    setActiveStreamingTools([]);
    setInputPrompt('');
    setExpandedChatTools({});
    setExpandedChatCoT({});
    setIsStreaming(false);
  };

  // Automatically reset chat when the active investigation thread changes
  const prevThreadIdRef = useRef<string | undefined>(rcaState?.thread_id);
  useEffect(() => {
    if (rcaState?.thread_id && prevThreadIdRef.current && rcaState.thread_id !== prevThreadIdRef.current) {
      handleClearChat();
    }
    prevThreadIdRef.current = rcaState?.thread_id;
  }, [rcaState?.thread_id]);

  const isTelemetryConnected = Boolean(
    liveMetric &&
    liveMetric.telemetry_connected !== false &&
    liveMetric.status !== 'OFFLINE'
  );

  const currentF = liveMetric && isTelemetryConnected ? liveMetric.f_out.toFixed(2) : '0.00';
  const currentVdc = liveMetric && isTelemetryConnected ? liveMetric.v_dc.toFixed(1) : '0.0';
  const currentA = liveMetric && isTelemetryConnected ? liveMetric.current.toFixed(2) : '0.00';
  const currentRpm = liveMetric && isTelemetryConnected ? liveMetric.rpm.toFixed(0) : '0';

  const defaultThinking = rcaState?.execution_logs?.join('\n') || 'No investigation has run.';
  const isPaused = rcaState?.is_paused_at_hitl || false;
  const isFinalized = rcaState?.pipeline_status === 'COMPLETED';
  const isStateResolved = ['CAUSAL_TRACE_COMPLETED', 'ANALYSIS_COMPLETE', 'COMPLETED', 'AWAITING_REVIEW', 'INCONCLUSIVE', 'REJECTED', 'NORMAL_STABLE'].includes(rcaState?.pipeline_status || '');
  const isPipelineActive = isPipelineRunning && !isStateResolved;
  const displayedThinking = defaultThinking;
  const displayedDiagnosis = rcaState?.pipeline_status === 'INCONCLUSIVE'
    ? `Investigation inconclusive. ${(rcaState.missing_evidence || []).join(' ')}`
    : rcaState?.root_cause_description || (isIncidentActive
      ? 'Investigation pending. No supported diagnosis is available.'
      : isTelemetryConnected
        ? `Latest readings: ${currentF} Hz, ${currentVdc} V DC, ${currentA} A, ${currentRpm} RPM. See configured limits and source details in telemetry.`
        : 'Telemetry is offline. Connect the gateway or enable simulation to collect data.');

  return (
    <div className="flex flex-col h-full bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden text-slate-800 font-sans">
      {/* Sleek Agent Terminal Header */}
      <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between gap-3">
        <div className="flex items-center space-x-2.5 min-w-0">
          <div className="w-6 h-6 rounded-md bg-teal-600/10 border border-teal-600/20 flex items-center justify-center text-teal-700 flex-shrink-0">
            <Bot className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono font-bold text-slate-800 truncate">
                Industrial RCA Agent
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 font-bold">
                V4 Flash
              </span>
            </div>
            <div className="text-[11px] text-slate-500 font-mono truncate">
              Asset: <span className="font-semibold text-slate-700">VFD_VM_01</span> · Modbus 1 Hz Stream
            </div>
          </div>
        </div>

        {/* Live Status Indicators & Actions */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          <button
            type="button"
            onClick={handleClearChat}
            disabled={isStreaming || (messages.length === 0 && !currentContent && !inputPrompt)}
            className="flex items-center space-x-1.5 px-2.5 py-1 text-[11px] font-mono font-medium text-slate-600 hover:text-slate-900 bg-white hover:bg-slate-100 active:bg-slate-200 border border-slate-200 rounded-md transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-2xs"
            title="Reset chat conversation"
          >
            <RotateCcw className={`w-3 h-3 text-slate-500 ${isStreaming ? 'animate-spin' : ''}`} />
            <span>Reset Chat</span>
          </button>

          {isPipelineActive && (
            <span className="flex items-center space-x-1.5 text-[11px] font-mono text-amber-700 bg-amber-50 border border-amber-200/80 px-2 py-0.5 rounded-md animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin text-amber-600" />
              <span>Analyzing</span>
            </span>
          )}

          {isIncidentActive ? (
            <span className="flex items-center space-x-1.5 text-[11px] font-mono font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-md">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
              <span>Trip: {faultCode >= 10 ? `Err${faultCode}` : `Err0${faultCode}`}</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1.5 text-[11px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Monitoring</span>
            </span>
          )}
        </div>
      </div>

      {/* Main Agent Feed (Unified Chronological Trace) */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 text-xs font-sans">
        {/* ================= TURN 1: Autonomous RCA Mission ================= */}
        <div className="space-y-2.5">
          {/* User / Mission Prompt */}
          <div className="flex items-start space-x-2.5">
            <div className="w-5 h-5 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center text-slate-600 text-[10px] font-bold flex-shrink-0 mt-0.5">
              ⚡
            </div>
            <div className="font-mono text-xs text-slate-800 font-semibold bg-slate-100/70 border border-slate-200 rounded-lg px-3 py-1.5 w-full">
              {isIncidentActive
                ? `Investigate hardware trip ${faultCode >= 10 ? `Err${faultCode}` : `Err0${faultCode}`} on Wecon VFD Rig (VFD_VM_01). Trace root cause and generate ISO 14224 / 8D deliverables.`
                : `Continuous monitoring and diagnostic readiness on Wecon VFD Rig (VFD_VM_01).`}
            </div>
          </div>

          {/* LangGraph 7-Step Autonomous Diagnostic Plan Stepper */}
          <div className="pl-7">
            <PipelineStepper
              currentStep={rcaState?.current_step || (isIncidentActive ? 7 : 1)}
              isPausedAtHitl={rcaState?.is_paused_at_hitl || false}
              pipelineStatus={rcaState?.pipeline_status || (isIncidentActive ? 'ANALYSIS_COMPLETE' : 'MONITORING')}
              compact={true}
              onSelectStepTab={onSelectInspectorTab}
            />
          </div>

          {/* Reasoning Trace (CoT) - Matching Coding Agent Style */}
          <div className="pl-7">
            {isPipelineActive ? (
              <div className="flex items-center space-x-2 text-purple-700 font-mono text-xs py-1">
                <Brain className="w-3.5 h-3.5 animate-pulse text-purple-600" />
                <span className="animate-pulse">Thinking through telemetry and failure hypotheses...</span>
              </div>
            ) : (
              <div className="border border-purple-100 bg-purple-50/30 rounded-md overflow-hidden">
                <button
                  onClick={() => setIsCoTExpanded(!isCoTExpanded)}
                  className="w-full px-2.5 py-1.5 flex items-center justify-between text-left font-mono text-[11px] text-purple-800 hover:bg-purple-100/50 transition-colors cursor-pointer group"
                >
                  <div className="flex items-center space-x-2">
                    <Brain className="w-3.5 h-3.5 text-purple-600" />
                    <span className="font-semibold text-slate-700 group-hover:text-purple-900">
                      Investigation trace
                    </span>
                    <span className="text-slate-400 font-normal">
                      ({displayedThinking.split('\n').length} diagnostic steps)
                    </span>
                  </div>
                  {isCoTExpanded ? (
                    <ChevronDown className="w-3.5 h-3.5 text-purple-600" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-purple-600" />
                  )}
                </button>

                {isCoTExpanded && (
                  <div className="px-3 py-2 border-t border-purple-100 bg-white font-mono text-[11px] text-slate-600 leading-relaxed whitespace-pre-line">
                    {displayedThinking}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Grouped Tool Executions (Coding Agent Style matching Image 2) */}
          <div className="pl-7 space-y-1.5">
            <div className="border border-slate-200 rounded-md overflow-hidden bg-slate-50/40">
              {/* Tool Group Header */}
              <button
                onClick={() => setIsToolsGroupExpanded(!isToolsGroupExpanded)}
                className="w-full px-2.5 py-1.5 flex items-center justify-between text-left font-mono text-[11px] text-slate-700 hover:bg-slate-100/70 transition-colors cursor-pointer"
              >
                <div className="flex items-center space-x-2">
                  <Terminal className="w-3.5 h-3.5 text-slate-500" />
                  <span className="font-semibold">
                    {isPipelineActive
                      ? `Running ${autonomousTools.length} diagnostic tools...`
                      : `Ran ${autonomousTools.length} diagnostic tools`}
                  </span>
                </div>
                {isToolsGroupExpanded ? (
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                )}
              </button>

              {/* Nested Tool Execution Rows */}
              {isToolsGroupExpanded && (
                <div className="divide-y divide-slate-100 border-t border-slate-200 bg-white">
                  {autonomousTools.map((tool) => {
                    const isExpanded = !!expandedToolIds[tool.id];
                    return (
                      <div key={tool.id} className="text-[11px] font-mono">
                        {/* Summary Line matching Image 2 */}
                        <div className="px-3 py-1.5 flex items-center justify-between hover:bg-slate-50 transition-colors">
                          <button
                            onClick={() => toggleToolExpanded(tool.id)}
                            className="flex items-center space-x-2 text-left text-slate-700 hover:text-slate-900 cursor-pointer min-w-0 flex-1 pr-2"
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-3 h-3 text-slate-400 flex-shrink-0" />
                            ) : (
                              <ChevronRight className="w-3 h-3 text-slate-400 flex-shrink-0" />
                            )}
                            <span className="text-slate-500 flex-shrink-0">Ran</span>
                            <span className="font-semibold text-slate-800 flex-shrink-0">
                              {tool.name}
                            </span>
                            <span className="text-slate-500 truncate font-normal">
                              {tool.summary}
                            </span>
                          </button>

                          {/* 1-Click Action Link to Right-Panel Tab */}
                          {tool.inspector_tab && (
                            <button
                              onClick={() => onSelectInspectorTab(tool.inspector_tab!)}
                              className="text-teal-600 hover:text-teal-800 font-semibold flex items-center space-x-1 flex-shrink-0 hover:underline cursor-pointer pl-2 text-[10px]"
                            >
                              <span>[{tool.tab_label || 'Inspect'}]</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </button>
                          )}
                        </div>

                        {/* Expandable Accordion: Command, Parameters, Output, and Logs */}
                        {isExpanded && (
                          <div className="px-3 py-2 bg-slate-50/60 border-t border-slate-100 space-y-2 text-[11px] font-mono">
                            {tool.command && (
                              <div className="text-slate-500 text-[10px]">
                                <span className="text-slate-400">$ </span>
                                <code>{tool.command}</code>
                              </div>
                            )}

                            {/* Arguments Preview */}
                            {tool.args && (
                              <div className="p-2 rounded bg-white border border-slate-200/80 text-slate-600">
                                <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">
                                  Invocation Parameters
                                </div>
                                <pre className="text-[10px] overflow-x-auto text-slate-700">
                                  {JSON.stringify(tool.args, null, 2)}
                                </pre>
                              </div>
                            )}

                            {/* Output Preview */}
                            {tool.output_details && (
                              <div className="p-2 rounded bg-white border border-slate-200/80 text-slate-600">
                                <div className="text-[10px] text-teal-700 uppercase font-bold mb-1 flex items-center space-x-1">
                                  <CheckCircle2 className="w-3 h-3 text-teal-600" />
                                  <span>Execution Result</span>
                                </div>
                                <pre className="text-[10px] overflow-x-auto text-slate-700">
                                  {JSON.stringify(tool.output_details, null, 2)}
                                </pre>
                              </div>
                            )}

                            {/* Logs Preview */}
                            {tool.logs && tool.logs.length > 0 && (
                              <div className="p-2 rounded bg-slate-900 text-slate-300 text-[10px] space-y-0.5 overflow-x-auto">
                                {tool.logs.map((log, idx) => (
                                  <div key={idx} className="font-mono leading-tight">
                                    {log}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Live 'Working...' Indicator matching Image 2 */}
            {isPipelineActive && (
              <div className="flex items-center space-x-2 text-slate-500 font-mono text-[11px] pt-1 animate-pulse">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" />
                <span>Working...</span>
              </div>
            )}
          </div>

          {/* Root Cause Synthesis Response */}
          {!isPipelineActive && (
            <div className="pl-7 space-y-2.5">
              <div className="p-3.5 bg-slate-50/90 border border-slate-200 rounded-lg text-xs leading-relaxed space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-slate-800 text-[11px] uppercase tracking-wide flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                    <span>{isIncidentActive ? 'Root Cause Synthesis' : 'Operational Baseline Synthesis'}</span>
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    isIncidentActive
                      ? 'bg-teal-50 text-teal-700 border border-teal-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}>
                    {isIncidentActive
                      ? rcaState?.winning_hypothesis
                        ? `${(rcaState.winning_hypothesis.confidence * 100).toFixed(0)}% Confidence`
                        : 'Unresolved'
                      : 'Monitoring'}
                  </span>
                </div>
                <MarkdownContent content={displayedDiagnosis} />
              </div>

              {/* Action / Review Card: 8D Report + SAP Work Order */}
              {(isPaused || isFinalized) ? (
                <div className="p-3 bg-teal-50/40 border border-teal-200/80 rounded-lg flex items-center justify-between gap-3 shadow-2xs">
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-md bg-teal-100/70 border border-teal-200 flex items-center justify-center text-teal-700 flex-shrink-0">
                      <FileCheck className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-mono font-bold text-teal-900 truncate">
                        {isFinalized ? 'Local PM01 draft and 8D report generated' : 'Diagnosis ready for human review'}
                      </div>
                      <div className="text-[11px] text-teal-700/80 font-sans truncate">
                        {isFinalized
                          ? `Authorized by ${rcaState?.incident_report_8d?.d8_sign_off?.reviewed_by || 'Lead Reliability Engineer'} · Local drafts created`
                          : isPaused
                          ? 'Awaiting Lead Reliability Engineer digital signature sign-off'
                          : 'Awaiting Lead Reliability Engineer digital signature sign-off'}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={onOpenReviewModal}
                    disabled={!isPaused}
                    className="disabled:opacity-50 disabled:cursor-not-allowed px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white text-xs font-mono font-bold rounded-md shadow-2xs flex items-center space-x-1.5 transition-colors cursor-pointer flex-shrink-0"
                  >
                    <span>{isFinalized ? 'Reviewed' : 'Review & Authorize'}</span>
                  </button>
                </div>
              ) : (
                <div className={`p-3 rounded-lg flex items-center justify-between gap-3 shadow-2xs ${
                  isTelemetryConnected
                    ? 'bg-emerald-50/40 border border-emerald-200/80'
                    : 'bg-slate-50 border border-slate-200'
                }`}>
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <div className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${
                      isTelemetryConnected
                        ? 'bg-emerald-100/70 border border-emerald-200 text-emerald-700'
                        : 'bg-slate-200 border border-slate-300 text-slate-600'
                    }`}>
                      {isTelemetryConnected ? <CheckCircle2 className="w-4 h-4" /> : <Activity className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <div className={`text-xs font-mono font-bold truncate ${
                        isTelemetryConnected ? 'text-emerald-900' : 'text-slate-800'
                      }`}>
                        {isIncidentActive ? 'No maintenance artifacts available' : isTelemetryConnected ? 'Telemetry monitoring' : 'Telemetry Link Disconnected'}
                      </div>
                      <div className={`text-[11px] font-sans truncate ${
                        isTelemetryConnected ? 'text-emerald-700/80' : 'text-slate-500'
                      }`}>
                        {isTelemetryConnected
                          ? 'All telemetry channels within calibrated operational envelopes · RCA standby'
                          : 'Awaiting 1 Hz telemetry from MQTT broker (port 1883) or user-enabled simulation'}
                      </div>
                    </div>
                  </div>
                  <span className={`px-2.5 py-1 text-[10px] font-mono font-bold rounded-md border ${
                    isTelemetryConnected
                      ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                      : 'bg-slate-200 text-slate-700 border-slate-300'
                  }`}>
                    {isIncidentActive ? 'Unresolved' : isTelemetryConnected ? 'Monitoring' : 'Offline'}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ================= FOLLOW-UP CONVERSATION TURNS ================= */}
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const hasTools = msg.tools && msg.tools.length > 0;
          const isCoTMsgExpanded = !!expandedChatCoT[msg.id];

          return (
            <div key={msg.id} className="space-y-2.5 pt-2 border-t border-slate-100">
              {/* User Prompt */}
              {isUser ? (
                <div className="flex items-start space-x-2.5">
                  <div className="w-5 h-5 rounded-full bg-blue-100 border border-blue-200 flex items-center justify-center text-blue-700 text-[10px] font-bold flex-shrink-0 mt-0.5">
                    U
                  </div>
                  <div className="font-sans text-xs text-slate-800 bg-blue-50/60 border border-blue-200/70 rounded-lg px-3 py-1.5 max-w-[90%]">
                    {msg.content}
                    <div className="text-[10px] font-mono text-blue-500/80 mt-1">
                      {msg.timestamp}
                    </div>
                  </div>
                </div>
              ) : (
                /* Assistant Turn */
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <div className="w-5 h-5 rounded-full bg-teal-100 border border-teal-200 flex items-center justify-center text-teal-700 flex-shrink-0">
                      <Bot className="w-3 h-3" />
                    </div>
                    <span className="font-mono text-[11px] font-semibold text-slate-700">Copilot</span>
                    {msg.timestamp && (
                      <span className="text-[10px] font-mono text-slate-400">
                        {msg.timestamp}
                      </span>
                    )}
                  </div>
                  {/* CoT Reasoning for Follow-up message */}
                  {msg.reasoning_content && (
                    <div className="pl-7">
                      <div className="border border-purple-100 bg-purple-50/30 rounded-md overflow-hidden">
                        <button
                          onClick={() => toggleChatCoT(msg.id)}
                          className="w-full px-2.5 py-1.5 flex items-center justify-between text-left font-mono text-[11px] text-purple-800 hover:bg-purple-100/50 transition-colors cursor-pointer group"
                        >
                          <div className="flex items-center space-x-2">
                            <Brain className="w-3.5 h-3.5 text-purple-600" />
                            <span className="font-semibold text-slate-700 group-hover:text-purple-900">
                              Response time {msg.elapsed_time_sec ?? '—'}s
                            </span>
                          </div>
                          {isCoTMsgExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5 text-purple-600" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5 text-purple-600" />
                          )}
                        </button>

                        {isCoTMsgExpanded && (
                          <div className="px-3 py-2 border-t border-purple-100 bg-white font-mono text-[11px] text-slate-600 leading-relaxed whitespace-pre-line">
                            {msg.reasoning_content}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Tool Call rows for follow-up message */}
                  {hasTools && (
                    <div className="pl-7 space-y-1">
                      {msg.tools!.map((tool) => {
                        const isExpanded = !!expandedChatTools[tool.id];
                        return (
                          <div
                            key={tool.id}
                            className="border border-slate-200 rounded-md bg-white text-[11px] font-mono"
                          >
                            <div className="px-2.5 py-1.5 flex items-center justify-between hover:bg-slate-50">
                              <button
                                onClick={() => toggleChatToolExpanded(tool.id)}
                                className="flex items-center space-x-2 text-left text-slate-700 hover:text-slate-900 cursor-pointer min-w-0 flex-1 pr-2"
                              >
                                {isExpanded ? (
                                  <ChevronDown className="w-3 h-3 text-slate-400 flex-shrink-0" />
                                ) : (
                                  <ChevronRight className="w-3 h-3 text-slate-400 flex-shrink-0" />
                                )}
                                <span className="text-slate-500">Ran</span>
                                <span className="font-semibold text-slate-800">{tool.name}</span>
                                <span className="text-slate-500 truncate">{tool.summary}</span>
                              </button>
                              {tool.inspector_tab && (
                                <button
                                  onClick={() => onSelectInspectorTab(tool.inspector_tab!)}
                                  className="text-teal-600 hover:text-teal-800 font-semibold flex items-center space-x-1 flex-shrink-0 hover:underline cursor-pointer pl-2 text-[10px]"
                                >
                                  <span>[{tool.tab_label || 'Inspect'}]</span>
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </button>
                              )}
                            </div>

                            {isExpanded && (
                              <div className="px-3 py-2 bg-slate-50/70 border-t border-slate-100 space-y-1.5 text-[11px] font-mono">
                                {tool.command && (
                                  <div className="text-slate-500 text-[10px]">
                                    <span className="text-slate-400">$ </span>
                                    <code>{tool.command}</code>
                                  </div>
                                )}
                                {tool.output_details && (
                                  <div className="p-2 rounded bg-white border border-slate-200/80 text-slate-600">
                                    <pre className="text-[10px] overflow-x-auto text-slate-700">
                                      {JSON.stringify(tool.output_details, null, 2)}
                                    </pre>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Assistant Content */}
                  <div className="pl-7">
                    <div className="p-3.5 bg-white border border-slate-200/90 rounded-xl text-xs leading-relaxed text-slate-800 font-sans shadow-2xs">
                      <MarkdownContent content={msg.content} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Live Streaming Delta Bubble for follow-up turns */}
        {isStreaming && (
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <div className="flex items-center space-x-2">
              <div className="w-5 h-5 rounded-full bg-teal-100 border border-teal-200 flex items-center justify-center text-teal-700 flex-shrink-0">
                <Bot className="w-3 h-3" />
              </div>
              <span className="font-mono text-[11px] font-semibold text-slate-700">Copilot</span>
              <span className="text-[10px] font-mono text-teal-600 animate-pulse">generating...</span>
            </div>

            {/* Live Thinking */}
            {currentReasoning && (
              <div className="pl-7">
                <div className="p-2 rounded-md bg-purple-50 border border-purple-200 font-mono text-[11px] text-purple-900 space-y-1">
                  <div className="flex items-center space-x-1.5 text-purple-700 font-bold">
                    <Brain className="w-3.5 h-3.5 animate-pulse" />
                    <span>Thinking...</span>
                  </div>
                  <div className="whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto">
                    {currentReasoning}
                  </div>
                </div>
              </div>
            )}

            {/* Live Tool Execution in progress */}
            {activeStreamingTools.length > 0 && (
              <div className="pl-7 space-y-1">
                {activeStreamingTools.map((tool) => (
                  <div
                    key={tool.id}
                    className="px-2.5 py-1.5 rounded-md border border-slate-200 bg-white flex items-center justify-between text-[11px] font-mono"
                  >
                    <div className="flex items-center space-x-2 text-slate-700">
                      <Loader2 className="w-3 h-3 text-teal-600 animate-spin" />
                      <span className="text-slate-500">Running</span>
                      <span className="font-semibold text-slate-800">{tool.name}</span>
                      <span className="text-slate-500 truncate">{tool.summary}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Live Streaming Output */}
            <div className="pl-7">
              <div className="p-3.5 bg-white border border-teal-200 rounded-xl text-xs leading-relaxed text-slate-800 font-sans shadow-2xs">
                {currentContent ? (
                  <MarkdownContent content={currentContent} />
                ) : (
                  <div className="flex items-center space-x-2 text-slate-500 font-mono text-[11px] animate-pulse">
                    <Loader2 className="w-3 h-3 animate-spin text-teal-600" />
                    <span>Synthesizing response...</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Pinned Bottom Input */}
      <div className="p-3 border-t border-slate-200 bg-slate-50/50 flex-shrink-0">
        {/* Prompt Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendChat();
          }}
          className="flex items-center space-x-2"
        >
          <div className="relative flex-1">
            <input
              type="text"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              disabled={isStreaming || isPipelineRunning}
              placeholder="Ask Copilot about DC bus spikes, parameter F0.18, or PM work order..."
              className="w-full bg-white border border-slate-200 rounded-lg pl-3 pr-8 py-2 text-xs font-sans text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-teal-500 focus:border-teal-500 shadow-2xs"
            />
          </div>
          <button
            type="submit"
            disabled={isStreaming || isPipelineRunning || !inputPrompt.trim()}
            className="px-3.5 py-2 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white rounded-lg text-xs font-mono font-bold flex items-center space-x-1 transition-colors cursor-pointer disabled:opacity-50 shadow-2xs"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </form>

        {/* DeepSeek API Key Status Bar */}
        <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mt-2 px-0.5">
          <div className="flex items-center space-x-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                apiKeyStatus?.has_key ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
            <span>
              Engine: {apiKeyStatus?.has_key ? 'DeepSeek configured' : 'AI unavailable · configure a key'}
            </span>
          </div>
          {onOpenApiKeyModal && (
            <button
              type="button"
              onClick={onOpenApiKeyModal}
              className="text-purple-600 hover:text-purple-700 hover:underline flex items-center space-x-1 cursor-pointer transition-colors"
            >
              <Key className="w-2.5 h-2.5" />
              <span>{apiKeyStatus?.has_key ? 'Manage Key (.env)' : 'Set API Key (.env)'}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentWorkspace;
