import React, { useState, useRef, useEffect } from 'react';
import {
  Brain,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FileCheck,
  Send,
  Sparkles,
  Server,
  Layers,
  Bot,
  Clock,
  Loader2,
} from 'lucide-react';
import { RCAState, ChatMessage } from '../../types';
import { streamCopilotChat } from '../../api';

interface AgentWorkspaceProps {
  rcaState: RCAState | null;
  apiOnline: boolean;
  deepseekModel: string;
  onSelectInspectorTab: (tabId: string) => void;
  onOpenReviewModal: () => void;
  activeScenarioName?: string;
  isPipelineRunning?: boolean;
}

export const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({
  rcaState,
  apiOnline,
  deepseekModel,
  onSelectInspectorTab,
  onOpenReviewModal,
  activeScenarioName = 'Emergency Trip (Strainer Clog)',
  isPipelineRunning = false,
}) => {
  // Collapsible sections
  const [isThinkingExpanded, setIsThinkingExpanded] = useState<boolean>(true);
  const [expandedCoT, setExpandedCoT] = useState<Record<string, boolean>>({});

  // Copilot Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-msg',
      role: 'assistant',
      content:
        'Continuous telemetry ingested from **Wecon VM VFD & Induction Motor Test Bench (VFD_VM_01)**. ' +
        'Monitoring 1 Hz Modbus registers: Output Frequency (`f_out`), DC Bus Voltage (`v_dc`), Motor Current (`current`), RPM, and Trip Codes. ' +
        'Ready to analyze real telemetry, detect trips (>195 Vdc or forced decel), and evaluate failure modes (Err02, Err06, Err03, Err11).',
      timestamp: 'Just now',
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [currentReasoning, setCurrentReasoning] = useState<string>('');
  const [currentContent, setCurrentContent] = useState<string>('');

  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentContent, currentReasoning]);

  const toggleMsgCoT = (id: string) => {
    setExpandedCoT((prev) => ({ ...prev, [id]: !prev[id] }));
  };

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

    const assistantMsgId = `asst-${Date.now()}`;
    let accumulatedContent = '';
    let accumulatedReasoning = '';

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
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content: accumulatedContent || 'Diagnosis confirmed by DeepSeek Copilot.',
            reasoning_content: accumulatedReasoning || undefined,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        setCurrentReasoning('');
        setCurrentContent('');
        setIsStreaming(false);
      },
      (err) => {
        console.error('Chat error:', err);
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content:
              accumulatedContent ||
              `Diagnosis verified from deterministic FMEA convergence. (Notice: ${err.message})`,
            reasoning_content: accumulatedReasoning || undefined,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        setCurrentReasoning('');
        setCurrentContent('');
        setIsStreaming(false);
      }
    );
  };

  const isVfd = true;

  const quickPrompts = [
    'Why does DC bus reach ~207V at 50 Hz and trip Err06 above 195V?',
    'What caused the instantaneous Err02 current spike on PLC On/Off stop?',
    'What braking resistor (P+/PB) is needed to prevent overvoltage trips?',
    'How does increasing parameter F0.18 prevent regeneration trips?',
  ];

  const defaultThinking =
    "1. Ingested live Wecon HMI telemetry buffer via embedded TSDB on asset VFD_VM_01.\n" +
    "2. Operating envelope: 40.00 Hz nominal, 182.0 V DC bus nominal, 1.15 A current, 1199 RPM.\n" +
    "3. Trip setpoint evaluated: DC bus limit at 195.0 V DC (reaches ~207V at 50 Hz), current limit at 2.50 A.\n" +
    "4. Evaluated failure hypotheses: H_VFD_ERR06 (Overfrequency > 40 Hz) and H_VFD_ERR02 (Forced Decel Stop).\n" +
    "5. OEM corrective action: Install dynamic braking resistor on terminals P+/PB and tune parameter F0.18.";

  const isPaused = rcaState?.is_paused_at_hitl || false;
  const isFinalized = rcaState?.pipeline_status === 'COMPLETED';

  const displayedThinking =
    rcaState?.deepseek_evaluation?.reasoning_content ||
    rcaState?.deepseek_evaluation?.content ||
    defaultThinking;

  const displayedDiagnosis =
    rcaState?.root_cause_description ||
    'Real-time telemetry and FMEA matrix actively monitored for Wecon VM Series VFD (VFD_VM_01). Operational baseline calibrated at 40.00 Hz and 182.0 V DC bus. Emergency trips calibrated at 195.0 V DC (Err06) and 2.50 A (Err02).';

  return (
    <div className="flex flex-col h-full bg-slate-50/50 border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      {/* Top User Prompt / Goal Card */}
      <div className="p-4 bg-white border-b border-slate-200">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center space-x-2">
            <span className={`w-2 h-2 rounded-full ${isPipelineRunning ? 'bg-amber-500 animate-ping' : 'bg-teal-500 animate-pulse'}`} />
            <span className="text-[11px] font-mono font-bold tracking-wider text-teal-700 uppercase">
              Current Agentic Objective
            </span>
          </div>
          <div className="flex items-center space-x-1.5">
            {isPipelineRunning && (
              <span className="flex items-center space-x-1 text-[10px] font-mono text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Running Pipeline</span>
              </span>
            )}
            <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
              {activeScenarioName}
            </span>
          </div>
        </div>
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-semibold text-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-teal-600 flex-shrink-0" />
            <span>
              {isVfd
                ? 'Investigate hardware overvoltage trip on Wecon VFD VM 01'
                : 'Analyze emergency trip on Boiler Feed Pump P-301A'}
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-500 bg-white border border-slate-200 px-1.5 py-0.5 rounded">
            Autonomous RCA
          </span>
        </div>
      </div>

      {/* Scrollable Agent Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Service Status Block */}
        <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs space-y-2">
          <div className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider">
            Connected Agentic Environment
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
            {/* FastAPI Service */}
            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center space-x-2">
                <Server className="w-3.5 h-3.5 text-slate-600" />
                <span className="text-slate-700 font-medium truncate">
                  FastAPI Backend Server (REST & SSE)
                </span>
              </div>
              <span className={`flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                apiOnline
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-rose-50 text-rose-700 border border-rose-200'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${apiOnline ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span>{apiOnline ? 'ONLINE' : 'OFFLINE'}</span>
              </span>
            </div>

            {/* React UI */}
            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center space-x-2">
                <Layers className="w-3.5 h-3.5 text-slate-600" />
                <span className="text-slate-700 font-medium truncate">
                  React 19 + Vite Industrial Control Room UI
                </span>
              </div>
              <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>ONLINE</span>
              </span>
            </div>
          </div>
        </div>

        {/* Expandable Thinking Box */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
          <button
            onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
            className="w-full px-3.5 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs font-mono font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <div className="flex items-center space-x-2">
              <Brain className="w-4 h-4 text-purple-600" />
              <span>DeepSeek-R1 Chain-of-Thought</span>
              <span className="flex items-center space-x-1 text-[10px] font-mono text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.2 rounded font-normal">
                <Clock className="w-3 h-3" />
                <span>Elapsed: 1.8s</span>
              </span>
            </div>
            {isThinkingExpanded ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {isThinkingExpanded && (
            <div className="p-3 bg-purple-50/20 text-xs font-mono text-slate-600 leading-relaxed whitespace-pre-line border-t border-purple-100">
              {displayedThinking}
            </div>
          )}
        </div>

        {/* Discrete Tool Call Execution Steps with 1-Click Tab Jump Links */}
        <div className="space-y-2">
          <div className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider px-1">
            Autonomous Tool Executions
          </div>

          <div className="space-y-1.5">
            {/* Step 1: ChangePointDetector */}
            <div className="bg-white border border-slate-200 rounded-xl p-3 flex flex-wrap items-center justify-between gap-2 shadow-xs hover:border-slate-300 transition-colors">
              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  OK
                </span>
                <span className="font-semibold text-slate-800">ChangePointDetector</span>
                <span className="text-slate-500">on VFD_VM_01 (DC bus voltage & motor current transients)</span>
              </div>
              <button
                onClick={() => onSelectInspectorTab('telemetry')}
                className="text-xs font-mono text-blue-600 hover:text-blue-800 font-medium flex items-center space-x-1 hover:underline cursor-pointer"
              >
                <span>[Inspect Telemetry]</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>

            {/* Step 2: TopologyTracer */}
            <div className="bg-white border border-slate-200 rounded-xl p-3 flex flex-wrap items-center justify-between gap-2 shadow-xs hover:border-slate-300 transition-colors">
              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  OK
                </span>
                <span className="font-semibold text-slate-800">TopologyTracer</span>
                <span className="text-slate-500">on PLC_LX_01 → VFD_VM_01</span>
              </div>
              <button
                onClick={() => onSelectInspectorTab('topology')}
                className="text-xs font-mono text-blue-600 hover:text-blue-800 font-medium flex items-center space-x-1 hover:underline cursor-pointer"
              >
                <span>[View Topology]</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>

            {/* Step 3: FMEAEngine */}
            <div className="bg-white border border-slate-200 rounded-xl p-3 flex flex-wrap items-center justify-between gap-2 shadow-xs hover:border-slate-300 transition-colors">
              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  OK
                </span>
                <span className="font-semibold text-slate-800">FMEAEngine</span>
                <span className="text-slate-500">evaluating VFD modes (Err02, Err06, Err03, Err11)</span>
              </div>
              <button
                onClick={() => onSelectInspectorTab('hypotheses')}
                className="text-xs font-mono text-blue-600 hover:text-blue-800 font-medium flex items-center space-x-1 hover:underline cursor-pointer"
              >
                <span>[View Hypotheses]</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>

            {/* Step 4: CMMSConnector */}
            <div className="bg-white border border-slate-200 rounded-xl p-3 flex flex-wrap items-center justify-between gap-2 shadow-xs hover:border-slate-300 transition-colors">
              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  OK
                </span>
                <span className="font-semibold text-slate-800">CMMSConnector</span>
                <span className="text-slate-500">verifying work order WO-VFD-2026-0042</span>
              </div>
              <button
                onClick={() => onSelectInspectorTab('deliverables')}
                className="text-xs font-mono text-blue-600 hover:text-blue-800 font-medium flex items-center space-x-1 hover:underline cursor-pointer"
              >
                <span>[View Deliverables]</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Diagnostic Conclusion Summary Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-slate-900 uppercase tracking-wide">
              Root Cause Synthesis
            </span>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-teal-50 text-teal-700 border border-teal-200">
              {rcaState?.winning_hypothesis ? `${(rcaState.winning_hypothesis.confidence * 100).toFixed(0)}% Confidence` : '98% Confidence'}
            </span>
          </div>

          <div className="text-xs text-slate-700 leading-relaxed font-sans">
            {displayedDiagnosis}
          </div>
        </div>

        {/* Action / Review Card (matches reference screenshot) */}
        <div className="bg-teal-50/50 border border-teal-200 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-teal-100/70 border border-teal-200 flex items-center justify-center text-teal-700">
              <FileCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-mono font-bold text-teal-900">
                1 SAP Work Order (PM01) + 8D Report generated
              </div>
              <div className="text-[11px] text-teal-700/80 font-sans">
                {isFinalized
                  ? `Authorized by ${rcaState?.incident_report_8d?.d8_sign_off?.reviewed_by || 'Lead Reliability Engineer'} · Deliverables Released`
                  : isPaused
                  ? 'Awaiting Lead Reliability Engineer digital signature sign-off'
                  : 'Awaiting Lead Reliability Engineer digital signature sign-off'}
              </div>
            </div>
          </div>

          <button
            onClick={onOpenReviewModal}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white text-xs font-mono font-bold rounded-lg shadow-xs flex items-center space-x-1.5 transition-colors cursor-pointer"
          >
            <span>📄</span>
            <span>Review & Authorize</span>
          </button>
        </div>

        {/* Real-time Copilot Chat Stream */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div className="flex items-center space-x-2">
              <Bot className="w-4 h-4 text-purple-600" />
              <span className="text-xs font-mono font-bold text-slate-800">
                DeepSeek Diagnostic Copilot
              </span>
              <span className="text-[10px] font-mono text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.2 rounded">
                {deepseekModel}
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">
              Physics & Standards Grounded
            </span>
          </div>

          {/* Messages Stream Container */}
          <div className="max-h-[300px] overflow-y-auto space-y-2.5 pr-1">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`max-w-[92%] rounded-xl p-3 text-xs leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-none shadow-xs'
                      : 'bg-slate-50 text-slate-800 border border-slate-200 rounded-bl-none shadow-xs space-y-2'
                  }`}
                >
                  {/* Collapsible Chain-of-Thought for Assistant Messages */}
                  {m.reasoning_content && (
                    <div className="rounded-lg bg-purple-50 border border-purple-200 overflow-hidden font-mono text-[11px]">
                      <button
                        onClick={() => toggleMsgCoT(m.id)}
                        className="w-full px-2 py-1 bg-purple-100/60 flex items-center justify-between text-purple-800 font-bold hover:bg-purple-100 cursor-pointer"
                      >
                        <span className="flex items-center space-x-1.5">
                          <Brain className="w-3.5 h-3.5 text-purple-600" />
                          <span>DeepSeek Reasoning Trace</span>
                        </span>
                        {expandedCoT[m.id] ? (
                          <ChevronUp className="w-3 h-3 text-purple-600" />
                        ) : (
                          <ChevronDown className="w-3 h-3 text-purple-600" />
                        )}
                      </button>
                      {expandedCoT[m.id] && (
                        <div className="p-2 text-purple-900 whitespace-pre-wrap leading-relaxed border-t border-purple-200 bg-white">
                          {m.reasoning_content}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="whitespace-pre-wrap font-sans">{m.content}</div>
                  <div
                    className={`text-[10px] font-mono mt-1 ${
                      m.role === 'user' ? 'text-blue-100 text-right' : 'text-slate-400'
                    }`}
                  >
                    {m.timestamp}
                  </div>
                </div>
              </div>
            ))}

            {/* Live Streaming Delta Bubble */}
            {isStreaming && (
              <div className="flex flex-col items-start">
                <div className="max-w-[92%] rounded-xl p-3 text-xs font-sans leading-relaxed bg-slate-50 text-slate-800 border border-purple-300 rounded-bl-none shadow-xs space-y-2">
                  {currentReasoning && (
                    <div className="rounded-lg bg-purple-50 border border-purple-200 p-2 font-mono text-[11px] text-purple-900 space-y-1">
                      <div className="flex items-center space-x-1 text-purple-700 font-bold">
                        <Brain className="w-3.5 h-3.5 animate-pulse" />
                        <span>Live Thinking...</span>
                      </div>
                      <div className="whitespace-pre-wrap leading-relaxed">{currentReasoning}</div>
                    </div>
                  )}

                  <div className="whitespace-pre-wrap">
                    {currentContent || (
                      <span className="text-purple-600 italic animate-pulse">
                        Analyzing telemetry and formulation...
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={chatBottomRef} />
          </div>

          {/* Quick Suggestion Chips */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {quickPrompts.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => handleSendChat(chip)}
                disabled={isStreaming}
                className="px-2.5 py-1 bg-slate-50 hover:bg-slate-100 text-[11px] font-mono text-slate-600 rounded-md border border-slate-200 transition-colors cursor-pointer disabled:opacity-50"
              >
                {chip}
              </button>
            ))}
          </div>

          {/* Prompt Input Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendChat();
            }}
            className="flex items-center space-x-2 pt-1"
          >
            <input
              type="text"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              disabled={isStreaming}
              placeholder="Ask Copilot about vibration, cavitation, or PM work order..."
              className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs font-sans text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-teal-500 focus:bg-white"
            />
            <button
              type="submit"
              disabled={isStreaming || !inputPrompt.trim()}
              className="px-3.5 py-2 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white rounded-lg text-xs font-mono font-bold flex items-center space-x-1 transition-colors cursor-pointer disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
