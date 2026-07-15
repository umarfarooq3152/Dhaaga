import { api } from './client';

interface TranscribeResponse {
  text: string;
}

export async function transcribeAudio(audioBlob: Blob): Promise<string> {
  const formData = new FormData();
  const mimeType = audioBlob.type.toLowerCase();
  const extension = mimeType.includes('ogg')
    ? 'ogg'
    : mimeType.includes('mp4') || mimeType.includes('m4a')
      ? 'm4a'
      : mimeType.includes('mpeg')
        ? 'mp3'
        : mimeType.includes('wav')
          ? 'wav'
          : 'webm';
  formData.append('file', audioBlob, `voice-query.${extension}`);
  const response = await api.postFormData<TranscribeResponse>('/voice/transcribe', formData);
  return response.text;
}
