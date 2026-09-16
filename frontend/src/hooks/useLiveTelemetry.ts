import { useState, useEffect } from 'react';
import { TelemetryData, LiveMetric } from '../types';
import { fetchLiveMetrics, subscribeLiveTelemetryStream, fetchTSDBHistory } from '../api';

export interface UseLiveTelemetryResult {
  isLiveStream: boolean;
  isVfdAsset: boolean;
  liveMetric: LiveMetric | null;
  rollingTimestamps: number[];
  rollingSeries: Record<string, number[]>;
}

export function useLiveTelemetry(
  telemetry: TelemetryData | null,
  activeScenarioId?: string
): UseLiveTelemetryResult {
  const isLiveStream =
    activeScenarioId === 'live_stream' ||
    activeScenarioId === 'hil' ||
    Boolean(activeScenarioId?.startsWith('ds_hil'));
  const isVfdAsset =
    activeScenarioId === 'live_stream' ||
    activeScenarioId === 'exp_err02' ||
    activeScenarioId === 'exp_err06' ||
    activeScenarioId === 'exp_nominal' ||
    activeScenarioId === 'hil' ||
    Boolean(activeScenarioId?.startsWith('ds_hil')) ||
    telemetry?.metadata?.asset_id === 'VFD_VM_01' ||
    true;

  const [liveMetric, setLiveMetric] = useState<LiveMetric | null>(null);
  const [rollingTimestamps, setRollingTimestamps] = useState<number[]>([]);
  const [rollingSeries, setRollingSeries] = useState<Record<string, number[]>>({});

  // Sync initial telemetry data into rolling buffer when telemetry or scenario changes
  useEffect(() => {
    if (telemetry) {
      if (isLiveStream) {
        const ts = telemetry.timestamps || [];
        setRollingTimestamps(ts.length > 300 ? ts.slice(-300) : ts);
        const s = telemetry.series || {};
        const trimmed: Record<string, number[]> = {};
        for (const [k, v] of Object.entries(s)) {
          trimmed[k] = v.length > 300 ? v.slice(-300) : v;
        }
        setRollingSeries(trimmed);
      } else if (!activeScenarioId || telemetry.dataset_id === activeScenarioId || telemetry.dataset_id === 'hil' || activeScenarioId.startsWith('ds_hil')) {
        setRollingTimestamps(telemetry.timestamps || []);
        setRollingSeries(telemetry.series || {});
        setLiveMetric(null);
      }
    }
  }, [telemetry, isLiveStream, activeScenarioId]);

  // Connect to SSE live stream when in live_stream scenario
  useEffect(() => {
    if (!isLiveStream) return;

    fetchLiveMetrics()
      .then((m) => {
        setLiveMetric(m);
      })
      .catch(console.warn);

    // Pre-fill rolling buffer from embedded TSDB history
    fetchTSDBHistory(120)
      .then((history) => {
        if (history && history.length > 0) {
          setRollingTimestamps(history.map((_, i) => i));
          setRollingSeries({
            f_out: history.map((p) => p.f_out ?? 40.0),
            v_dc: history.map((p) => p.v_dc ?? 182.0),
            current: history.map((p) => p.current ?? 0.0),
            rpm: history.map((p) => p.rpm ?? 1199.0),
            fault_code: history.map((p) => p.fault_code ?? 0),
            'IT-30101': history.map((p) => (p['IT-30101'] !== undefined ? p['IT-30101'] : (p.current ?? 0) * 60.0)),
            'PT-30101': history.map((p) => p['PT-30101'] ?? 2.40),
            'DPS-30101': history.map((p) => p['DPS-30101'] ?? 0.12),
            'VI-301-R': history.map((p) => p['VI-301-R'] ?? 1.80),
            'TI-301-DE': history.map((p) => p['TI-301-DE'] ?? 48.50),
          });
        }
      })
      .catch(console.warn);

    const unsubscribe = subscribeLiveTelemetryStream(
      (m: LiveMetric) => {
        setLiveMetric(m);
        setRollingTimestamps((prev) => {
          const nextSec = prev.length > 0 ? prev[prev.length - 1] + 1 : 0;
          const updated = [...prev, nextSec];
          return updated.length > 300 ? updated.slice(-300) : updated;
        });
        setRollingSeries((prev) => {
          const appendVal = (key: string, val: number) => {
            const existing = prev[key] || [];
            const nextArr = [...existing, val];
            return nextArr.length > 300 ? nextArr.slice(-300) : nextArr;
          };

          return {
            ...prev,
            f_out: appendVal('f_out', m.f_out),
            v_dc: appendVal('v_dc', m.v_dc),
            current: appendVal('current', m.current),
            rpm: appendVal('rpm', m.rpm),
            fault_code: appendVal('fault_code', m.fault_code),
            'IT-30101': appendVal('IT-30101', m.current * 60.0),
            'PT-30101': appendVal('PT-30101', m.fault_code > 0 ? 0.58 : 2.40),
            'DPS-30101': appendVal('DPS-30101', m.fault_code > 0 ? 1.85 : 0.12),
            'VI-301-R': appendVal('VI-301-R', m.fault_code > 0 ? 11.4 : 1.80),
            'TI-301-DE': appendVal('TI-301-DE', m.fault_code > 0 ? 92.3 : 48.5),
          };
        });
      },
      (err) => {
        console.warn('Live telemetry stream closed/error:', err);
      }
    );

    return () => {
      unsubscribe();
    };
  }, [isLiveStream]);

  return {
    isLiveStream,
    isVfdAsset,
    liveMetric,
    rollingTimestamps,
    rollingSeries,
  };
}
