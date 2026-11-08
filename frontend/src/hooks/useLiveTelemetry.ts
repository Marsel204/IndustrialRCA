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
    activeScenarioId === 'exp_err13' ||
    activeScenarioId === 'exp_nominal' ||
    activeScenarioId === 'hil' ||
    Boolean(activeScenarioId?.startsWith('ds_hil')) ||
    telemetry?.metadata?.asset_id === 'VFD_VM_01';

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
          const observed: Record<string, number[]> = {};
          const channels = ['f_out', 'f_in', 'f_target', 'v_dc', 'v_out', 'current', 'rpm', 'torque', 'power', 'fault_code', 'IT-30101', 'PT-30101', 'DPS-30101', 'VI-301-R', 'TI-301-DE'];
          for (const tag of channels) {
            observed[tag] = history.map((point) => {
              const value = (point as unknown as Record<string, unknown>)[tag];
              return typeof value === 'number' && Number.isFinite(value) ? value : Number.NaN;
            });
          }
          setRollingSeries(observed);
        }
      })
      .catch(console.warn);

    const unsubscribe = subscribeLiveTelemetryStream(
      (m: LiveMetric) => {
        setLiveMetric(m);
        if (m.telemetry_connected === false || m.status === 'OFFLINE') return;
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

          const next = { ...prev };
          for (const tag of ['f_out', 'f_in', 'f_target', 'v_dc', 'v_out', 'current', 'rpm', 'torque', 'power', 'fault_code', 'IT-30101', 'PT-30101', 'DPS-30101', 'VI-301-R', 'TI-301-DE']) {
            const value = (m as unknown as Record<string, unknown>)[tag];
            next[tag] = appendVal(tag, typeof value === 'number' && Number.isFinite(value) ? value : Number.NaN);
          }
          return next;
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
