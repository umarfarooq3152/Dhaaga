import { api } from './client';

interface TranscribeResponse {
  text: string;
}

export async function transcribeAudio(audioBlob: Blob): Promise<string> {
  const formData = new FormData();
  formData.append('file', audioBlob, 'voice-query.webm');
  const response = await api.postFormData<TranscribeResponse>('/voice/transcribe', formData);
  return response.text;
}
