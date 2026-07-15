import { useCallback, useEffect, useRef, useState } from 'react';
import { transcribeAudio } from '../api/voice';

const MAX_RECORDING_MS = 30_000;
const AUDIO_MIME_TYPES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
];

function preferredAudioMimeType(): string {
  if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') return '';
  return AUDIO_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) || '';
}

function microphoneErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : '';
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return 'Microphone access is blocked. Allow it from the lock icon in the address bar, then try again.';
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return 'No microphone was found. Connect or enable a microphone, then try again.';
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'Your microphone is busy in another app. Close that app, then try again.';
  }
  return 'The microphone could not start. Check the browser microphone permission and try again.';
}

interface UseVoiceRecordingResult {
  isRecording: boolean;
  isTranscribing: boolean;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

/** Records a short voice query via the browser's MediaRecorder and sends it
 * to the backend for Whisper transcription (via Groq) once stopped. */
export function useVoiceRecording(onTranscribed: (text: string) => void): UseVoiceRecordingResult {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const autoStopTimerRef = useRef<number | null>(null);

  const clearAutoStopTimer = useCallback(() => {
    if (autoStopTimerRef.current !== null) window.clearTimeout(autoStopTimerRef.current);
    autoStopTimerRef.current = null;
  }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError('Voice search needs a secure page. Open Dhaaga on http://localhost:3000 and try again.');
      return;
    }
    if (typeof MediaRecorder === 'undefined') {
      setError('Voice recording is not supported by this browser. Try the latest Chrome or Edge.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = preferredAudioMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        clearAutoStopTimer();
        stopStream();
        mediaRecorderRef.current = null;
        setIsRecording(false);

        const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        chunksRef.current = [];

        if (audioBlob.size === 0) {
          setError('No audio was captured. Check your selected microphone and try again.');
          return;
        }

        setIsTranscribing(true);
        try {
          const text = await transcribeAudio(audioBlob);
          if (!text.trim()) throw new Error('Empty transcription');
          onTranscribed(text.trim());
        } catch (err) {
          console.error('Voice transcription failed:', err);
          setError("Sorry, I couldn't understand that. Please try again or type instead.");
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.onerror = () => {
        clearAutoStopTimer();
        stopStream();
        mediaRecorderRef.current = null;
        chunksRef.current = [];
        setIsRecording(false);
        setError('Recording stopped unexpectedly. Check your microphone and try again.');
      };

      // A timeslice makes short recordings reliably emit data in Chromium.
      recorder.start(750);
      setIsRecording(true);
      autoStopTimerRef.current = window.setTimeout(() => {
        if (recorder.state === 'recording') recorder.stop();
      }, MAX_RECORDING_MS);
    } catch (err) {
      console.error('Microphone access failed:', err);
      clearAutoStopTimer();
      stopStream();
      mediaRecorderRef.current = null;
      chunksRef.current = [];
      setIsRecording(false);
      setError(microphoneErrorMessage(err));
    }
  }, [clearAutoStopTimer, onTranscribed, stopStream]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  useEffect(() => () => {
    clearAutoStopTimer();
    const recorder = mediaRecorderRef.current;
    recorder?.onstop && (recorder.onstop = null);
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    stopStream();
  }, [clearAutoStopTimer, stopStream]);

  return { isRecording, isTranscribing, error, startRecording, stopRecording };
}
