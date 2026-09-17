import React, { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { Waves } from 'lucide-react';
import { TelemetryData, SpectrumData } from '../../types';
import { useLiveTelemetry } from '../../hooks/useLiveTelemetry';
import { TelemetryMetricsCards } from '../telemetry/TelemetryMetricsCards';
import { VibrationSpectrumSection } from '../telemetry/VibrationSpectrumSection';

interface TelemetryAnalyticsTabProps {
  telemetry: TelemetryData | null;
  spectrum: SpectrumData | null;
  activeScenarioId?: string;
  onToggleSimulation?: (enabled: boolean, scenario?: string, duration?: number) => void;
  isSimulated?: boolean;
  telemetryConnected?: boolean;
  simulationScenario?: string;
  simulationPhase?: string;
  simulationCountdown?: number;
}

const EMPTY_TIMESTAMPS: number[] = [];
const EMPTY_SERIES: Record<string, number[]> = {};
const ECHARTS_OPTS = { renderer: 'canvas' as const };

export const TelemetryAnalyticsTab: React.FC<TelemetryAnalyticsTabProps> = ({
  telemetry,
  spectrum,
  activeScenarioId,
  onToggleSimulation,
  isSimulated: _isSimulated = false,
  telemetryConnected: _telemetryConnected = false,
  simulationScenario: _simulationScenario = 'nominal',
  simulationPhase: _simulationPhase = 'IDLE',
  simulationCountdown: _simulationCountdown = 0,
}) => {
  const {
    isLiveStream,
    isVfdAsset,
    liveMetric,
    rollingTimestamps,
    rollingSeries,
  } = useLiveTelemetry(telemetry, activeScenarioId);

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
                label: { formatter: '90°C', position: 'insideEndTop', color: '#DC2626', fontWeight: 'bold' },
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
                label: { formatter: '7.10 mm/s', position: 'insideEndTop', color: '#DC2626', fontWeight: 'bold' },
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
                yAxis: 1.80,
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: '1.80 bar', position: 'insideEndTop', color: '#DC2626', fontWeight: 'bold' },
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
                label: { formatter: '1.20 bar', position: 'insideEndBottom', color: '#DC2626', fontWeight: 'bold' },
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
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: '115.0 A', position: 'insideEndTop', color: '#DC2626', fontWeight: 'bold' },
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
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: '40.00 Hz', position: 'insideEndTop', color: '#DC2626', fontSize: 10, fontWeight: 'bold' },
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
      grid: { top: 35, right: 35, bottom: 25, left: 55 },
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
        min: 0,
        max: (value: { max: number }) => Math.max(225, Math.ceil(value.max * 1.08)),
        axisLabel: { formatter: '{value} V', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'DC Bus Voltage',
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
                yAxis: 195.0,
                name: 'Err06 Trip Threshold',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: {
                  formatter: '195.0 V',
                  position: 'insideEndTop',
                  color: '#DC2626',
                  fontSize: 10,
                  fontWeight: 'bold',
                },
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
      grid: { top: 35, right: 35, bottom: 25, left: 55 },
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
                label: { formatter: '2.50 A', position: 'insideEndTop', color: '#DC2626', fontSize: 10, fontWeight: 'bold' },
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
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: '1450 RPM', position: 'insideEndTop', color: '#DC2626', fontSize: 10, fontWeight: 'bold' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // For live stream: prefer liveMetric, but fall back to rollingSeries last point when liveMetric
  // has physically-invalid zero values (e.g., stale init before first SSE message arrives).
  const isTelemetryConnected = isLiveStream
    ? (liveMetric ? (liveMetric.telemetry_connected !== false && liveMetric.status !== 'OFFLINE') : false)
    : true;

  const _lmFOut  = isLiveStream && liveMetric ? liveMetric.f_out  : null;
  const _lmVDc   = isLiveStream && liveMetric ? liveMetric.v_dc   : null;
  const _lmAmp   = isLiveStream && liveMetric ? liveMetric.current : null;
  const _lmRpm   = isLiveStream && liveMetric ? liveMetric.rpm    : null;
  const _serFOut  = series['f_out']?.[series['f_out'].length - 1];
  const _serVDc   = series['v_dc']?.[series['v_dc'].length - 1];
  const _serAmp   = series['current']?.[series['current'].length - 1];
  const _serRpm   = series['rpm']?.[series['rpm'].length - 1];

  const currentFOut = isTelemetryConnected
    ? (((_lmFOut !== null && _lmFOut !== 0) ? _lmFOut : (_serFOut ?? _lmFOut)) ?? 40.0)
    : 0.0;
  const currentVDc  = isTelemetryConnected
    ? (((_lmVDc  !== null && _lmVDc  !== 0) ? _lmVDc  : (_serVDc  ?? _lmVDc )) ?? 182.0)
    : 0.0;
  const currentAmp  = isTelemetryConnected
    ? (_lmAmp  !== null ? _lmAmp  : (_serAmp  ?? 0.0))
    : 0.0;
  const currentRpm  = isTelemetryConnected
    ? (((_lmRpm  !== null && _lmRpm  !== 0) ? _lmRpm  : (_serRpm  ?? _lmRpm )) ?? 1199.0)
    : 0.0;
  const currentStatus = isLiveStream
    ? (liveMetric ? liveMetric.status : (isTelemetryConnected ? 'RUNNING' : 'OFFLINE'))
    : ((series['fault_code']?.[series['fault_code'].length - 1] || 0) > 0 ? 'TRIPPED' : 'RUNNING');

  const latestTi = series['TI-301-DE']?.[series['TI-301-DE'].length - 1] ?? 48.5;
  const latestVi = series['VI-301-R']?.[series['VI-301-R'].length - 1] ?? 1.80;
  const latestDps = series['DPS-30101']?.[series['DPS-30101'].length - 1] ?? 0.12;
  const latestPt = series['PT-30101']?.[series['PT-30101'].length - 1] ?? 2.40;
  const freqStatus = !isTelemetryConnected
    ? 'OFFLINE'
    : currentFOut > 42
    ? 'WARNING'
    : 'NOMINAL';

  return (
    <div className="space-y-4">
      {/* Offline Alert Banner */}
      {isLiveStream && !isTelemetryConnected && (
        <div className="bg-amber-50/90 border border-amber-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center space-x-3">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500" />
            </span>
            <div>
              <div className="font-mono text-xs font-bold text-amber-950 flex items-center gap-2">
                <span>⚠️ TELEMETRY OFFLINE · NO LIVE HARDWARE PACKETS DETECTED</span>
              </div>
              <div className="text-[11px] text-amber-800">
                Awaiting 1 Hz Modbus RTU packets on MQTT port 1883. Metrics show 0.0 until hardware connects or simulation is enabled.
              </div>
            </div>
          </div>
          {onToggleSimulation && (
            <button
              onClick={() => onToggleSimulation(true)}
              className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white font-mono text-xs font-bold rounded-lg shadow-xs transition-colors cursor-pointer flex items-center space-x-1.5"
            >
              <span>🧪 Enable Simulation Mode</span>
            </button>
          )}
        </div>
      )}

      {/* Live Hardware Summary Cards */}
      <TelemetryMetricsCards
        isVfdAsset={isVfdAsset}
        frequencyHz={currentFOut}
        freqStatus={freqStatus}
        voltageVdc={currentVDc}
        currentAmp={currentAmp}
        currentRpm={currentRpm}
        currentStatus={currentStatus}
        latestTi={latestTi}
        latestVi={latestVi}
        latestDps={latestDps}
        latestPt={latestPt}
      />

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

      {/* 20 kHz FFT Vibration Spectrum Panel */}
      {!isVfdAsset && (
        <VibrationSpectrumSection
          spectrum={spectrum}
          fftSpectrumOption={fftSpectrumOption}
          echartsOpts={ECHARTS_OPTS}
        />
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
