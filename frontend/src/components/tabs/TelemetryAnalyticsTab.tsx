import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { Radio, Waves, Zap, Gauge, Activity, Cpu, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { TelemetryData, SpectrumData, LiveMetric } from '../../types';
import { fetchLiveMetrics, subscribeLiveTelemetryStream, fetchTSDBHistory } from '../../api';

interface TelemetryAnalyticsTabProps {
  telemetry: TelemetryData | null;
  spectrum: SpectrumData | null;
  activeScenarioId?: string;
}

const EMPTY_TIMESTAMPS: number[] = [];
const EMPTY_SERIES: Record<string, number[]> = {};
const ECHARTS_OPTS = { renderer: 'canvas' as const };

export const TelemetryAnalyticsTab: React.FC<TelemetryAnalyticsTabProps> = ({
  telemetry,
  spectrum,
  activeScenarioId,
}) => {
  const isLiveStream = activeScenarioId === 'live_stream';
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
      } else {
        setRollingTimestamps(telemetry.timestamps || []);
        setRollingSeries(telemetry.series || {});
        setLiveMetric(null);
      }
    }
  }, [telemetry, isLiveStream]);

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
            'PT-30101': appendVal('PT-30101', 2.40),
            'DPS-30101': appendVal('DPS-30101', 0.12),
            'VI-301-R': appendVal('VI-301-R', 1.80),
            'TI-301-DE': appendVal('TI-301-DE', 48.50),
          };
        });
      },
      (err) => console.warn('Live stream SSE disconnected:', err)
    );

    return () => unsubscribe();
  }, [isLiveStream]);

  const timestamps = isLiveStream && rollingTimestamps.length > 0
    ? rollingTimestamps
    : (telemetry?.timestamps || EMPTY_TIMESTAMPS);

  const series = isLiveStream && Object.keys(rollingSeries).length > 0
    ? rollingSeries
    : (telemetry?.series || EMPTY_SERIES);

  // Formatter for timestamp seconds to mm:ss or HH:mm:ss if epoch
  const formatTime = (sec: number) => {
    if (sec > 1000000000) {
      const d = new Date(sec * 1000);
      return d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `T+${m}m${s.toString().padStart(2, '0')}s`;
  };

  // Synchronize timeseries charts group for crosshair and zoom linking
  const onTelemetryChartReady = useCallback((instance: any) => {
    if (instance) {
      instance.group = 'telemetry_sync';
      echarts.connect('telemetry_sync');
    }
  }, []);

  // Base options template for crisp light ECharts with animation disabled for flicker-free live streaming
  const baseChartTheme = useMemo(
    () => ({
      animation: false,
      animationDurationUpdate: 0,
      backgroundColor: '#FFFFFF',
      textStyle: { fontFamily: 'JetBrains Mono, monospace', color: '#334155' },
      grid: { top: 35, right: 20, bottom: 25, left: 55 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#E2E8F0',
        textStyle: { color: '#0F172A', fontSize: 11 },
        extraCssText: 'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-radius: 8px;',
        axisPointer: { type: 'cross', lineStyle: { color: '#94A3B8', type: 'dashed' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100, xAxisIndex: 0 },
      ],
    }),
    []
  );

  // 1. Bearing Temp Chart
  const bearingTempOption = useMemo(() => {
    const data = series['TI-301-DE'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'TI-301-DE · Drive-End Bearing Temperature (°C)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 40,
        max: 100,
        axisLabel: { formatter: '{value}°C', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Bearing Temp',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#DC2626' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(220, 38, 38, 0.18)' },
                { offset: 1, color: 'rgba(220, 38, 38, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 90.0,
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'Trip 90°C', position: 'insideEndTop', color: '#DC2626' },
              },
              {
                yAxis: 80.0,
                name: 'Alarm Limit',
                lineStyle: { color: '#D97706', type: 'dotted', width: 1.5 },
                label: { formatter: 'Alarm 80°C', position: 'insideEndTop', color: '#D97706' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 2. Vibration RMS Chart
  const vibrationOption = useMemo(() => {
    const data = series['VI-301-R'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'VI-301-R · Radial Vibration Velocity (mm/s RMS)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 14,
        axisLabel: { formatter: '{value}', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Vibration RMS',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#7C3AED' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(124, 58, 237, 0.18)' },
                { offset: 1, color: 'rgba(124, 58, 237, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 7.10,
                name: 'ISO Zone D Trip',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'Zone D Trip 7.1 mm/s', position: 'insideEndTop', color: '#DC2626' },
              },
              {
                yAxis: 4.50,
                name: 'Zone C Alarm',
                lineStyle: { color: '#D97706', type: 'dotted', width: 1.5 },
                label: { formatter: 'Zone C Alarm 4.5 mm/s', position: 'insideEndTop', color: '#D97706' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 3. Strainer Delta-P Chart
  const strainerDpOption = useMemo(() => {
    const data = series['DPS-30101'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'DPS-30101 · Suction Strainer STR-301A Delta-P (bar)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 2.2,
        axisLabel: { formatter: '{value} bar', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Strainer Delta-P',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#D97706' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(217, 119, 6, 0.18)' },
                { offset: 1, color: 'rgba(217, 119, 6, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 1.00,
                name: 'High Alarm',
                lineStyle: { color: '#D97706', type: 'dashed', width: 2 },
                label: { formatter: 'Alarm 1.00 bar', position: 'insideEndTop', color: '#D97706' },
              },
              {
                yAxis: 1.80,
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 1.5 },
                label: { formatter: 'Trip 1.80 bar', position: 'insideEndTop', color: '#DC2626' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 4. Suction Pressure vs NPSHr Chart
  const suctionOption = useMemo(() => {
    const data = series['PT-30101'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'PT-30101 · Pump Suction Pressure vs NPSHr (bar)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 3.0,
        axisLabel: { formatter: '{value} bar', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Suction Pressure',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#2563EB' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(37, 99, 235, 0.18)' },
                { offset: 1, color: 'rgba(37, 99, 235, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 1.20,
                name: 'NPSH Required Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'NPSHr 1.20 bar (Cavitation Inception)', position: 'insideEndBottom', color: '#DC2626' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 5. Motor Line Current Chart
  const motorCurrentOption = useMemo(() => {
    const data = series['IT-30101'] || [];
    return {
      ...baseChartTheme,
      grid: { top: 35, right: 20, bottom: 45, left: 55 },
      dataZoom: [
        { type: 'inside', start: 0, end: 100, xAxisIndex: 0 },
        {
          type: 'slider',
          start: 0,
          end: 100,
          xAxisIndex: 0,
          height: 16,
          bottom: 4,
          borderColor: '#E2E8F0',
          fillerColor: 'rgba(13, 148, 136, 0.12)',
          handleStyle: { color: '#0D9488', borderColor: '#CBD5E1' },
          textStyle: { color: '#334155', fontSize: 10 },
          moveHandleStyle: { color: '#94A3B8' },
        },
      ],
      title: {
        text: 'IT-30101 · Induction Motor Line Current (Amperes)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 130,
        axisLabel: { formatter: '{value} A', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Motor Current',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#0D9488' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(13, 148, 136, 0.15)' },
                { offset: 1, color: 'rgba(13, 148, 136, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 115.0,
                name: 'Continuous FLA',
                lineStyle: { color: '#D97706', type: 'dashed', width: 1.5 },
                label: { formatter: 'Rated FLA 115.0 A', position: 'insideEndTop', color: '#D97706' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 6. 20 kHz Vibration FFT Spectrum Chart
  const fftSpectrumOption = useMemo(() => {
    if (!spectrum) return null;
    const freqs = spectrum.frequencies || [];
    const mags = spectrum.magnitudes || [];
    const dataPairs = freqs.map((f, i) => [f, mags[i]]);

    const shaft1x = spectrum.shaft_1x_hz || 49.7;
    const shaft2x = spectrum.shaft_2x_hz || 99.3;

    return {
      animation: false,
      animationDurationUpdate: 0,
      backgroundColor: '#FFFFFF',
      textStyle: { fontFamily: 'JetBrains Mono, monospace', color: '#334155' },
      grid: { top: 70, right: 30, bottom: 40, left: 60 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#E2E8F0',
        textStyle: { color: '#0F172A', fontSize: 11 },
        extraCssText: 'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-radius: 8px;',
        formatter: (params: any[]) => {
          const item = params[0];
          const val = Array.isArray(item.value) ? item.value : [item.name, item.value];
          return `<div class="font-mono text-xs"><b>${val[0]} Hz</b>: ${val[1]} mm/s</div>`;
        },
      },
      title: {
        text: '20 kHz Vibration Velocity FFT Spectrum (0 - 10,000 Hz)',
        subtext: 'Discrete Shaft Harmonics (1X: 49.7 Hz, 2X: 99.3 Hz) vs High-Frequency Cavitation Noise Floor (2.0 - 8.0 kHz)',
        textStyle: { color: '#0F172A', fontSize: 13, fontWeight: 'bold' },
        subtextStyle: { color: '#475569', fontSize: 10 },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'value',
        min: 0,
        max: 10000,
        name: 'Frequency (Hz)',
        nameLocation: 'middle',
        nameGap: 25,
        nameTextStyle: { color: '#334155' },
        axisLabel: {
          formatter: (val: number) => (val % 1000 === 0 ? `${val / 1000}k` : ''),
          fontSize: 10,
          color: '#334155',
        },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      yAxis: {
        type: 'value',
        name: 'Amplitude (mm/s)',
        nameTextStyle: { color: '#334155' },
        axisLabel: { fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Spectral Amplitude',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 1.5, color: '#0284C7' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(2, 132, 199, 0.25)' },
                { offset: 1, color: 'rgba(2, 132, 199, 0.01)' },
              ],
            },
          },
          markArea: {
            itemStyle: {
              color: 'rgba(220, 38, 38, 0.08)',
              borderWidth: 1,
              borderColor: 'rgba(220, 38, 38, 0.25)',
            },
            data: [
              [
                {
                  name: 'Broadband Cavitation Acoustic Floor (2.0 - 8.0 kHz)',
                  xAxis: 2000,
                  label: {
                    position: 'top',
                    color: '#DC2626',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                  },
                },
                { xAxis: 8000 },
              ],
            ],
          },
          markPoint: {
            symbol: 'pin',
            symbolSize: 35,
            itemStyle: { color: '#D97706' },
            data: [
              {
                name: '1X Running Speed',
                coord: [shaft1x, spectrum.analysis?.peak_1x_amplitude_mms || 2.8],
                value: `1X (${shaft1x} Hz)`,
              },
              {
                name: '2X Harmonic',
                coord: [shaft2x, spectrum.analysis?.peak_2x_amplitude_mms || 0.4],
                value: `2X (${shaft2x} Hz)`,
              },
            ],
          },
          data: dataPairs,
        },
      ],
    };
  }, [spectrum]);

  // 7. VFD Output Frequency Chart (live_stream)
  const vfdFrequencyOption = useMemo(() => {
    const data = series['f_out'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'f_out · VFD Inverter Output Frequency (Hz)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 60 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 60,
        axisLabel: { formatter: '{value} Hz', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Output Frequency',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#0284C7' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(2, 132, 199, 0.22)' },
                { offset: 1, color: 'rgba(2, 132, 199, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 40.0,
                name: 'Operating Limit',
                lineStyle: { color: '#D97706', type: 'dashed', width: 2 },
                label: { formatter: 'Max Limit 40 Hz', position: 'insideEndTop', color: '#D97706' },
              },
              {
                yAxis: 50.0,
                name: 'Rated Frequency',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 1.5 },
                label: { formatter: 'Rated 50 Hz', position: 'insideEndTop', color: '#DC2626' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 8. VFD DC Bus Voltage Chart (live_stream)
  const vfdDcBusOption = useMemo(() => {
    const data = series['v_dc'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'v_dc · DC Bus Voltage (V DC)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 60 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 150,
        max: 225,
        axisLabel: { formatter: '{value} V', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'DC Bus Voltage',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#DC2626' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(220, 38, 38, 0.22)' },
                { offset: 1, color: 'rgba(220, 38, 38, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 195.0,
                name: 'Err06 Trip Threshold',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'Trip 195.0 V (Err06)', position: 'insideEndTop', color: '#DC2626' },
              },
              {
                yAxis: 190.0,
                name: 'High Alarm',
                lineStyle: { color: '#D97706', type: 'dotted', width: 1.5 },
                label: { formatter: 'Alarm 190.0 V', position: 'insideEndTop', color: '#D97706' },
              },
              {
                yAxis: 182.0,
                name: 'Nominal 40Hz',
                lineStyle: { color: '#10B981', type: 'dotted', width: 1.5 },
                label: { formatter: 'Nominal 182.0 V', position: 'insideEndBottom', color: '#10B981' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 9. VFD Motor Current Chart (live_stream)
  const vfdCurrentOption = useMemo(() => {
    const data = series['current'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'I_out · Motor Phase Current (Amperes)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 60 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 4.0,
        axisLabel: { formatter: '{value} A', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Motor Current',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#0D9488' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(13, 148, 136, 0.20)' },
                { offset: 1, color: 'rgba(13, 148, 136, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 2.50,
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'Trip 2.50 A', position: 'insideEndTop', color: '#DC2626' },
              },
              {
                yAxis: 2.00,
                name: 'High Alarm',
                lineStyle: { color: '#D97706', type: 'dotted', width: 1.5 },
                label: { formatter: 'Alarm 2.00 A', position: 'insideEndTop', color: '#D97706' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 10. VFD Motor RPM Chart (live_stream)
  const vfdRpmOption = useMemo(() => {
    const data = series['rpm'] || [];
    return {
      ...baseChartTheme,
      grid: { top: 35, right: 20, bottom: 45, left: 55 },
      dataZoom: [
        { type: 'inside', start: 0, end: 100, xAxisIndex: 0 },
        {
          type: 'slider',
          start: 0,
          end: 100,
          xAxisIndex: 0,
          height: 16,
          bottom: 4,
          borderColor: '#E2E8F0',
          fillerColor: 'rgba(124, 58, 237, 0.12)',
          handleStyle: { color: '#7C3AED', borderColor: '#CBD5E1' },
          textStyle: { color: '#334155', fontSize: 10 },
          moveHandleStyle: { color: '#94A3B8' },
        },
      ],
      title: {
        text: 'RPM · Induction Motor Speed (RPM)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 60 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 1800,
        axisLabel: { formatter: '{value}', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Motor Speed',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#7C3AED' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(124, 58, 237, 0.18)' },
                { offset: 1, color: 'rgba(124, 58, 237, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 1450.0,
                name: 'Rated Speed',
                lineStyle: { color: '#7C3AED', type: 'dashed', width: 1.5 },
                label: { formatter: 'Rated 1450 RPM', position: 'insideEndTop', color: '#7C3AED' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  const currentFOut = (isLiveStream && liveMetric ? liveMetric.f_out : (series['f_out']?.[series['f_out'].length - 1])) ?? 40.0;
  const currentVDc = (isLiveStream && liveMetric ? liveMetric.v_dc : (series['v_dc']?.[series['v_dc'].length - 1])) ?? 182.0;
  const currentAmp = (isLiveStream && liveMetric ? liveMetric.current : (series['current']?.[series['current'].length - 1])) ?? 1.15;
  const currentRpm = (isLiveStream && liveMetric ? liveMetric.rpm : (series['rpm']?.[series['rpm'].length - 1])) ?? 1199.0;
  const currentStatus = (isLiveStream && liveMetric ? liveMetric.status : undefined) || ((series['fault_code']?.[series['fault_code'].length - 1] || 0) > 0 ? 'TRIPPED' : 'RUNNING');

  const latestTi = series['TI-301-DE']?.[series['TI-301-DE'].length - 1] ?? 48.5;
  const latestVi = series['VI-301-R']?.[series['VI-301-R'].length - 1] ?? 1.80;
  const latestDps = series['DPS-30101']?.[series['DPS-30101'].length - 1] ?? 0.12;
  const latestPt = series['PT-30101']?.[series['PT-30101'].length - 1] ?? 2.40;

  return (
    <div className="space-y-4">
      {/* Live Hardware Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {isVfdAsset ? (
          <>
            {/* Card 1: VFD Output Frequency */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Zap className="w-3.5 h-3.5 text-sky-600" />
                  Output Frequency (f_out)
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    currentFOut > 42
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {currentFOut > 42 ? 'WARNING' : 'NOMINAL'}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {currentFOut.toFixed(2)}{' '}
                <span className="text-xs font-normal text-slate-500">Hz</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Nominal limit: 40.00 Hz · Rated: 50.00 Hz
              </div>
            </div>

            {/* Card 2: DC Bus Voltage */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Gauge className="w-3.5 h-3.5 text-rose-600" />
                  DC Bus Voltage (v_dc)
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    currentVDc >= 195.0
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : currentVDc >= 190.0
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {currentVDc >= 195.0
                    ? 'TRIP'
                    : currentVDc >= 190.0
                    ? 'ALARM'
                    : 'STABLE'}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {currentVDc.toFixed(1)}{' '}
                <span className="text-xs font-normal text-slate-500">V</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Nominal: 182.0 V (40 Hz) · Trip limit: 195.0 V (&gt;195V trips Err06)
              </div>
            </div>

            {/* Card 3: Motor Current */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Activity className="w-3.5 h-3.5 text-teal-600" />
                  Motor Current
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    currentAmp >= 2.5
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : currentAmp > 2.0
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {currentAmp >= 2.5 ? 'OVERLOAD' : 'NOMINAL'}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {currentAmp.toFixed(2)}{' '}
                <span className="text-xs font-normal text-slate-500">A</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Rated FLA: 1.50 A · Trip limit: 2.50 A
              </div>
            </div>

            {/* Card 4: Motor RPM */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Cpu className="w-3.5 h-3.5 text-purple-600" />
                  Motor Speed
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    currentStatus === 'TRIPPED'
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {currentStatus}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {Math.round(currentRpm).toLocaleString()}{' '}
                <span className="text-xs font-normal text-slate-500">RPM</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Synchronous: 1,450 RPM (4-pole)
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Card 1: Bearing Temp */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Zap className="w-3.5 h-3.5 text-rose-600" />
                  Bearing Temp (TI-301-DE)
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    latestTi >= 90
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : latestTi > 80
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {latestTi >= 90 ? 'TRIP' : latestTi > 80 ? 'ALARM' : 'NORMAL'}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {latestTi.toFixed(1)}{' '}
                <span className="text-xs font-normal text-slate-500">°C</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Alarm: 80.0°C · Trip: 90.0°C
              </div>
            </div>

            {/* Card 2: Vibration RMS */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Activity className="w-3.5 h-3.5 text-purple-600" />
                  Vibration RMS (VI-301-R)
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    latestVi >= 7.1
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : latestVi > 4.5
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {latestVi >= 7.1 ? 'ZONE D TRIP' : latestVi > 4.5 ? 'ZONE C ALARM' : 'ZONE A/B'}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {latestVi.toFixed(2)}{' '}
                <span className="text-xs font-normal text-slate-500">mm/s</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Zone C Alarm: 4.50 mm/s · Trip: 7.10 mm/s
              </div>
            </div>

            {/* Card 3: Strainer Delta-P */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Gauge className="w-3.5 h-3.5 text-amber-600" />
                  Strainer Delta-P (DPS-30101)
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    latestDps >= 1.8
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : latestDps > 1.0
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {latestDps >= 1.8 ? 'BLINDED' : latestDps > 1.0 ? 'FOULING' : 'CLEAN'}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {latestDps.toFixed(2)}{' '}
                <span className="text-xs font-normal text-slate-500">bar</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Clean: 0.12 bar · Alarm: 1.00 bar
              </div>
            </div>

            {/* Card 4: Suction Pressure */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-1.5">
                <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                  <Cpu className="w-3.5 h-3.5 text-blue-600" />
                  Suction Pressure (PT-30101)
                </span>
                <span
                  className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                    latestPt <= 1.2
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {latestPt <= 1.2 ? 'NPSH CAVITATION' : 'HEALTHY'}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-slate-900">
                {latestPt.toFixed(2)}{' '}
                <span className="text-xs font-normal text-slate-500">bar</span>
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                Normal: 2.40 bar · NPSHr limit: 1.20 bar
              </div>
            </div>
          </>
        )}
      </div>

      {/* Overview Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-teal-50 text-teal-600 border border-teal-100">
            <Waves className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold font-mono text-slate-800 uppercase flex items-center gap-2">
              <span>
                {isLiveStream
                  ? 'Wecon VFD Live Streaming Telemetry (1 Hz Continuous)'
                  : 'High-Frequency Synchronized Telemetry Analytics'}
              </span>
              {isLiveStream && (
                <span className="px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-[10px] font-bold animate-pulse flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  LIVE SSE
                </span>
              )}
            </div>
            <div className="text-[11px] text-slate-500">
              {isLiveStream
                ? 'Continuous real-time 1 Hz telemetry streaming from Wecon HMI (rolling 300-point embedded TSDB buffer)'
                : '60-minute interval (3,600 samples at 1 Hz) + 20,000-point 20 kHz Piezoelectric FFT'}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-700">
            Points: <strong className="text-teal-700">{timestamps.length.toLocaleString()}</strong>
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-700">
            Engine: <strong className="text-blue-700">ECharts Canvas (60 FPS)</strong>
          </span>
        </div>
      </div>

      {/* 20 kHz FFT Vibration Spectrum Panel (Only shown on centrifugal pump cavitation scenarios, hidden in VFD live mode) */}
      {!isVfdAsset && spectrum && fftSpectrumOption && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
            <div className="flex items-center space-x-2">
              <Radio className="w-4 h-4 text-purple-600" />
              <span className="font-mono text-xs font-bold text-slate-900">
                Acoustic Frequency Decomposition (FFT)
              </span>
            </div>
            <div className="flex items-center space-x-2 text-[11px] font-mono">
              <span
                className={`px-2 py-0.5 rounded font-bold ${
                  spectrum.analysis?.cavitation_detected
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {spectrum.analysis?.cavitation_detected ? '🚨 CAVITATION CONFIRMED' : '✓ HEALTHY BASELINE'}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-600">
                Broadband Ratio: <strong className="text-purple-700">{spectrum.analysis?.broadband_cavitation_ratio_pct}%</strong>
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-600">
                Overall RMS: <strong className="text-amber-700">{spectrum.analysis?.overall_rms} mm/s</strong>
              </span>
            </div>
          </div>

          <div className="h-[240px] w-full">
            <ReactECharts
              option={fftSpectrumOption}
              style={{ height: '100%', width: '100%' }}
              opts={ECHARTS_OPTS}
              lazyUpdate={true}
              notMerge={false}
            />
          </div>

          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 flex items-start space-x-2">
            <span className="text-teal-700 font-bold">FFT Diagnosis:</span>
            <span>{spectrum.analysis?.diagnosis}</span>
          </div>
        </div>
      )}

      {/* Timeseries Charts Grid */}
      {isVfdAsset ? (
        /* VFD Hardware Timeseries Grid (live_stream or VFD HIL incident) */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Chart 1: VFD Output Frequency */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={vfdFrequencyOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>

          {/* Chart 2: DC Bus Voltage */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={vfdDcBusOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>

          {/* Chart 3: Motor Output Current */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={vfdCurrentOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>

          {/* Chart 4: Motor RPM (Full Width or 2-col) */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={vfdRpmOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>
        </div>
      ) : (
        /* Standard 5 Core Process & Electrical Timeseries Charts Grid */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Chart 1: Bearing Temp */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={bearingTempOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>

          {/* Chart 2: Vibration RMS */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={vibrationOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>

          {/* Chart 3: Strainer Delta-P */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={strainerDpOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>

          {/* Chart 4: Suction Pressure vs NPSHr */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={suctionOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>

          {/* Chart 5: Motor Line Current (Full Width) */}
          <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
            <div className="h-[200px] w-full">
              <ReactECharts
                option={motorCurrentOption}
                style={{ height: '100%', width: '100%' }}
                opts={ECHARTS_OPTS}
                lazyUpdate={true}
                notMerge={false}
                onChartReady={onTelemetryChartReady}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
