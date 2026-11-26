import { config } from '../lib/config';
import {
  extractApiErrorMessage,
  fetchCsrfToken,
  getCsrfFromCookie,
  isValidCsrfToken,
} from './authApi';
import {
  AiConversationDetail,
  AiConversationSummary,
  AiMessage,
  RagReindexResult,
  UserAiPreference,
  VoiceExpenseDraft,
  WebProviderId,
  WebProviderStatus,
} from '../types/assistant';

async function assistantRequest<T>(
  endpoint: string,
  options: RequestInit & { timeoutMs?: number } = {}
): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();
  const { timeoutMs = 45000, ...fetchOptions } = options;

  const isFormData = typeof FormData !== 'undefined' && fetchOptions.body instanceof FormData;
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
    let token = getCsrfFromCookie();
    if (!isValidCsrfToken(token)) {
      token = await fetchCsrfToken(true);
    }
    if (token) headers['X-CSRF-Token'] = token;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: 'include',
      signal: controller.signal,
    });

    if (response.status === 403 && ['POST', 'PATCH', 'DELETE', 'PUT'].includes(method)) {
      try {
        const errJson = await response.clone().json();
        if (String(errJson?.detail || '').toLowerCase().includes('csrf')) {
          const fresh = await fetchCsrfToken(true);
          if (fresh) {
            headers['X-CSRF-Token'] = fresh;
            response = await fetch(url, {
              ...fetchOptions,
              headers,
              credentials: 'include',
              signal: controller.signal,
            });
          }
        }
      } catch {
        // ignore JSON parse failure
      }
    }
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') {
      throw new Error('Assistant request timed out. Please retry.');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let errData: unknown = null;
    try {
      errData = await response.json();
    } catch {
      errData = await response.text().catch(() => null);
    }
    throw new Error(extractApiErrorMessage(errData, response.status));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const assistantApi = {
  listProviders(): Promise<WebProviderStatus[]> {
    return assistantRequest<WebProviderStatus[]>('/api/v1/assistant/providers');
  },

  getPreferences(): Promise<UserAiPreference> {
    return assistantRequest<UserAiPreference>('/api/v1/assistant/preferences');
  },

  updatePreferences(payload: {
    default_web_provider?: WebProviderId;
    web_search_enabled?: boolean;
    voice_read_aloud_enabled?: boolean;
    auto_execute_actions?: boolean;
  }): Promise<UserAiPreference> {
    return assistantRequest<UserAiPreference>('/api/v1/assistant/preferences', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  listConversations(): Promise<AiConversationSummary[]> {
    return assistantRequest<AiConversationSummary[]>('/api/v1/assistant/conversations');
  },

  createConversation(payload?: {
    title?: string;
    preferred_provider?: WebProviderId;
    web_search_enabled?: boolean;
  }): Promise<AiConversationDetail> {
    return assistantRequest<AiConversationDetail>('/api/v1/assistant/conversations', {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    });
  },

  getConversation(id: string): Promise<AiConversationDetail> {
    return assistantRequest<AiConversationDetail>(`/api/v1/assistant/conversations/${id}`);
  },

  updateConversation(
    id: string,
    payload: {
      title?: string;
      preferred_provider?: WebProviderId;
      web_search_enabled?: boolean;
    }
  ): Promise<AiConversationSummary> {
    return assistantRequest<AiConversationSummary>(`/api/v1/assistant/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  deleteConversation(id: string): Promise<void> {
    return assistantRequest<void>(`/api/v1/assistant/conversations/${id}`, {
      method: 'DELETE',
    });
  },

  sendMessage(
    conversationId: string,
    payload: {
      content: string;
      web_search_enabled?: boolean;
      web_provider?: WebProviderId;
      include_personal_context?: boolean;
      auto_execute?: boolean;
    }
  ): Promise<AiMessage> {
    return assistantRequest<AiMessage>(
      `/api/v1/assistant/conversations/${conversationId}/messages`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
        timeoutMs: 60000,
      }
    );
  },

  reindexRag(): Promise<RagReindexResult> {
    return assistantRequest<RagReindexResult>('/api/v1/assistant/rag/reindex', {
      method: 'POST',
      body: JSON.stringify({}),
    });
  },

  parseVoiceExpense(transcript: string): Promise<VoiceExpenseDraft> {
    return assistantRequest<VoiceExpenseDraft>('/api/v1/assistant/voice/parse-expense', {
      method: 'POST',
      body: JSON.stringify({ transcript }),
    });
  },

  transcribeVoice(audioBlob: Blob): Promise<{ transcript: string; provider: string }> {
    const t = (audioBlob.type || '').toLowerCase();
    const ext = t.includes('wav')
      ? 'wav'
      : t.includes('ogg')
      ? 'ogg'
      : t.includes('mp4')
      ? 'm4a'
      : 'webm';
    const formData = new FormData();
    formData.append('audio', audioBlob, `recording.${ext}`);
    return assistantRequest<{ transcript: string; provider: string }>(
      '/api/v1/assistant/voice/transcribe',
      {
        method: 'POST',
        body: formData,
        timeoutMs: 30000,
      }
    );
  },

  async synthesizeSpeech(text: string): Promise<Blob> {
    const url = `${config.apiBaseUrl}/api/v1/assistant/voice/speak`;
    let token = getCsrfFromCookie();
    if (!isValidCsrfToken(token)) {
      token = await fetchCsrfToken(true);
    }
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) headers['X-CSRF-Token'] = token;

    let response = await fetch(url, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({ text }),
    });
    if (response.status === 403) {
      const fresh = await fetchCsrfToken(true);
      if (fresh) {
        headers['X-CSRF-Token'] = fresh;
        response = await fetch(url, {
          method: 'POST',
          headers,
          credentials: 'include',
          body: JSON.stringify({ text }),
        });
      }
    }
    if (!response.ok) {
      throw new Error(`Speech synthesis failed (${response.status}).`);
    }
    return response.blob();
  },

  confirmMessageAction(
    messageId: string,
    payload: Record<string, unknown> = {}
  ): Promise<AiMessage> {
    return assistantRequest<AiMessage>(
      `/api/v1/assistant/messages/${messageId}/confirm-action`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  },
};
