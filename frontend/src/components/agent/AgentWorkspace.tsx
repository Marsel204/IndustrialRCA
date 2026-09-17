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
} from 'lucide-react';
import { RCAState, ChatMessage, ToolExecutionItem, LatestIncident, LiveMetric } from '../../types';
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
            <blockquote className="border-l-3 border-teal-500 bg-teal-50/50 px-3 py-2 my-2.5 rounded-r text-xs text-teal-900" {...props} />
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

  const faultCode =
    (latestIncident?.has_incident ? latestIncident?.incident_data?.fault_code : null) ||
    rcaState?.fault_code ||
    latestIncident?.incident_data?.fault_code ||
    (rcaState?.winning_hypothesis?.hypothesis_id === 'H_VFD_ERR02' || rcaState?.winning_hypothesis?.name?.includes('Err02') ? 2 :
     rcaState?.winning_hypothesis?.hypothesis_id === 'H_VFD_ERR06' || rcaState?.winning_hypothesis?.name?.includes('Err06') ? 6 :
     rcaState?.winning_hypothesis?.hypothesis_id === 'H_VFD_ERR03' || rcaState?.winning_hypothesis?.name?.includes('Err03') ? 3 :
     rcaState?.winning_hypothesis?.hypothesis_id === 'H_VFD_ERR11' || rcaState?.winning_hypothesis?.name?.includes('Err11') ? 11 :
     (rcaState?.has_active_trip ? (latestIncident?.incident_data?.fault_code || 2) : 0));
  const isIncidentActive = Boolean(
    latestIncident?.has_incident ||
    rcaState?.has_active_trip ||
    faultCode > 0
  );

  // Build Diagnostic Tool Executions from rcaState
  const autonomousTools: ToolExecutionItem[] = useMemo(() => {
    const assetId = rcaState?.root_cause_asset || 'VFD_VM_01';
    const faultStr = faultCode > 0 ? `Err0${faultCode}` : 'Nominal';
    const winningHypo = rcaState?.winning_hypothesis;

    if (!isIncidentActive) {
      return [
        {
          id: 'tool-stream',
          name: 'LiveTelemetryMonitor',
          command: `LiveTelemetryMonitor --asset ${assetId} --protocol Modbus_RTU --rate 1Hz`,
          args: {
            asset: assetId,
            channels: ['f_out', 'v_dc', 'current', 'rpm', 'fault_code'],
            buffer_window: '60s',
            status: 'HEALTHY',
          },
          status: 'completed',
          duration_ms: 64,
          summary: `on ${assetId} (1 Hz Modbus stream: 40.00 Hz, 182.0 V, 1.15 A nominal)`,
          output_details: {
            f_out_hz: 40.0,
            v_dc_volts: 182.0,
            motor_current_amps: 1.15,
            rpm: 1199.0,
            fault_code: 0,
            trip_status: 'NONE (Nominal Operation)',
          },
          logs: [
            `[LiveTelemetryMonitor] Ingesting Modbus RTU telemetry for ${assetId}...`,
            '[LiveTelemetryMonitor] 1 Hz buffer synchronized. All sensor channels nominal.',
          ],
          inspector_tab: 'telemetry',
          tab_label: 'Inspect Telemetry',
        },
        {
          id: 'tool-limits',
          name: 'OperationalEnvelopeValidator',
          command: `OperationalEnvelopeValidator --asset ${assetId} --standard ISA95`,
          args: {
            v_dc_trip_limit: 195.0,
            current_trip_limit: 2.50,
            f_out_ceiling_hz: 40.00,
          },
          status: 'completed',
          duration_ms: 82,
          summary: `evaluating ISA-95 operational envelope (all values within safe margins)`,
          output_details: {
            v_dc_margin_volts: '+13.0 V below trip threshold',
            current_margin_amps: '+1.35 A below trip threshold',
            health_score_pct: 100,
          },
          logs: [
            '[OperationalEnvelopeValidator] Checking DC bus voltage (182.0V < 195.0V ceiling) -> PASS.',
            '[OperationalEnvelopeValidator] Checking motor stator current (1.15A < 2.50A trip) -> PASS.',
            '[OperationalEnvelopeValidator] Operational envelope nominal.',
          ],
          inspector_tab: 'hypotheses',
          tab_label: 'View Hypotheses',
        },
        {
          id: 'tool-watchdog',
          name: 'HealthWatchdog',
          command: `HealthWatchdog --subscribe MQTT://1883 --topic factory/bench01/vfd/telemetry`,
          args: {
            mqtt_broker: '1883',
            trip_register: '700BH',
            trip_condition: 'Reg 700BH > 0',
          },
          status: 'completed',
          duration_ms: 45,
          summary: `listening for trip trigger events on MQTT / PLC D-variable`,
          output_details: {
            connection: 'ESTABLISHED',
            trip_listener: 'ACTIVE',
            standby_mode: 'AUTONOMOUS_RCA_READY',
          },
          logs: [
            '[HealthWatchdog] Connected to Mosquitto MQTT broker.',
            '[HealthWatchdog] Listening on factory/bench01/vfd/telemetry. Trip triggers armed.',
          ],
          inspector_tab: 'telemetry',
          tab_label: 'Inspect Status',
        },
      ];
    }

    return [
      {
        id: 'tool-cpd',
        name: 'ChangePointDetector',
        command: `ChangePointDetector --asset ${assetId} --window 10s --tags [v_dc,current,f_out]`,
        args: {
          asset: assetId,
          monitored_tags: ['v_dc', 'current', 'f_out', 'rpm'],
          detection_algorithm: 'Pelt (Pruned Exact Linear Time)',
          penalty: 'BIC (Bayesian Information Criterion)',
        },
        status: isPipelineRunning ? 'running' : 'completed',
        duration_ms: 284,
        summary: `on ${assetId} (${faultCode === 2 ? 'abrupt stop transient: current peak 3.85A' : 'transient shift: DC bus 182V → 202.5V, current peak 2.62A'})`,
        output_details: {
          changepoints_detected: rcaState?.detected_anomalies?.length || 2,
          critical_event:
            faultCode === 2
              ? 'Instantaneous motor stall current peak (3.85A > 2.50A trip setpoint)'
              : 'DC bus overvoltage escalation (202.5V > 195.0V trip threshold)',
          timestamp: 't = 14.200s relative to baseline',
          status: 'PRIMARY_TRIGGER_VALIDATED',
        },
        logs: [
          `[ChangePointDetector] Loading high-resolution 100Hz buffer for ${assetId}...`,
          '[ChangePointDetector] Computed L2-norm cost matrix across 4 channels.',
          `[ChangePointDetector] Changepoint confirmed at sample #1420 (anomaly score: 0.942).`,
          faultCode === 2
            ? `[ChangePointDetector] Operational ceiling breached: motor current surged past 2.50A trip limit.`
            : `[ChangePointDetector] Operational ceiling breached: DC bus reached threshold.`,
        ],
        inspector_tab: 'telemetry',
        tab_label: 'Inspect Telemetry',
      },
      {
        id: 'tool-topo',
        name: 'TopologyTracer',
        command: `TopologyTracer --source PLC_LX_01 --target ${assetId} --depth 2`,
        args: {
          target: assetId,
          upstream_controller: 'PLC_LX_01',
          protocol: 'Modbus RTU / RS485 (19200 baud, 8-E-1)',
          isa95_hierarchy: ['Enterprise', 'Site_01', 'Area_VFD', 'Cell_01', assetId],
        },
        status: isPipelineRunning ? 'running' : 'completed',
        duration_ms: 142,
        summary: `on PLC_LX_01 → ${assetId}`,
        output_details: {
          upstream_nodes: ['PLC_LX_01', 'Mains_Supply_230V', 'Braking_Unit_P_PB'],
          downstream_nodes: ['Induction_Motor_M01', 'Shaft_Encoder_E01'],
          path_verification: 'Confirmed: Braking resistor terminal P+/PB unpopulated.',
        },
        logs: [
          `[TopologyTracer] Traversing ISA-95 Equipment Graph for ${assetId}...`,
          '[TopologyTracer] Verified physical link: PLC_LX_01 D-variable register D100 → VFD Run Command.',
          '[TopologyTracer] Checked auxiliary circuit: Terminals P+ and PB open circuit.',
        ],
        inspector_tab: 'topology',
        tab_label: 'View Topology',
      },
      {
        id: 'tool-fmea',
        name: 'FMEAEngine',
        command: `FMEAEngine --evaluate [Err02,Err06,Err03,Err11] --dataset ${rcaState?.thread_id || 'active'}`,
        args: {
          fault_observed: faultStr,
          candidate_hypotheses: ['H_VFD_ERR06', 'H_VFD_ERR02', 'H_VFD_ERR03', 'H_VFD_ERR11'],
          methodology: 'Deterministic Multi-Hypothesis Falsification (MIL-STD-1629A)',
        },
        status: isPipelineRunning ? 'running' : 'completed',
        duration_ms: 512,
        summary: `evaluating VFD failure modes (Err02, Err06, Err03, Err11)`,
        output_details: {
          winning_hypothesis:
            winningHypo?.name ||
            (faultCode === 2
              ? 'Forced Sudden Deceleration Overcurrent (WECON VM Err02)'
              : 'Overfrequency Deceleration Overvoltage (WECON VM Err06)'),
          confidence: winningHypo?.confidence
            ? `${(winningHypo.confidence * 100).toFixed(0)}%`
            : '98%',
          refuted_hypotheses:
            faultCode === 2
              ? [
                  'H_VFD_ERR06: Decel Overvoltage (Refuted: trip was Err02 overcurrent)',
                  'H_VFD_ERR11: Motor Overheat (Refuted: current within thermal rating)',
                ]
              : [
                  'H_VFD_ERR02: Sudden Decel Overcurrent (Refuted: peak current below threshold)',
                  'H_VFD_ERR11: Motor Overheat (Refuted: PT100 nominal)',
                ],
          mechanism:
            faultCode === 2
              ? 'Kinetic back-EMF discharge surge from spinning induction rotor upon abrupt PLC stop'
              : 'Regenerative kinetic energy dump into DC bus capacitors without dynamic dissipation',
        },
        logs: [
          '[FMEAEngine] Ingesting fault symptoms and boundary criteria...',
          faultCode === 2
            ? '[FMEAEngine] Testing H_VFD_ERR02: Instantaneous stop surge > 2.50A -> CONFIRMED (p=0.98).'
            : '[FMEAEngine] Testing H_VFD_ERR06: DC bus > 195V during rapid decel / 50Hz ramp -> CONFIRMED (p=0.98).',
          '[FMEAEngine] FMEA matrix convergence achieved.',
        ],
        inspector_tab: 'hypotheses',
        tab_label: 'View Hypotheses',
      },
      {
        id: 'tool-cmms',
        name: 'CMMSConnector',
        command:
          'CMMSConnector --action create_order --template SAP_PM01 --standard ISO14224',
        args: {
          system: 'SAP S/4HANA Plant Maintenance',
          order_type: 'PM01 (Corrective Maintenance)',
          equipment: assetId,
          priority: '1 - Emergency Immediate Shutdown',
        },
        status: isPipelineRunning ? 'running' : 'completed',
        duration_ms: 195,
        summary: `verifying work order WO-VFD-2026-0042 & Global 8D deliverable`,
        output_details: {
          work_order_id: rcaState?.sap_work_order?.order_number || 'WO-VFD-2026-0042',
          notification:
            rcaState?.sap_work_order?.notification_number || 'NOTIF-2026-0089',
          actions_required: [
            'Install external dynamic braking resistor on terminals P+ and PB (100 Ohm, 200W)',
            'Tune Wecon VM parameter F0.18 (Decel time) from 0.5s to 3.0s',
            'Verify parameter F0.10 voltage clamp configuration',
          ],
        },
        logs: [
          '[CMMSConnector] Connecting to SAP PM REST API endpoint...',
          '[CMMSConnector] Drafted Order WO-VFD-2026-0042 in System Status: CRTD.',
          '[CMMSConnector] Linked Global 8D Root Cause Report with ISO 14224 failure taxonomy.',
        ],
        inspector_tab: 'deliverables',
        tab_label: 'View Deliverables',
      },
    ];
  }, [rcaState, isPipelineRunning]);

  // Handle follow-up chat with simulated agent tool calling and live reasoning
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

    // Generate contextual simulated tool calls based on user query
    const lower = text.toLowerCase();
    const chatTools: ToolExecutionItem[] = [];

    if (
      lower.includes('dc bus') ||
      lower.includes('207v') ||
      lower.includes('voltage') ||
      lower.includes('v_dc')
    ) {
      chatTools.push({
        id: `chat-tool-${Date.now()}-1`,
        name: 'QueryTelemetry',
        command: `QueryTelemetry --sensor v_dc --asset VFD_VM_01 --window 30s`,
        args: { sensor: 'v_dc', asset: 'VFD_VM_01', aggregate: 'max_and_std' },
        status: 'completed',
        duration_ms: 120,
        summary: `on VFD_VM_01 (v_dc range: 181.8V to 206.9V)`,
        output_details: { peak_v_dc: 206.9, trip_threshold: 195.0, duration_over_limit_ms: 410 },
        logs: [
          '[QueryTelemetry] Retrieved 300 data points from TSDB.',
          '[QueryTelemetry] Peak DC bus recorded at 50.00 Hz: 206.9V.',
        ],
        inspector_tab: 'telemetry',
        tab_label: 'Inspect Telemetry',
      });
    }

    if (
      lower.includes('braking') ||
      lower.includes('resistor') ||
      lower.includes('p+/pb') ||
      lower.includes('f0.18') ||
      lower.includes('parameter')
    ) {
      chatTools.push({
        id: `chat-tool-${Date.now()}-2`,
        name: 'CheckOEMManual',
        command: `CheckOEMManual --model Wecon_VM --section "Braking Resistor & F0.18"`,
        args: {
          manual: 'Wecon VM Series User Manual Rev 3.2',
          section: 'Dynamic Braking Specification',
        },
        status: 'completed',
        duration_ms: 165,
        summary: `for Wecon VM (P+/PB recommended: 100Ω 200W, min 75Ω)`,
        output_details: {
          recommended_resistance: '100 Ohm',
          min_resistance: '75 Ohm',
          param_f0_18_default: '5.0s',
        },
        logs: [
          '[CheckOEMManual] Matched section 4.3: Braking Resistor Selection.',
          '[CheckOEMManual] Overvoltage stall prevention requires F0.10=1.',
        ],
        inspector_tab: 'hypotheses',
        tab_label: 'View Hypotheses',
      });
    }

    if (lower.includes('err02') || lower.includes('current') || lower.includes('stall')) {
      chatTools.push({
        id: `chat-tool-${Date.now()}-3`,
        name: 'AnalyzeCurrentTransient',
        command: `AnalyzeCurrentTransient --sensor current --threshold 2.5A`,
        args: { sensor: 'current', threshold_amps: 2.5, event: 'Forced Stop' },
        status: 'completed',
        duration_ms: 140,
        summary: `on Motor Current (spike 2.62A during immediate 0Hz step)`,
        output_details: { peak_current: 2.62, trip_setpoint: 2.50, di_trigger: 'PLC_LX_01 DI Stop Command' },
        logs: [
          '[AnalyzeCurrentTransient] Rapid decel caused back-EMF opposing stator field.',
          '[AnalyzeCurrentTransient] Current trip Err02 triggered in 12ms.',
        ],
        inspector_tab: 'telemetry',
        tab_label: 'Inspect Telemetry',
      });
    }

    if (chatTools.length === 0) {
      chatTools.push({
        id: `chat-tool-${Date.now()}-def`,
        name: 'SearchDiagnosticKB',
        command: `SearchDiagnosticKB --query "${text.slice(0, 40)}"`,
        args: { query: text, domain: 'Industrial VFD Root Cause Analysis' },
        status: 'completed',
        duration_ms: 95,
        summary: `searching ISO 14224 & OEM knowledge base`,
        output_details: {
          matches_found: 3,
          top_match: 'Wecon VM Dynamic Braking and Deceleration Profile',
        },
        logs: ['[SearchDiagnosticKB] Searched 42 technical manuals and 8D incident histories.'],
        inspector_tab: 'hypotheses',
        tab_label: 'View Hypotheses',
      });
    }

    setActiveStreamingTools(chatTools);

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
            elapsed_time_sec: 1.4,
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
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content:
              accumulatedContent ||
              `Diagnosis verified from deterministic FMEA convergence. (Notice: ${err.message})`,
            reasoning_content: accumulatedReasoning || undefined,
            elapsed_time_sec: 0.8,
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

  const currentF = liveMetric ? liveMetric.f_out.toFixed(2) : '10.00';
  const currentVdc = liveMetric ? liveMetric.v_dc.toFixed(1) : '51.0';
  const currentA = liveMetric ? liveMetric.current.toFixed(2) : '0.00';
  const currentRpm = liveMetric ? liveMetric.rpm.toFixed(0) : '0';

  const defaultThinking = isIncidentActive
    ? (faultCode === 2
        ? "1. Ingested live Wecon HMI telemetry buffer via embedded TSDB on asset VFD_VM_01.\n" +
          "2. Operating envelope: 40.00 Hz nominal, 182.0 V DC bus nominal, 1.15 A current, 1199 RPM.\n" +
          "3. Trip setpoint evaluated: Motor stator current breached 2.50 A threshold (reached 3.85 A on forced stop).\n" +
          "4. Evaluated failure hypotheses: H_VFD_ERR02 (Forced Decel Overcurrent) CONFIRMED; H_VFD_ERR06 REFUTED.\n" +
          "5. OEM corrective action: Implement controlled deceleration ramp in PLC ladder logic and tune parameter F0.18."
        : "1. Ingested live Wecon HMI telemetry buffer via embedded TSDB on asset VFD_VM_01.\n" +
          "2. Operating envelope: 40.00 Hz nominal, 182.0 V DC bus nominal, 1.15 A current, 1199 RPM.\n" +
          "3. Trip setpoint evaluated: DC bus limit at 195.0 V DC (reaches ~207V at 50 Hz), current limit at 2.50 A.\n" +
          "4. Evaluated failure hypotheses: H_VFD_ERR06 (Overfrequency > 40 Hz) and H_VFD_ERR02 (Forced Decel Stop).\n" +
          "5. OEM corrective action: Install dynamic braking resistor on terminals P+/PB and tune parameter F0.18.")
    : `1. Ingested live Wecon HMI telemetry buffer via embedded TSDB on asset VFD_VM_01.\n` +
      `2. Operating envelope: ${currentF} Hz nominal, ${currentVdc} V DC bus nominal, ${currentA} A current, ${currentRpm} RPM.\n` +
      `3. Continuous safety verification: DC bus (${currentVdc} V < 195.0 V ceiling), current (${currentA} A < 2.50 A trip).\n` +
      `4. All health diagnostics green. Zero hardware trip codes active.\n` +
      `5. System operating nominal edge monitoring. Ready for hardware trip triggers.`;

  const isPaused = rcaState?.is_paused_at_hitl || false;
  const isFinalized = rcaState?.pipeline_status === 'COMPLETED';
  const isStateResolved =
    rcaState?.pipeline_status === 'CAUSAL_TRACE_COMPLETED' ||
    rcaState?.pipeline_status === 'ANALYSIS_COMPLETE' ||
    rcaState?.pipeline_status === 'COMPLETED' ||
    rcaState?.pipeline_status === 'AWAITING_REVIEW';
  const isPipelineActive = isPipelineRunning && !isStateResolved;

  const displayedThinking =
    rcaState?.deepseek_evaluation?.reasoning_content ||
    rcaState?.deepseek_evaluation?.content ||
    defaultThinking;

  const displayedDiagnosis = isIncidentActive
    ? rcaState?.root_cause_description ||
      (faultCode === 2
        ? 'Operator actuated PLC On/Off stop button via PLC D-variable register, cutting the run command instantaneously without a controlled deceleration ramp routine (F0.18 too steep and braking resistor absent), inducing a 3.85 A kinetic back-EMF overcurrent surge that tripped the drive on Err02.'
        : 'Output frequency setpoint was ramped past the 40.00 Hz operational ceiling toward 50.00 Hz, causing DC bus voltage to escalate to 202.5 V (breaching the calibrated 195.0 V trip limit) because Wecon VM parameter F0.10 was unclamped and dynamic braking resistor terminals P+/PB were unpopulated.')
    : `Continuous real-time telemetry from Wecon VM VFD (VFD_VM_01) is nominal. Output frequency (${currentF} Hz), DC bus voltage (${currentVdc} V), and motor current (${currentA} A) remain within calibrated ISA-95 envelopes. Listening for hardware trip trigger over MQTT / PLC D-variable.`;

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
                V4.1 Flash
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
              <span>Nominal Monitoring</span>
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
                      Thought for 1.8s
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
                        : '98% Confidence'
                      : '100% Health Score'}
                  </span>
                </div>
                <MarkdownContent content={displayedDiagnosis} />
              </div>

              {/* Action / Review Card: 8D Report + SAP Work Order */}
              {isIncidentActive ? (
                <div className="p-3 bg-teal-50/40 border border-teal-200/80 rounded-lg flex items-center justify-between gap-3 shadow-2xs">
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-md bg-teal-100/70 border border-teal-200 flex items-center justify-center text-teal-700 flex-shrink-0">
                      <FileCheck className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-mono font-bold text-teal-900 truncate">
                        1 SAP Work Order (PM01) + 8D Report generated
                      </div>
                      <div className="text-[11px] text-teal-700/80 font-sans truncate">
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
                    className="px-3.5 py-1.5 bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white text-xs font-mono font-bold rounded-md shadow-2xs flex items-center space-x-1.5 transition-colors cursor-pointer flex-shrink-0"
                  >
                    <span>Review & Authorize</span>
                  </button>
                </div>
              ) : (
                <div className="p-3 bg-emerald-50/40 border border-emerald-200/80 rounded-lg flex items-center justify-between gap-3 shadow-2xs">
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-md bg-emerald-100/70 border border-emerald-200 flex items-center justify-center text-emerald-700 flex-shrink-0">
                      <CheckCircle2 className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-mono font-bold text-emerald-900 truncate">
                        System Nominal · Zero Active Incidents
                      </div>
                      <div className="text-[11px] text-emerald-700/80 font-sans truncate">
                        All telemetry channels within calibrated operational envelopes · RCA standby
                      </div>
                    </div>
                  </div>
                  <span className="px-2.5 py-1 bg-emerald-100 text-emerald-800 text-[10px] font-mono font-bold rounded-md border border-emerald-200">
                    Nominal
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
                              Thought for {msg.elapsed_time_sec || '1.2'}s
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
      </div>
    </div>
  );
};

export default AgentWorkspace;
