import {
  Scenario,
  TelemetryData,
  SpectrumData,
  TopologyData,
  RCAState,
  LatestIncident,
  LiveMetric,
  ApiKeyStatus,
  ApiKeySaveResponse,
  ApiKeyTestResponse,
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || '/api/v1';

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await fetch(`${API_BASE}/scenarios`);
  if (!res.ok) throw new Error(`Failed to fetch scenarios: ${res.statusText}`);
  const data = await res.json();
  return data.scenarios;
}

export async function fetchTelemetry(datasetId: string): Promise<TelemetryData> {
  const res = await fetch(`${API_BASE}/telemetry/${datasetId}`);
  if (!res.ok) throw new Error(`Failed to fetch telemetry: ${res.statusText}`);
  return res.json();
}

export async function fetchSpectrum(datasetId: string): Promise<SpectrumData> {
  const res = await fetch(`${API_BASE}/telemetry/${datasetId}/spectrum`);
  if (!res.ok) throw new Error(`Failed to fetch spectrum: ${res.statusText}`);
  return res.json();
}

export async function fetchTopology(assetId: string): Promise<TopologyData> {
  const res = await fetch(`${API_BASE}/topology/${assetId}`);
  if (!res.ok) throw new Error(`Failed to fetch topology: ${res.statusText}`);
  return res.json();
}

export async function fetchRCAState(threadId: string): Promise<RCAState> {
  const res = await fetch(`${API_BASE}/rca/state/${threadId}`);
  if (!res.ok) throw new Error(`Failed to fetch RCA state: ${res.statusText}`);
  return res.json();
}

export async function runRCAPipeline(params: {
  dataset_id: string;
  asset_id: string;
  thread_id?: string;
  use_deepseek?: boolean;
  deepseek_model?: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/rca/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Failed to execute RCA pipeline: ${res.statusText}`);
  return res.json();
}

export async function submitHumanReview(params: {
  thread_id: string;
  action: string;
  reviewer: string;
  notes: string;
  override_root_cause?: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/rca/human-review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Failed to submit review: ${res.statusText}`);
  return res.json();
}

export async function fetchLatestIncident(): Promise<LatestIncident> {
  const res = await fetch(`${API_BASE}/telemetry/latest_incident`);
  if (!res.ok) throw new Error(`Failed to fetch latest incident: ${res.statusText}`);
  return res.json();
}

export function streamCopilotChat(
  messages: Array<{ role: string; content: string }>,
  model: string,
  onDelta: (delta: { content: string; reasoning_content: string }) => void,
  onDone: () => void,
  onError: (err: any) => void,
  threadId?: string
): () => void {
  const controller = new AbortController();

  fetch(`${API_BASE}/copilot/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, model, thread_id: threadId }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`Stream error: ${response.statusText}`);
      if (!response.body) throw new Error('Response body is null');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const block of lines) {
          const trimmed = block.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const dataStr = trimmed.slice(6).trim();
          if (dataStr === '[DONE]') {
            onDone();
            return;
          }
          try {
            const parsed = JSON.parse(dataStr);
            if (parsed.error) {
              onError(new Error(parsed.error));
              return;
            }
            onDelta(parsed);
          } catch (e) {
            console.error('Error parsing SSE chunk:', e, dataStr);
          }
        }
      }
      onDone();
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err);
      }
    });

  return () => controller.abort();
}

export function subscribeTelemetryEvents(
  onEvent: (eventData: any) => void,
  onError?: (err: any) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/telemetry/events/stream`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onEvent(data);
    } catch (err) {
      console.error('Error parsing telemetry event:', err);
    }
  };

  eventSource.onerror = (err) => {
    if (onError) onError(err);
  };

  return () => {
    eventSource.close();
  };
}

export async function fetchLiveMetrics(): Promise<LiveMetric> {
  const res = await fetch(`${API_BASE}/telemetry/live/metrics`);
  if (!res.ok) throw new Error(`Failed to fetch live metrics: ${res.statusText}`);
  return res.json();
}

export function subscribeLiveTelemetryStream(
  onMetric: (metric: LiveMetric) => void,
  onError?: (err: any) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/telemetry/live/stream`);

  eventSource.onmessage = (event) => {
    try {
      const data: LiveMetric = JSON.parse(event.data);
      onMetric(data);
    } catch (err) {
      console.error('Error parsing live telemetry stream metric:', err);
    }
  };

  eventSource.onerror = (err) => {
    if (onError) onError(err);
  };

  return () => {
    eventSource.close();
  };
}

export async function fetchTSDBHistory(seconds = 120): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/telemetry/tsdb/history?seconds=${seconds}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.history || [];
  } catch (err) {
    console.error('Error fetching TSDB history:', err);
    return [];
  }
}

export async function clearIncident(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/telemetry/incident/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to clear incident: ${res.statusText}`);
  return res.json();
}

export interface SimulationStatusResponse {
  simulation_enabled: boolean;
  is_simulated: boolean;
  scenario: string;
  phase: 'IDLE' | 'NORMAL' | 'TRIPPED' | 'STOPPED' | string;
  countdown: number;
}

export async function toggleSimulationMode(
  enabled: boolean,
  scenario: string = 'nominal',
  normalDurationSec: number = 5.0
): Promise<{ simulation_enabled: boolean; scenario: string; phase: string; countdown: number; status: string }> {
  const res = await fetch(`${API_BASE}/telemetry/simulation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      enabled,
      scenario,
      normal_duration_sec: normalDurationSec,
    }),
  });
  if (!res.ok) throw new Error(`Failed to toggle simulation mode: ${res.statusText}`);
  return res.json();
}

export async function fetchSimulationStatus(): Promise<SimulationStatusResponse> {
  const res = await fetch(`${API_BASE}/telemetry/simulation`);
  if (!res.ok) throw new Error(`Failed to fetch simulation status: ${res.statusText}`);
  return res.json();
}

export async function fetchApiKeyStatus(): Promise<ApiKeyStatus> {
  const res = await fetch(`${API_BASE}/settings/api-key`);
  if (!res.ok) throw new Error(`Failed to fetch API key status: ${res.statusText}`);
  return res.json();
}

export async function saveApiKey(params: {
  api_key: string;
  base_url?: string;
  model?: string;
}): Promise<ApiKeySaveResponse> {
  const res = await fetch(`${API_BASE}/settings/api-key`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to save API key: ${res.statusText}`);
  }
  return res.json();
}

export async function testApiKeyConnection(params?: {
  api_key?: string;
  base_url?: string;
  model?: string;
}): Promise<ApiKeyTestResponse> {
  const res = await fetch(`${API_BASE}/settings/api-key/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params || {}),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to test API key: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteApiKey(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/settings/api-key`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to delete API key: ${res.statusText}`);
  }
  return res.json();
}



