import { useState, useRef, useEffect, useCallback } from 'react';

interface VoiceButtonProps {
  onTranscript: (text: string) => void;
  onAudioResponse?: (audioBlob: Blob) => void;
  disabled?: boolean;
  silenceTimeout?: number; // ms to wait after silence before stopping
  apiBase?: string;
}

type VoiceState = 'idle' | 'recording' | 'processing' | 'speaking';

export default function VoiceButton({
  onTranscript,
  onAudioResponse,
  disabled = false,
  silenceTimeout = 2000, // 2 seconds of silence
  apiBase = 'http://localhost:8000',
}: VoiceButtonProps) {
  const [state, setState] = useState<VoiceState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopRecording = useCallback(() => {
    // Clear timers
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    // Stop media recorder
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    // Stop all tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    setAudioLevel(0);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [stopRecording]);

  const processAudio = useCallback(async () => {
    setState('processing');

    try {
      // Convert webm to wav using AudioContext
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      const arrayBuffer = await audioBlob.arrayBuffer();

      // Decode audio
      const audioContext = new AudioContext({ sampleRate: 16000 });
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

      // Convert to WAV
      const wavBlob = audioBufferToWav(audioBuffer);
      onAudioResponse?.(wavBlob);

      // Send to transcription API
      const response = await fetch(`${apiBase}/v1/voice/transcribe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'audio/wav',
        },
        body: wavBlob,
      });

      if (!response.ok) {
        throw new Error(`Transcription failed: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.text) {
        onTranscript(result.text);
      } else if (result.error) {
        throw new Error(result.error);
      }

      audioContext.close();

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process audio');
    } finally {
      setState('idle');
    }
  }, [apiBase, onAudioResponse, onTranscript]);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setState('recording');
      audioChunksRef.current = [];

      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        }
      });
      streamRef.current = stream;

      // Create audio context for level monitoring
      audioContextRef.current = new AudioContext();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);

      // Start level monitoring
      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
      let lastSoundTime = Date.now();

      const checkAudioLevel = () => {
        if (!analyserRef.current || state !== 'recording') return;

        analyserRef.current.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setAudioLevel(average / 255);

        if (average > 10) {
          lastSoundTime = Date.now();
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        } else if (Date.now() - lastSoundTime > silenceTimeout && !silenceTimerRef.current) {
          silenceTimerRef.current = setTimeout(() => {
            stopRecording();
          }, 500);
        }

        animationFrameRef.current = requestAnimationFrame(checkAudioLevel);
      };

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        if (audioChunksRef.current.length > 0) {
          await processAudio();
        }
      };

      mediaRecorder.start(100);
      checkAudioLevel();

      setTimeout(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
          stopRecording();
        }
      }, 30000);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start recording');
      setState('idle');
    }
  }, [processAudio, silenceTimeout, state, stopRecording]);

  // Convert AudioBuffer to WAV blob
  const audioBufferToWav = (buffer: AudioBuffer): Blob => {
    const numChannels = 1;
    const sampleRate = buffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;

    const data = buffer.getChannelData(0);
    const dataLength = data.length * (bitDepth / 8);
    const bufferLength = 44 + dataLength;

    const arrayBuffer = new ArrayBuffer(bufferLength);
    const view = new DataView(arrayBuffer);

    // WAV header
    const writeString = (offset: number, str: string) => {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, bufferLength - 8, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * (bitDepth / 8), true);
    view.setUint16(32, numChannels * (bitDepth / 8), true);
    view.setUint16(34, bitDepth, true);
    writeString(36, 'data');
    view.setUint32(40, dataLength, true);

    // Write audio data
    let offset = 44;
    for (let i = 0; i < data.length; i++) {
      const sample = Math.max(-1, Math.min(1, data[i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
      offset += 2;
    }

    return new Blob([arrayBuffer], { type: 'audio/wav' });
  };

  const handleClick = () => {
    if (state === 'idle') {
      startRecording();
    } else if (state === 'recording') {
      stopRecording();
    }
  };

  const getButtonStyles = () => {
    const baseStyles = 'relative p-3 rounded-full transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500';

    switch (state) {
      case 'recording':
        return `${baseStyles} bg-red-600 hover:bg-red-700 text-white animate-pulse`;
      case 'processing':
        return `${baseStyles} bg-yellow-600 text-white cursor-wait`;
      case 'speaking':
        return `${baseStyles} bg-green-600 text-white`;
      default:
        return `${baseStyles} bg-slate-700 hover:bg-slate-600 text-slate-300`;
    }
  };

  const getIcon = () => {
    switch (state) {
      case 'recording':
        return (
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        );
      case 'processing':
        return (
          <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        );
      default:
        return (
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        );
    }
  };

  const getStatusText = () => {
    switch (state) {
      case 'recording':
        return 'Listening... (speak now)';
      case 'processing':
        return 'Processing...';
      case 'speaking':
        return 'Speaking...';
      default:
        return 'Click to speak';
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleClick}
        disabled={disabled || state === 'processing'}
        className={getButtonStyles()}
        title={getStatusText()}
      >
        {/* Audio level indicator */}
        {state === 'recording' && (
          <div
            className="absolute inset-0 rounded-full bg-red-400 opacity-50"
            style={{ transform: `scale(${1 + audioLevel * 0.5})` }}
          />
        )}
        <span className="relative z-10">{getIcon()}</span>
      </button>

      {state !== 'idle' && (
        <span className="text-sm text-slate-400">{getStatusText()}</span>
      )}

      {error && (
        <span className="text-sm text-red-400">{error}</span>
      )}
    </div>
  );
}
