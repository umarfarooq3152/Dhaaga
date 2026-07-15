import { useCallback, useRef, useState } from 'react';
import { transcribeAudio } from '../api/voice';

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

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;

        const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        chunksRef.current = [];

        if (audioBlob.size === 0) return;

        setIsTranscribing(true);
        try {
          const text = await transcribeAudio(audioBlob);
          if (text.trim()) onTranscribed(text.trim());
        } catch (err) {
          console.error('Voice transcription failed:', err);
          setError("Sorry, I couldn't understand that. Please try again or type instead.");
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access failed:', err);
      setError('Microphone access is needed for voice search — please allow it and try again.');
    }
  }, [onTranscribed]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  return { isRecording, isTranscribing, error, startRecording, stopRecording };
}
