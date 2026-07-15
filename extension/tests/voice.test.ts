import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferredAudioMimeType } from '../src/voice';

describe('voice MIME negotiation', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('prefers Opus WebM when supported', () => {
    vi.stubGlobal('MediaRecorder', { isTypeSupported: (type: string) => type === 'audio/webm;codecs=opus' });
    expect(preferredAudioMimeType()).toBe('audio/webm;codecs=opus');
  });

  it('falls back to the browser default', () => {
    vi.stubGlobal('MediaRecorder', { isTypeSupported: () => false });
    expect(preferredAudioMimeType()).toBe('');
  });
});
