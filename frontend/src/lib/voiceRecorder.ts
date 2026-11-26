/**
 * Pure Web Audio API 16 kHz mono PCM WAV recorder with live RMS input metering.
 * Avoids Linux/Brave MediaRecorder WebM/Opus container muxing glitches and gives
 * immediate visual confirmation that microphone hardware audio is arriving.
 */

export function downsampleTo16k(samples: Float32Array, inputSampleRate: number): Float32Array {
  if (inputSampleRate === 16000) return samples;
  const ratio = inputSampleRate / 16000;
  const outLength = Math.max(1, Math.round(samples.length / ratio));
  const result = new Float32Array(outLength);
  for (let i = 0; i < outLength; i += 1) {
    const start = Math.floor(i * ratio);
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (let j = start; j < end; j += 1) {
      sum += samples[j];
      count += 1;
    }
    result[i] = count > 0 ? sum / count : samples[Math.min(start, samples.length - 1)] || 0;
  }
  return result;
}

export function encodePcmWav(chunks: Float32Array[], inputSampleRate: number): Blob {
  const totalLen = chunks.reduce((acc, c) => acc + c.length, 0);
  const merged = new Float32Array(totalLen);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }

  const downsampled = downsampleTo16k(merged, inputSampleRate);
  const buffer = new ArrayBuffer(44 + downsampled.length * 2);
  const view = new DataView(buffer);

  const writeStr = (pos: number, str: string) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(pos + i, str.charCodeAt(i));
    }
  };

  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + downsampled.length * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // Linear PCM
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, 16000, true); // Sample rate
  view.setUint32(28, 16000 * 2, true); // Byte rate
  view.setUint16(32, 2, true); // Block align
  view.setUint16(34, 16, true); // Bits per sample
  writeStr(36, 'data');
  view.setUint32(40, downsampled.length * 2, true);

  let dataOffset = 44;
  for (let i = 0; i < downsampled.length; i += 1) {
    const s = Math.max(-1, Math.min(1, downsampled[i]));
    view.setInt16(dataOffset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    dataOffset += 2;
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

export interface PcmCaptureSession {
  stop: () => Promise<{ blob: Blob; hadSignal: boolean; durationMs: number }>;
  cancel: () => void;
}

export async function startPcmWavCapture(
  stream: MediaStream,
  onLevel: (pct: number) => void
): Promise<PcmCaptureSession | null> {
  if (typeof window === 'undefined') return null;
  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) return null;

  const ctx = new AudioCtx();
  if (ctx.state === 'suspended') {
    await ctx.resume();
  }

  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  // Route via zero-gain node so browser runs audio graph without playing mic echo
  const silentGain = ctx.createGain();
  silentGain.gain.value = 0;

  const chunks: Float32Array[] = [];
  let peakRms = 0;
  const startedAt = Date.now();

  processor.onaudioprocess = (ev) => {
    const input = ev.inputBuffer.getChannelData(0);
    const copy = new Float32Array(input.length);
    copy.set(input);
    chunks.push(copy);

    let sq = 0;
    for (let i = 0; i < input.length; i += 4) {
      const v = input[i];
      sq += v * v;
    }
    const rms = Math.sqrt(sq / Math.max(1, Math.ceil(input.length / 4)));
    if (rms > peakRms) peakRms = rms;
    const pct = Math.min(100, Math.round(rms * 450));
    onLevel(pct);
  };

  source.connect(processor);
  processor.connect(silentGain);
  silentGain.connect(ctx.destination);

  const cleanup = async () => {
    try {
      processor.disconnect();
      source.disconnect();
      silentGain.disconnect();
    } catch {
      // ignore
    }
    if (ctx.state !== 'closed') {
      try {
        await ctx.close();
      } catch {
        // ignore
      }
    }
  };

  return {
    stop: async () => {
      const durationMs = Date.now() - startedAt;
      const sampleRate = ctx.sampleRate || 48000;
      await cleanup();
      const blob = encodePcmWav(chunks, sampleRate);
      return { blob, hadSignal: peakRms > 0.0015, durationMs };
    },
    cancel: () => {
      void cleanup();
    },
  };
}
