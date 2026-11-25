import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  Database,
  Edit3,
  ExternalLink,
  FileText,
  Globe,
  Mic,
  MicOff,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { assistantApi } from '../../services/assistantApi';
import { billsApi } from '../../services/billsApi';
import { financeApi } from '../../services/financeApi';
import {
  AiConversationDetail,
  AiConversationSummary,
  AiMessage,
  ChatBillDraftAction,
  ChatTransactionDraftAction,
  EvidenceItem,
  UserAiPreference,
  VoiceExpenseDraft,
  WebProviderId,
  WebProviderStatus,
} from '../../types/assistant';
import { FinancialAccount, FinancialCategory } from '../../types/finance';
import { formatDate } from '../../lib/formatters';

interface AssistantPageProps {
  onNavigate: (view: string) => void;
}

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  0: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionErrorEventLike {
  error: string;
}

interface SpeechRecognitionInstanceLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionInstanceLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

function getSafeExternalUrl(rawUrl?: string | null): string | null {
  if (!rawUrl) return null;
  try {
    const parsed = new URL(rawUrl.trim());
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

function cleanSpeechText(raw: string): string {
  return raw
    .replace(/\[\d+\]|【\d+】/g, '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/\|[-:]+\|/g, ' ')
    .replace(/\|/g, ', ')
    .replace(/₹\s*/g, 'rupees ')
    .replace(/[#*_`>~•-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 1500);
}

const STARTER_PROMPTS = [
  'How much did I spend this month and what bills or EMIs are coming up soon?',
  'Summarize my uploaded documents, receipts, or rent agreements.',
  'Explain what my cash-flow forecast predicts and how I can improve monthly savings.',
  'What are the latest RBI rules on UPI transaction limits in India?',
  'Compare PPF and ELSS tax benefits under Section 80C in India.',
];

function renderInlineTokens(
  text: string,
  citationIds: Set<number>,
  onCitationClick: (citationNum: number) => void,
  keyPrefix: string
): React.ReactNode[] {
  const parts = text.split(/(\[\d+\]|【\d+】|\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    const citMatch = /^(?:\[(\d+)\]|【(\d+)】)$/.exec(part);
    if (citMatch) {
      const num = Number(citMatch[1] || citMatch[2]);
      const clickable = citationIds.has(num);
      return clickable ? (
        <button
          key={`${keyPrefix}-c-${idx}`}
          type="button"
          onClick={() => onCitationClick(num)}
          className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-[11px] font-semibold rounded bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 align-baseline"
          title={`View evidence [${num}]`}
        >
          [{num}]
        </button>
      ) : (
        <span key={`${keyPrefix}-c-${idx}`} className="text-slate-500 text-xs">
          [{num}]
        </span>
      );
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={`${keyPrefix}-b-${idx}`} className="font-semibold text-slate-900">
          {renderInlineTokens(part.slice(2, -2), citationIds, onCitationClick, `${keyPrefix}-bi-${idx}`)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return (
        <em key={`${keyPrefix}-em-${idx}`} className="italic text-slate-700">
          {renderInlineTokens(part.slice(1, -1), citationIds, onCitationClick, `${keyPrefix}-ei-${idx}`)}
        </em>
      );
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code
          key={`${keyPrefix}-cd-${idx}`}
          className="px-1 py-0.5 rounded bg-slate-100 text-slate-800 text-xs font-mono"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <React.Fragment key={`${keyPrefix}-t-${idx}`}>{part}</React.Fragment>;
  });
}

function parseTableCells(rowLine: string): string[] {
  const trimmed = rowLine.trim().replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((c) => c.trim());
}

function isTableSeparatorRow(rowLine: string): boolean {
  const trimmed = rowLine.trim();
  return /^\|?(\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?$/.test(trimmed);
}

function renderTextWithCitations(
  content: string,
  citationIds: Set<number>,
  onCitationClick: (citationNum: number) => void
): React.ReactNode {
  const lines = content.split('\n');
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      nodes.push(<div key={`sp-${i}`} className="h-1" />);
      i += 1;
      continue;
    }

    // Markdown table block detection
    if (
      trimmed.startsWith('|') &&
      i + 1 < lines.length &&
      isTableSeparatorRow(lines[i + 1])
    ) {
      const headers = parseTableCells(trimmed);
      const bodyRows: string[][] = [];
      let j = i + 2;
      while (j < lines.length && lines[j].trim().startsWith('|')) {
        bodyRows.push(parseTableCells(lines[j]));
        j += 1;
      }
      nodes.push(
        <div key={`tbl-${i}`} className="my-2 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead className="bg-slate-50">
              <tr>
                {headers.map((h, hIdx) => (
                  <th
                    key={`th-${i}-${hIdx}`}
                    className="px-3 py-2 text-left font-semibold text-slate-700 whitespace-nowrap"
                  >
                    {renderInlineTokens(h, citationIds, onCitationClick, `th-${i}-${hIdx}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {bodyRows.map((row, rIdx) => (
                <tr key={`tr-${i}-${rIdx}`} className="hover:bg-slate-50/70">
                  {headers.map((_, cIdx) => (
                    <td key={`td-${i}-${rIdx}-${cIdx}`} className="px-3 py-1.5 text-slate-700">
                      {renderInlineTokens(
                        row[cIdx] ?? '',
                        citationIds,
                        onCitationClick,
                        `td-${i}-${rIdx}-${cIdx}`
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      i = j;
      continue;
    }

    if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
      nodes.push(<hr key={`hr-${i}`} className="my-2 border-slate-200" />);
      i += 1;
      continue;
    }

    const headingMatch = /^(#{1,4})\s+(.+)$/.exec(trimmed);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const body = headingMatch[2];
      const cls =
        level === 1
          ? 'text-base font-bold text-slate-900 pt-1'
          : level === 2
          ? 'text-sm font-bold text-slate-900 pt-1'
          : 'text-sm font-semibold text-slate-900 pt-1';
      nodes.push(
        <h4 key={`h-${i}`} className={cls}>
          {renderInlineTokens(body, citationIds, onCitationClick, `h-${i}`)}
        </h4>
      );
      i += 1;
      continue;
    }

    const bulletMatch = /^(?:[-*•])\s+(.+)$/.exec(trimmed);
    if (bulletMatch) {
      nodes.push(
        <div key={`li-${i}`} className="flex items-start space-x-2 pl-1">
          <span className="text-indigo-500 mt-0.5 text-xs font-bold">•</span>
          <span className="flex-1">
            {renderInlineTokens(bulletMatch[1], citationIds, onCitationClick, `li-${i}`)}
          </span>
        </div>
      );
      i += 1;
      continue;
    }

    const orderedMatch = /^(\d+)\.\s+(.+)$/.exec(trimmed);
    if (orderedMatch) {
      nodes.push(
        <div key={`ol-${i}`} className="flex items-start space-x-2 pl-1">
          <span className="text-indigo-600 font-semibold text-xs mt-0.5 min-w-[1.1rem]">
            {orderedMatch[1]}.
          </span>
          <span className="flex-1">
            {renderInlineTokens(orderedMatch[2], citationIds, onCitationClick, `ol-${i}`)}
          </span>
        </div>
      );
      i += 1;
      continue;
    }

    nodes.push(
      <p key={`p-${i}`}>
        {renderInlineTokens(trimmed, citationIds, onCitationClick, `p-${i}`)}
      </p>
    );
    i += 1;
  }

  return <div className="space-y-1.5 text-sm leading-relaxed text-slate-800">{nodes}</div>;
}

export const AssistantPage: React.FC<AssistantPageProps> = ({ onNavigate }) => {
  const [providers, setProviders] = useState<WebProviderStatus[]>([]);
  const [preferences, setPreferences] = useState<UserAiPreference | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<WebProviderId>('tavily');
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(true);
  const [includePersonalContext, setIncludePersonalContext] = useState<boolean>(true);
  const [readAloudEnabled, setReadAloudEnabled] = useState<boolean>(false);

  const [conversations, setConversations] = useState<AiConversationSummary[]>([]);
  const [activeConversation, setActiveConversation] = useState<AiConversationDetail | null>(null);
  const [editingTitleId, setEditingTitleId] = useState<string | null>(null);
  const [editingTitleValue, setEditingTitleValue] = useState<string>('');

  const [inputText, setInputText] = useState<string>('');
  const [loadingInit, setLoadingInit] = useState<boolean>(true);
  const [sending, setSending] = useState<boolean>(false);
  const [reindexing, setReindexing] = useState<boolean>(false);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [expandedEvidenceIds, setExpandedEvidenceIds] = useState<Record<string, boolean>>({});
  const [highlightedCitationKey, setHighlightedCitationKey] = useState<string | null>(null);
  const [openEvidenceMsgIds, setOpenEvidenceMsgIds] = useState<Record<string, boolean>>({});

  // Voice states
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isTranscribing, setIsTranscribing] = useState<boolean>(false);
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstanceLike | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaChunksRef = useRef<BlobPart[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const ttsWatchdogRef = useRef<number | null>(null);

  // Voice Expense Draft Modal states
  const [parsingDraft, setParsingDraft] = useState<boolean>(false);
  const [voiceDraft, setVoiceDraft] = useState<VoiceExpenseDraft | null>(null);
  const [draftAmount, setDraftAmount] = useState<string>('');
  const [draftType, setDraftType] = useState<'expense' | 'income'>('expense');
  const [draftAccountId, setDraftAccountId] = useState<string>('');
  const [draftCategoryId, setDraftCategoryId] = useState<string>('');
  const [draftDescription, setDraftDescription] = useState<string>('');
  const [draftMerchant, setDraftMerchant] = useState<string>('');
  const [draftDate, setDraftDate] = useState<string>('');
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [categories, setCategories] = useState<FinancialCategory[]>([]);
  const [savingDraft, setSavingDraft] = useState<boolean>(false);

  // Inline chat draft confirmation states (Bills / Transactions from chat)
  const [billDraftEdits, setBillDraftEdits] = useState<
    Record<
      string,
      {
        bill_name: string;
        bill_category: string;
        provider_name: string;
        expected_amount: string;
        due_date: string;
        bill_type: 'one_time' | 'recurring';
        frequency: 'weekly' | 'monthly' | 'quarterly' | 'half_yearly' | 'yearly' | 'custom';
      }
    >
  >({});
  const [savingMsgDraftId, setSavingMsgDraftId] = useState<string | null>(null);
  const [confirmedMsgDrafts, setConfirmedMsgDrafts] = useState<
    Record<string, { kind: 'bill' | 'transaction'; label: string }>
  >({});
  const [activeDraftMessageId, setActiveDraftMessageId] = useState<string | null>(null);

  const mediaRecorderSupported = useMemo(
    () =>
      typeof navigator !== 'undefined' &&
      Boolean(navigator.mediaDevices?.getUserMedia) &&
      typeof MediaRecorder !== 'undefined',
    []
  );
  const speechSupported = useMemo(
    () => mediaRecorderSupported || Boolean(getSpeechRecognitionCtor()),
    [mediaRecorderSupported]
  );
  const ttsSupported = useMemo(() => true, []);

  const loadBootstrap = useCallback(async () => {
    setLoadingInit(true);
    setError(null);
    try {
      const [provList, prefs, convList] = await Promise.all([
        assistantApi.listProviders(),
        assistantApi.getPreferences(),
        assistantApi.listConversations(),
      ]);
      setProviders(provList);
      setPreferences(prefs);
      setSelectedProvider(prefs.default_web_provider);
      setWebSearchEnabled(prefs.web_search_enabled);
      setReadAloudEnabled(prefs.voice_read_aloud_enabled);
      setConversations(convList);

      if (convList.length > 0) {
        const detail = await assistantApi.getConversation(convList[0].id);
        setActiveConversation(detail);
      }
    } catch (err) {
      setError((err as Error)?.message || 'Unable to load AI Assistant.');
    } finally {
      setLoadingInit(false);
    }
  }, []);

  useEffect(() => {
    loadBootstrap();
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try {
          mediaRecorderRef.current.stop();
        } catch {
          // ignore
        }
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (ttsWatchdogRef.current !== null) {
        window.clearTimeout(ttsWatchdogRef.current);
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        try {
          window.speechSynthesis.cancel();
        } catch {
          // ignore
        }
      }
    };
  }, [loadBootstrap]);

  const activeProviderObj = useMemo(
    () => providers.find((p) => p.provider === selectedProvider) || null,
    [providers, selectedProvider]
  );

  const handleSelectProvider = async (providerId: WebProviderId) => {
    setSelectedProvider(providerId);
    setError(null);
    try {
      const updated = await assistantApi.updatePreferences({
        default_web_provider: providerId,
      });
      setPreferences(updated);
      if (activeConversation) {
        await assistantApi.updateConversation(activeConversation.id, {
          preferred_provider: providerId,
        });
      }
    } catch (err) {
      setError((err as Error)?.message || 'Failed to save web research provider preference.');
    }
  };

  const handleToggleWebSearch = async (next: boolean) => {
    setWebSearchEnabled(next);
    try {
      const updated = await assistantApi.updatePreferences({ web_search_enabled: next });
      setPreferences(updated);
    } catch (err) {
      setError((err as Error)?.message || 'Failed to update web research preference.');
    }
  };

  const handleToggleReadAloud = async (next: boolean) => {
    setReadAloudEnabled(next);
    if (!next) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      setSpeakingMessageId(null);
    }
    try {
      const updated = await assistantApi.updatePreferences({ voice_read_aloud_enabled: next });
      setPreferences(updated);
    } catch (err) {
      setError((err as Error)?.message || 'Failed to update voice preference.');
    }
  };

  const handleCreateConversation = async () => {
    setError(null);
    try {
      const created = await assistantApi.createConversation({
        preferred_provider: selectedProvider,
        web_search_enabled: webSearchEnabled,
      });
      setConversations((prev) => [created, ...prev.filter((c) => c.id !== created.id)]);
      setActiveConversation(created);
    } catch (err) {
      setError((err as Error)?.message || 'Could not create conversation.');
    }
  };

  const handleSelectConversation = async (id: string) => {
    setError(null);
    try {
      const detail = await assistantApi.getConversation(id);
      setActiveConversation(detail);
      if (detail.preferred_provider) {
        setSelectedProvider(detail.preferred_provider);
      }
    } catch (err) {
      setError((err as Error)?.message || 'Could not load conversation.');
    }
  };

  const handleSaveTitle = async (id: string) => {
    const trimmed = editingTitleValue.trim();
    if (!trimmed) {
      setEditingTitleId(null);
      return;
    }
    try {
      const updated = await assistantApi.updateConversation(id, { title: trimmed });
      setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)));
      if (activeConversation?.id === id) {
        setActiveConversation({ ...activeConversation, title: updated.title });
      }
    } catch (err) {
      setError((err as Error)?.message || 'Could not rename conversation.');
    } finally {
      setEditingTitleId(null);
    }
  };

  const handleDeleteConversation = async (id: string) => {
    setError(null);
    try {
      await assistantApi.deleteConversation(id);
      const remaining = conversations.filter((c) => c.id !== id);
      setConversations(remaining);
      if (activeConversation?.id === id) {
        if (remaining.length > 0) {
          const detail = await assistantApi.getConversation(remaining[0].id);
          setActiveConversation(detail);
        } else {
          setActiveConversation(null);
        }
      }
    } catch (err) {
      setError((err as Error)?.message || 'Could not delete conversation.');
    }
  };

  const handleReindexRag = async () => {
    setReindexing(true);
    setError(null);
    setStatusNotice(null);
    try {
      const res = await assistantApi.reindexRag();
      setStatusNotice(
        `Document index refreshed: ${res.documents_scanned} document(s) scanned, ${res.chunks_indexed} chunk(s) indexed.`
      );
    } catch (err) {
      setError((err as Error)?.message || 'Failed to reindex uploaded documents.');
    } finally {
      setReindexing(false);
    }
  };

  const stopActivePlayback = useCallback(() => {
    if (ttsWatchdogRef.current !== null) {
      window.clearTimeout(ttsWatchdogRef.current);
      ttsWatchdogRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore
      }
    }
    setSpeakingMessageId(null);
  }, []);

  const playServerAudioTts = useCallback(
    async (cleanText: string, messageId: string) => {
      try {
        const wavBlob = await assistantApi.synthesizeSpeech(cleanText);
        if (audioUrlRef.current) {
          URL.revokeObjectURL(audioUrlRef.current);
        }
        const url = URL.createObjectURL(wavBlob);
        audioUrlRef.current = url;
        const audio = new Audio(url);
        audioRef.current = audio;
        setSpeakingMessageId(messageId);
        audio.onended = () => {
          setSpeakingMessageId(null);
          if (audioUrlRef.current === url) {
            URL.revokeObjectURL(url);
            audioUrlRef.current = null;
          }
        };
        audio.onerror = () => {
          setSpeakingMessageId(null);
          setVoiceNotice('Audio playback was blocked or failed in the browser.');
        };
        await audio.play();
      } catch (err) {
        setSpeakingMessageId(null);
        setVoiceNotice(
          (err as Error)?.message || 'Unable to play Read Aloud audio in this browser.'
        );
      }
    },
    []
  );

  const speakText = useCallback(
    (msg: AiMessage) => {
      const wasSpeakingSame = speakingMessageId === msg.id;
      stopActivePlayback();
      if (wasSpeakingSame) {
        return;
      }

      const cleanSpeech = cleanSpeechText(msg.content);
      if (!cleanSpeech) return;

      const hasBrowserSynth =
        typeof window !== 'undefined' &&
        'speechSynthesis' in window &&
        typeof SpeechSynthesisUtterance !== 'undefined';

      const voices = hasBrowserSynth ? window.speechSynthesis.getVoices() : [];
      if (!hasBrowserSynth || voices.length === 0) {
        // On Linux Chromium/Firefox, browser speechSynthesis often has no OS voices; play server WAV via <Audio>
        void playServerAudioTts(cleanSpeech, msg.id);
        return;
      }

      const preferredVoice =
        voices.find((v) => v.lang.toLowerCase().startsWith('en-in')) ||
        voices.find((v) => v.lang.toLowerCase().startsWith('en')) ||
        voices[0];

      let started = false;
      let fellBack = false;
      const triggerFallback = () => {
        if (fellBack) return;
        fellBack = true;
        try {
          window.speechSynthesis.cancel();
        } catch {
          // ignore
        }
        void playServerAudioTts(cleanSpeech, msg.id);
      };

      const utterance = new SpeechSynthesisUtterance(cleanSpeech);
      if (preferredVoice) {
        utterance.voice = preferredVoice;
        utterance.lang = preferredVoice.lang;
      } else {
        utterance.lang = 'en-IN';
      }
      utterance.onstart = () => {
        started = true;
        if (ttsWatchdogRef.current !== null) {
          window.clearTimeout(ttsWatchdogRef.current);
          ttsWatchdogRef.current = null;
        }
      };
      utterance.onend = () => {
        if (!fellBack) setSpeakingMessageId(null);
      };
      utterance.onerror = () => {
        if (!started) {
          triggerFallback();
        } else {
          setSpeakingMessageId(null);
        }
      };

      setSpeakingMessageId(msg.id);
      // Small delay avoids Chromium synchronous cancel+speak bug while falling back if speech-dispatcher hangs
      window.setTimeout(() => {
        if (fellBack) return;
        window.speechSynthesis.speak(utterance);
        ttsWatchdogRef.current = window.setTimeout(() => {
          if (!started && !fellBack) {
            triggerFallback();
          }
        }, 700);
      }, 40);
    },
    [playServerAudioTts, speakingMessageId, stopActivePlayback]
  );

  const handleSendMessage = async (promptOverride?: string) => {
    const text = (promptOverride ?? inputText).trim();
    if (!text || sending) return;

    setSending(true);
    setError(null);
    setStatusNotice(null);
    if (!promptOverride) {
      setInputText('');
    }

    try {
      let targetConv = activeConversation;
      if (!targetConv) {
        targetConv = await assistantApi.createConversation({
          preferred_provider: selectedProvider,
          web_search_enabled: webSearchEnabled,
        });
        setConversations((prev) => [targetConv!, ...prev]);
        setActiveConversation(targetConv);
      }

      const assistantReply = await assistantApi.sendMessage(targetConv.id, {
        content: text,
        web_search_enabled: webSearchEnabled,
        web_provider: selectedProvider,
        include_personal_context: includePersonalContext,
      });

      const refreshed = await assistantApi.getConversation(targetConv.id);
      setActiveConversation(refreshed);
      setConversations((prev) => [
        {
          id: refreshed.id,
          title: refreshed.title,
          preferred_provider: refreshed.preferred_provider,
          web_search_enabled: refreshed.web_search_enabled,
          is_archived: refreshed.is_archived,
          created_at: refreshed.created_at,
          updated_at: refreshed.updated_at,
        },
        ...prev.filter((c) => c.id !== refreshed.id),
      ]);
      setOpenEvidenceMsgIds((prev) => ({ ...prev, [assistantReply.id]: true }));

      if (readAloudEnabled && ttsSupported) {
        speakText(assistantReply);
      }
    } catch (err) {
      setError((err as Error)?.message || 'Failed to send assistant message.');
    } finally {
      setSending(false);
    }
  };

  const startBrowserSpeechRecognition = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setVoiceNotice(
        'Microphone capture unavailable in this browser. Type or paste your phrase and click "Draft Expense" or "Send".'
      );
      return;
    }
    try {
      const rec = new Ctor();
      rec.lang = 'en-IN';
      rec.interimResults = true;
      rec.continuous = false;
      rec.onresult = (event) => {
        const parts: string[] = [];
        for (let i = 0; i < event.results.length; i += 1) {
          parts.push(event.results[i][0].transcript);
        }
        setInputText(parts.join(' ').trim());
      };
      rec.onerror = (ev) => {
        setIsListening(false);
        if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
          setVoiceNotice(
            'Microphone permission was denied. Allow mic access or type your phrase into the input box.'
          );
        } else {
          setVoiceNotice(`Voice capture stopped (${ev.error}). You can edit the transcript manually.`);
        }
      };
      rec.onend = () => {
        setIsListening(false);
      };
      recognitionRef.current = rec;
      rec.start();
      setIsListening(true);
    } catch {
      setIsListening(false);
      setVoiceNotice('Could not start browser speech recognition. Type your phrase directly instead.');
    }
  }, []);

  const handleToggleVoiceMic = async () => {
    // Stop active recording / recognition
    if (isListening) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
        return;
      }
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        setIsListening(false);
        return;
      }
    }

    setVoiceNotice(null);

    // Primary cross-browser path on Linux/Firefox/Chromium: record microphone audio & transcribe via Whisper
    if (mediaRecorderSupported) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaStreamRef.current = stream;
        mediaChunksRef.current = [];

        const preferredMime =
          typeof MediaRecorder.isTypeSupported === 'function' &&
          MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : typeof MediaRecorder.isTypeSupported === 'function' &&
              MediaRecorder.isTypeSupported('audio/webm')
            ? 'audio/webm'
            : '';

        const recorder = preferredMime
          ? new MediaRecorder(stream, { mimeType: preferredMime })
          : new MediaRecorder(stream);

        recorder.ondataavailable = (ev) => {
          if (ev.data && ev.data.size > 0) {
            mediaChunksRef.current.push(ev.data);
          }
        };

        recorder.onstop = async () => {
          setIsListening(false);
          stream.getTracks().forEach((t) => t.stop());
          mediaStreamRef.current = null;
          mediaRecorderRef.current = null;

          const audioBlob = new Blob(mediaChunksRef.current, {
            type: recorder.mimeType || 'audio/webm',
          });
          mediaChunksRef.current = [];
          if (audioBlob.size < 64) {
            setVoiceNotice('No audio recorded. Speak after clicking Voice and click Stop Mic.');
            return;
          }

          setIsTranscribing(true);
          try {
            const res = await assistantApi.transcribeVoice(audioBlob);
            if (res.transcript) {
              setInputText((prev) =>
                prev.trim() ? `${prev.trim()} ${res.transcript}` : res.transcript
              );
            } else {
              setVoiceNotice('No speech detected in audio. Try speaking closer to the microphone.');
            }
          } catch (err) {
            const msg = (err as Error)?.message || '';
            if (msg.toLowerCase().includes('503') || msg.toLowerCase().includes('disabled')) {
              startBrowserSpeechRecognition();
            } else {
              setVoiceNotice(msg || 'Voice transcription failed. You can type your text directly.');
            }
          } finally {
            setIsTranscribing(false);
          }
        };

        mediaRecorderRef.current = recorder;
        recorder.start();
        setIsListening(true);
        return;
      } catch (err) {
        const errName = (err as DOMException)?.name || '';
        if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError') {
          setVoiceNotice(
            'Microphone permission was denied in the browser. Allow microphone access or type your phrase directly.'
          );
          return;
        }
        if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError') {
          setVoiceNotice(
            'No microphone device found on this system. You can still type or paste phrases and click "Draft Expense".'
          );
          return;
        }
        // Fallback to Web Speech API if MediaRecorder initialization threw another error
      }
    }

    startBrowserSpeechRecognition();
  };

  const handleOpenVoiceExpenseDraft = async () => {
    const text = inputText.trim();
    if (!text) {
      setVoiceNotice(
        'Speak with the mic or type a phrase like "Spent 450 rupees on Swiggy lunch today" first.'
      );
      return;
    }
    setParsingDraft(true);
    setError(null);
    try {
      const [draft, acctList, catList] = await Promise.all([
        assistantApi.parseVoiceExpense(text),
        accounts.length > 0 ? Promise.resolve(accounts) : financeApi.listAccounts(),
        categories.length > 0 ? Promise.resolve(categories) : financeApi.listCategories(),
      ]);
      setAccounts(acctList);
      setCategories(catList);
      setVoiceDraft(draft);
      setDraftType(draft.transaction_type);
      setDraftAmount(draft.amount != null ? String(draft.amount) : '');
      setDraftAccountId(draft.account_id || acctList[0]?.id || '');
      setDraftCategoryId(draft.category_id || '');
      setDraftDescription(draft.description || text);
      setDraftMerchant(draft.merchant_payee || '');
      setDraftDate(draft.transaction_date);
    } catch (err) {
      setError((err as Error)?.message || 'Failed to parse voice expense draft.');
    } finally {
      setParsingDraft(false);
    }
  };

  const handleConfirmVoiceExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draftAccountId || !draftAmount || Number(draftAmount) <= 0) {
      setError('Please select an account and enter a valid positive amount before saving.');
      return;
    }
    setSavingDraft(true);
    setError(null);
    try {
      await financeApi.createTransaction({
        account_id: draftAccountId,
        transaction_type: draftType,
        amount: draftAmount,
        currency: 'INR',
        category_id: draftCategoryId || null,
        description: draftDescription.trim() || 'Voice expense entry',
        merchant_payee: draftMerchant.trim() || null,
        transaction_date: draftDate,
        notes: voiceDraft?.transcript ? `Voice transcript: ${voiceDraft.transcript}` : null,
      });
      setVoiceDraft(null);
      setInputText('');
      if (activeDraftMessageId) {
        setConfirmedMsgDrafts((prev) => ({
          ...prev,
          [activeDraftMessageId]: {
            kind: 'transaction',
            label: `${draftDescription.trim() || 'Transaction'} (₹${draftAmount}) saved`,
          },
        }));
        setActiveDraftMessageId(null);
      }
      setStatusNotice('Confirmed transaction saved to your financial ledger.');
    } catch (err) {
      setError((err as Error)?.message || 'Unable to save confirmed transaction.');
    } finally {
      setSavingDraft(false);
    }
  };

  const handleConfirmChatBillDraft = async (msgId: string, base: ChatBillDraftAction) => {
    const edited = billDraftEdits[msgId];
    const billName = (edited?.bill_name ?? base.bill_name ?? '').trim();
    const billCategory = edited?.bill_category ?? base.bill_category ?? 'other';
    const providerName = (edited?.provider_name ?? base.provider_name ?? '').trim();
    const amt = edited?.expected_amount ?? (base.expected_amount != null ? String(base.expected_amount) : '');
    const dueDate = edited?.due_date ?? base.due_date;
    const billType = edited?.bill_type ?? base.bill_type ?? 'one_time';
    const freq = edited?.frequency ?? base.frequency ?? 'monthly';

    if (!billName || !amt || Number(amt) <= 0 || !dueDate) {
      setError('Please provide a valid bill name, positive amount, and due date before adding the bill.');
      return;
    }

    setSavingMsgDraftId(msgId);
    setError(null);
    try {
      const created = await billsApi.createBill({
        bill_name: billName,
        bill_category: billCategory,
        provider_name: providerName || null,
        bill_type: billType,
        frequency: billType === 'recurring' ? freq : null,
        is_variable_amount: false,
        expected_amount: Number(amt).toFixed(2),
        current_amount: Number(amt).toFixed(2),
        currency: 'INR',
        due_date: dueDate,
        description: base.description || `Added via AI Assistant: ${billName}`,
        reminder_enabled: true,
      });
      setConfirmedMsgDrafts((prev) => ({
        ...prev,
        [msgId]: {
          kind: 'bill',
          label: `${created.bill_name} (₹${amt}, due ${dueDate})`,
        },
      }));
      setStatusNotice(`Bill "${created.bill_name}" added cleanly to Bills.`);
    } catch (err) {
      setError((err as Error)?.message || 'Failed to add bill to Bills.');
    } finally {
      setSavingMsgDraftId(null);
    }
  };

  const handleOpenChatTransactionDraft = async (
    msgId: string,
    draft: ChatTransactionDraftAction
  ) => {
    setError(null);
    try {
      const [acctList, catList] = await Promise.all([
        accounts.length > 0 ? Promise.resolve(accounts) : financeApi.listAccounts(),
        categories.length > 0 ? Promise.resolve(categories) : financeApi.listCategories(),
      ]);
      setAccounts(acctList);
      setCategories(catList);
      setActiveDraftMessageId(msgId);
      setVoiceDraft({
        transcript: draft.transcript,
        transaction_type: draft.transaction_type || 'expense',
        amount: draft.amount ?? null,
        currency: draft.currency || 'INR',
        category_id: draft.category_id ?? null,
        category_name: draft.category_name ?? null,
        account_id: draft.account_id ?? null,
        account_name: draft.account_name ?? null,
        description: draft.description ?? null,
        merchant_payee: draft.merchant_payee ?? null,
        transaction_date: draft.transaction_date,
        missing_fields: draft.missing_fields || [],
        requires_user_confirmation: true,
      });
      setDraftType(draft.transaction_type || 'expense');
      setDraftAmount(draft.amount != null ? String(draft.amount) : '');
      setDraftAccountId(draft.account_id || acctList[0]?.id || '');
      setDraftCategoryId(draft.category_id || '');
      setDraftDescription(draft.description || draft.transcript || '');
      setDraftMerchant(draft.merchant_payee || '');
      setDraftDate(draft.transaction_date);
    } catch (err) {
      setError((err as Error)?.message || 'Unable to load accounts and categories for confirmation.');
    }
  };

  const renderDraftActionCard = (msg: AiMessage) => {
    if (!msg.draft_action || typeof msg.draft_action !== 'object') return null;
    const actionType = (msg.draft_action as { action_type?: string }).action_type;
    const confirmed = confirmedMsgDrafts[msg.id];

    if (confirmed) {
      return (
        <div className="mt-3 p-3 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-900 text-xs flex items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>
              <strong>Saved:</strong> {confirmed.label}
            </span>
          </div>
          <button
            type="button"
            onClick={() => onNavigate(confirmed.kind === 'bill' ? 'bills' : 'transactions')}
            className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold shrink-0"
          >
            Open {confirmed.kind === 'bill' ? 'Bills' : 'Transactions'} →
          </button>
        </div>
      );
    }

    if (actionType === 'create_bill') {
      const base = msg.draft_action as ChatBillDraftAction;
      const formVal = billDraftEdits[msg.id] || {
        bill_name: base.bill_name || '',
        bill_category: base.bill_category || 'electricity',
        provider_name: base.provider_name || '',
        expected_amount: base.expected_amount != null ? String(base.expected_amount) : '',
        due_date: base.due_date || '',
        bill_type: base.bill_type || 'one_time',
        frequency: base.frequency || 'monthly',
      };
      const updateField = (patch: Partial<typeof formVal>) => {
        setBillDraftEdits((prev) => ({
          ...prev,
          [msg.id]: { ...formVal, ...patch },
        }));
      };
      const isSaving = savingMsgDraftId === msg.id;

      return (
        <div className="mt-3 p-3.5 rounded-xl border border-indigo-200 bg-white text-xs space-y-3 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-indigo-900">
              Pending Bill Draft (Review &amp; Confirm to add to Bills)
            </span>
            <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 text-[11px]">
              Not saved yet
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
            <label className="block space-y-1">
              <span className="text-slate-600 font-medium">Bill Name</span>
              <input
                type="text"
                value={formVal.bill_name}
                onChange={(e) => updateField({ bill_name: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-slate-900"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-slate-600 font-medium">Amount (INR)</span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={formVal.expected_amount}
                onChange={(e) => updateField({ expected_amount: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-slate-900"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-slate-600 font-medium">Due Date</span>
              <input
                type="date"
                value={formVal.due_date}
                onChange={(e) => updateField({ due_date: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-slate-900"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-slate-600 font-medium">Category</span>
              <select
                value={formVal.bill_category}
                onChange={(e) => updateField({ bill_category: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-2 py-1.5 bg-white text-slate-900"
              >
                <option value="electricity">Electricity</option>
                <option value="water">Water</option>
                <option value="gas">Gas</option>
                <option value="internet">Internet / Broadband</option>
                <option value="mobile_postpaid">Mobile Postpaid</option>
                <option value="mobile_recharge">Mobile Recharge</option>
                <option value="rent">Rent</option>
                <option value="insurance">Insurance</option>
                <option value="loan_emi">Loan EMI</option>
                <option value="credit_card">Credit Card</option>
                <option value="maintenance">Maintenance</option>
                <option value="other">Other</option>
              </select>
            </label>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => onNavigate('bills')}
              className="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 font-medium"
            >
              Open Bills Page
            </button>
            <button
              type="button"
              disabled={isSaving}
              onClick={() => handleConfirmChatBillDraft(msg.id, base)}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold"
            >
              {isSaving ? 'Adding Bill...' : 'Confirm & Add Bill'}
            </button>
          </div>
        </div>
      );
    }

    if (actionType === 'create_transaction') {
      const txDraft = msg.draft_action as ChatTransactionDraftAction;
      return (
        <div className="mt-3 p-3 rounded-xl border border-indigo-200 bg-white text-xs flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="font-semibold text-indigo-900">
              Pending Transaction Draft ({txDraft.transaction_type}: ₹{txDraft.amount ?? '—'})
            </span>
            <p className="text-slate-600 mt-0.5">
              Select account &amp; confirm to record this in your ledger.
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleOpenChatTransactionDraft(msg.id, txDraft)}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
          >
            Review &amp; Save Expense
          </button>
        </div>
      );
    }

    return null;
  };

  const renderEvidenceSection = (msg: AiMessage) => {
    if (!msg.evidence_items || msg.evidence_items.length === 0) return null;
    const personalItems = msg.evidence_items.filter((e) => e.origin !== 'external_web');
    const webItems = msg.evidence_items.filter((e) => e.origin === 'external_web');
    const citationByEvidence = new Map(msg.citations.map((c) => [c.evidence_id, c.citation_id]));
    const isOpen = openEvidenceMsgIds[msg.id] ?? true;

    const renderCard = (item: EvidenceItem) => {
      const citNum = citationByEvidence.get(item.evidence_id);
      const cardKey = `${msg.id}:${citNum ?? item.evidence_id}`;
      const isHighlighted = highlightedCitationKey === cardKey;
      const expanded = expandedEvidenceIds[cardKey] ?? false;
      const safeUrl = getSafeExternalUrl(item.url);
      const pageNum =
        typeof item.meta?.page_number === 'number' ? item.meta.page_number : null;

      return (
        <div
          key={item.evidence_id}
          className={`p-3 rounded-lg border text-xs transition-colors ${
            isHighlighted
              ? 'border-indigo-400 bg-indigo-50/70'
              : 'border-slate-200 bg-slate-50/60'
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center flex-wrap gap-1.5 min-w-0">
              {citNum !== undefined && (
                <span className="px-1.5 py-0.5 rounded bg-indigo-600 text-white font-semibold text-[11px]">
                  [{citNum}]
                </span>
              )}
              <span className="font-semibold text-slate-900 truncate">{item.title}</span>
              {item.origin === 'personal_document' && (
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                    item.is_confirmed_source
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-amber-50 text-amber-800 border border-amber-200'
                  }`}
                >
                  {item.is_confirmed_source ? 'Confirmed Document' : 'OCR Extracted (Unreviewed)'}
                </span>
              )}
              {pageNum !== null && (
                <span className="px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px]">
                  Page {pageNum}
                </span>
              )}
              {item.provider && (
                <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 text-[10px] uppercase font-medium">
                  {item.provider}
                </span>
              )}
            </div>

            {safeUrl && (
              <a
                href={safeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center space-x-1 text-indigo-600 hover:text-indigo-800 font-medium shrink-0"
              >
                <span>{item.domain || 'Open Source'}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          <p className="mt-1.5 text-slate-700 leading-relaxed">{item.summary}</p>

          {(item.published_at || item.retrieved_at || item.source_reference) && (
            <div className="mt-1.5 flex flex-wrap gap-3 text-[11px] text-slate-500">
              {item.source_reference && <span>Source: {item.source_reference}</span>}
              {item.published_at && <span>Published: {item.published_at.slice(0, 10)}</span>}
              {item.retrieved_at && <span>Retrieved: {item.retrieved_at.slice(0, 10)}</span>}
            </div>
          )}

          {item.excerpt && (
            <div className="mt-1.5">
              <button
                type="button"
                onClick={() =>
                  setExpandedEvidenceIds((prev) => ({ ...prev, [cardKey]: !expanded }))
                }
                className="text-[11px] font-medium text-indigo-600 hover:underline"
              >
                {expanded ? 'Hide excerpt' : 'Show excerpt'}
              </button>
              {expanded && (
                <pre className="mt-1.5 p-2 rounded bg-white border border-slate-200 text-[11px] text-slate-700 whitespace-pre-wrap font-sans max-h-44 overflow-y-auto">
                  {item.excerpt}
                </pre>
              )}
            </div>
          )}
        </div>
      );
    };

    return (
      <div className="mt-3 pt-2.5 border-t border-slate-200/80">
        <button
          type="button"
          onClick={() =>
            setOpenEvidenceMsgIds((prev) => ({ ...prev, [msg.id]: !isOpen }))
          }
          className="text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center space-x-1.5"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          <span>
            {isOpen ? 'Hide' : 'Show'} Sources &amp; Evidence ({msg.evidence_items.length})
          </span>
        </button>

        {isOpen && (
          <div className="mt-2.5 space-y-3">
            {personalItems.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700 mb-1.5 flex items-center space-x-1">
                  <Database className="w-3 h-3" />
                  <span>Personal Financial Records &amp; Documents</span>
                </div>
                <div className="space-y-2">{personalItems.map(renderCard)}</div>
              </div>
            )}

            {webItems.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-blue-700 mb-1.5 flex items-center space-x-1">
                  <Globe className="w-3 h-3" />
                  <span>External Web Research Sources</span>
                </div>
                <div className="space-y-2">{webItems.map(renderCard)}</div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  if (loadingInit) {
    return (
      <div className="p-8 text-center text-slate-500 text-sm">
        Loading AI Personal Finance Assistant...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header & Controls Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                AI Personal Finance Assistant
              </h2>
              <p className="text-xs text-slate-500">
                Read-only personal ledger tools, Document RAG, multi-provider web research &amp; voice expense drafts
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* 3-Provider Selector */}
          <div
            className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1"
            role="group"
            aria-label="Web research provider selector"
          >
            {providers.map((p) => {
              const active = selectedProvider === p.provider;
              return (
                <button
                  key={p.provider}
                  type="button"
                  onClick={() => handleSelectProvider(p.provider)}
                  title={p.description}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors ${
                    active
                      ? 'bg-white text-indigo-700 shadow-xs border border-indigo-200'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <span>{p.display_name}</span>
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      p.configured ? 'bg-emerald-500' : 'bg-amber-400'
                    }`}
                    title={p.configured ? 'Configured' : 'Unavailable (key missing)'}
                  />
                </button>
              );
            })}
          </div>

          <label className="inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={webSearchEnabled}
              onChange={(e) => handleToggleWebSearch(e.target.checked)}
              className="rounded text-indigo-600"
            />
            <Globe className="w-3.5 h-3.5 text-blue-600" />
            <span>Web Research</span>
          </label>

          <label className="inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={includePersonalContext}
              onChange={(e) => setIncludePersonalContext(e.target.checked)}
              className="rounded text-indigo-600"
            />
            <Database className="w-3.5 h-3.5 text-emerald-600" />
            <span>Personal Context</span>
          </label>

          <label className="inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-xl border border-slate-200 bg-white text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={readAloudEnabled}
              onChange={(e) => handleToggleReadAloud(e.target.checked)}
              className="rounded text-indigo-600"
            />
            <Volume2 className="w-3.5 h-3.5 text-purple-600" />
            <span>Read Aloud</span>
          </label>

          <button
            type="button"
            onClick={handleReindexRag}
            disabled={reindexing}
            className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${reindexing ? 'animate-spin' : ''}`} />
            <span>Reindex Docs</span>
          </button>
        </div>
      </div>

      {/* Banners */}
      {webSearchEnabled && activeProviderObj && !activeProviderObj.configured && (
        <div className="p-3 rounded-xl border border-amber-300 bg-amber-50 text-amber-900 text-xs flex items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              Selected web provider <strong>{activeProviderObj.display_name}</strong> is not configured on the server. Live web searches using this provider will report an error instead of silently falling back to another provider.
            </span>
          </div>
          {preferences && (
            <span className="text-[11px] font-mono text-amber-700 shrink-0">
              Saved preference: {preferences.default_web_provider}
            </span>
          )}
        </div>
      )}

      {error && (
        <div className="p-3 rounded-xl border border-rose-200 bg-rose-50 text-rose-800 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button type="button" onClick={() => setError(null)} aria-label="Dismiss error">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {statusNotice && (
        <div className="p-3 rounded-xl border border-emerald-200 bg-emerald-50 text-emerald-800 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{statusNotice}</span>
          </div>
          <button type="button" onClick={() => setStatusNotice(null)} aria-label="Dismiss notice">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {voiceNotice && (
        <div className="p-3 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-900 text-xs flex items-center justify-between">
          <span>{voiceNotice}</span>
          <button type="button" onClick={() => setVoiceNotice(null)} aria-label="Dismiss voice notice">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Split Workspace: Conversation History + Chat Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Conversation Sidebar */}
        <aside className="lg:col-span-3 bg-white rounded-2xl border border-slate-200 p-3 flex flex-col max-h-[680px]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Conversations
            </h3>
            <button
              type="button"
              onClick={handleCreateConversation}
              className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Chat</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-1.5">
            {conversations.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500">
                No conversations yet. Start asking about your finances or Indian tax rules.
              </div>
            ) : (
              conversations.map((conv) => {
                const isActive = activeConversation?.id === conv.id;
                const isEditing = editingTitleId === conv.id;
                return (
                  <div
                    key={conv.id}
                    className={`group rounded-xl border p-2.5 transition-colors ${
                      isActive
                        ? 'border-indigo-300 bg-indigo-50/70'
                        : 'border-slate-100 hover:bg-slate-50'
                    }`}
                  >
                    {isEditing ? (
                      <div className="flex items-center space-x-1">
                        <input
                          type="text"
                          value={editingTitleValue}
                          onChange={(e) => setEditingTitleValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveTitle(conv.id);
                            if (e.key === 'Escape') setEditingTitleId(null);
                          }}
                          className="flex-1 px-2 py-1 text-xs border border-indigo-300 rounded bg-white"
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveTitle(conv.id)}
                          className="p-1 text-emerald-600"
                          aria-label="Save title"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-2">
                        <button
                          type="button"
                          onClick={() => handleSelectConversation(conv.id)}
                          className="text-left flex-1 min-w-0"
                        >
                          <div className="text-xs font-semibold text-slate-900 truncate">
                            {conv.title}
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            {formatDate(conv.updated_at)}
                          </div>
                        </button>
                        <div className="flex items-center space-x-1 shrink-0">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingTitleId(conv.id);
                              setEditingTitleValue(conv.title);
                            }}
                            className="p-1 text-slate-400 hover:text-indigo-600"
                            aria-label={`Rename ${conv.title}`}
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteConversation(conv.id)}
                            className="p-1 text-slate-400 hover:text-rose-600"
                            aria-label={`Delete ${conv.title}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          <div className="pt-3 mt-3 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
            <span>Read-only ledger safeguard</span>
            <button
              type="button"
              onClick={() => onNavigate('documents')}
              className="text-indigo-600 hover:underline inline-flex items-center space-x-1"
            >
              <FileText className="w-3 h-3" />
              <span>Documents</span>
            </button>
          </div>
        </aside>

        {/* Main Chat Area */}
        <section className="lg:col-span-9 bg-white rounded-2xl border border-slate-200 flex flex-col min-h-[600px] max-h-[680px]">
          {/* Message Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {!activeConversation || activeConversation.messages.length === 0 ? (
              <div className="py-10 px-4 max-w-2xl mx-auto text-center space-y-5">
                <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center mx-auto">
                  <Sparkles className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Ask anything about your finances, uploaded documents, or Indian rules
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Personal financial questions never leak your account balances to external search providers. Select Tavily, Firecrawl, or LangSearch above whenever you want live web citations.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                  {STARTER_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleSendMessage(prompt)}
                      className="p-3 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/40 text-xs text-slate-700 transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              activeConversation.messages.map((msg) => {
                const isUser = msg.role === 'user';
                const citIds = new Set(msg.citations.map((c) => c.citation_id));
                return (
                  <div
                    key={msg.id}
                    className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[90%] rounded-2xl p-4 ${
                        isUser
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-50 border border-slate-200 text-slate-900 w-full'
                      }`}
                    >
                      {isUser ? (
                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      ) : (
                        <>
                          {/* Metadata Header */}
                          <div className="flex items-center justify-between flex-wrap gap-2 mb-2 pb-2 border-b border-slate-200/70">
                            <div className="flex items-center flex-wrap gap-1.5 text-[11px]">
                              <span className="font-semibold text-slate-700">Assistant</span>
                              <span
                                className={`px-2 py-0.5 rounded-full font-medium ${
                                  msg.web_search_used
                                    ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                }`}
                              >
                                {msg.web_search_used
                                  ? `Web Research (${msg.provider_used || 'web'})`
                                  : 'Personal Records / Deterministic'}
                              </span>
                              {msg.llm_model && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 font-mono">
                                  {msg.llm_model}
                                </span>
                              )}
                              {msg.tools_invoked.map((tool) => (
                                <span
                                  key={tool}
                                  className="px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-600"
                                >
                                  {tool}
                                </span>
                              ))}
                            </div>

                            {ttsSupported && (
                              <button
                                type="button"
                                onClick={() => speakText(msg)}
                                className="inline-flex items-center space-x-1 px-2 py-1 rounded-lg bg-white border border-slate-200 hover:bg-slate-100 text-[11px] text-slate-700"
                              >
                                {speakingMessageId === msg.id ? (
                                  <>
                                    <VolumeX className="w-3.5 h-3.5 text-rose-600" />
                                    <span>Stop</span>
                                  </>
                                ) : (
                                  <>
                                    <Volume2 className="w-3.5 h-3.5 text-indigo-600" />
                                    <span>Read Aloud</span>
                                  </>
                                )}
                              </button>
                            )}
                          </div>

                          {msg.error_message && (
                            <div className="mb-2.5 p-2.5 rounded-lg bg-amber-50 border border-amber-300 text-amber-900 text-xs flex items-center space-x-2">
                              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                              <span>{msg.error_message}</span>
                            </div>
                          )}

                          {renderTextWithCitations(msg.content, citIds, (citNum) => {
                            setOpenEvidenceMsgIds((prev) => ({ ...prev, [msg.id]: true }));
                            setHighlightedCitationKey(`${msg.id}:${citNum}`);
                          })}

                          {renderDraftActionCard(msg)}

                          {renderEvidenceSection(msg)}
                        </>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Composer */}
          <div className="p-3 border-t border-slate-200 bg-slate-50/70 rounded-b-2xl space-y-2">
            <div className="flex flex-col sm:flex-row gap-2">
              <textarea
                rows={2}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Ask about spending, bills, forecasts, uploaded documents, RBI/tax rules — or speak/type an expense like 'Spent 450 on Swiggy lunch today'..."
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
              <div className="flex sm:flex-col gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => handleSendMessage()}
                  disabled={sending || !inputText.trim()}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center space-x-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{sending ? 'Thinking...' : 'Send'}</span>
                </button>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={handleToggleVoiceMic}
                    disabled={isTranscribing}
                    title={
                      speechSupported
                        ? 'Click to start speaking, then click Stop Mic to transcribe'
                        : 'Microphone unsupported in this browser — type transcript manually'
                    }
                    className={`px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center space-x-1 disabled:opacity-60 ${
                      isListening
                        ? 'bg-rose-600 text-white border-rose-700 animate-pulse'
                        : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
                    }`}
                  >
                    {isTranscribing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Transcribing...</span>
                      </>
                    ) : isListening ? (
                      <>
                        <MicOff className="w-3.5 h-3.5" />
                        <span>Stop Mic</span>
                      </>
                    ) : (
                      <>
                        <Mic className="w-3.5 h-3.5" />
                        <span>Voice</span>
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={handleOpenVoiceExpenseDraft}
                    disabled={parsingDraft || !inputText.trim()}
                    className="px-2.5 py-1.5 rounded-xl border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 disabled:opacity-50 text-emerald-800 text-xs font-medium"
                  >
                    {parsingDraft ? 'Parsing...' : 'Draft Expense'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Voice Expense Confirmation Modal */}
      {voiceDraft && (
        <div
          className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Review Voice Expense Draft"
        >
          <form
            onSubmit={handleConfirmVoiceExpense}
            className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-lg w-full p-5 space-y-4"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Review &amp; Confirm Voice Expense Draft
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Draft only — nothing has been recorded in your ledger yet.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setVoiceDraft(null)}
                className="p-1 text-slate-400 hover:text-slate-700"
                aria-label="Close draft modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700">
              <span className="font-semibold">Transcript:</span> {voiceDraft.transcript}
            </div>

            {voiceDraft.missing_fields.length > 0 && (
              <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                Please verify missing/ambiguous field(s):{' '}
                <strong>{voiceDraft.missing_fields.join(', ')}</strong>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <label className="block space-y-1">
                <span className="font-medium text-slate-700">Type</span>
                <select
                  value={draftType}
                  onChange={(e) => setDraftType(e.target.value as 'expense' | 'income')}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 bg-white"
                >
                  <option value="expense">Expense</option>
                  <option value="income">Income</option>
                </select>
              </label>

              <label className="block space-y-1">
                <span className="font-medium text-slate-700">Amount (INR)</span>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={draftAmount}
                  onChange={(e) => setDraftAmount(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                />
              </label>

              <label className="block space-y-1">
                <span className="font-medium text-slate-700">Account</span>
                <select
                  required
                  value={draftAccountId}
                  onChange={(e) => setDraftAccountId(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 bg-white"
                >
                  <option value="">Select account...</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block space-y-1">
                <span className="font-medium text-slate-700">Category</span>
                <select
                  value={draftCategoryId}
                  onChange={(e) => setDraftCategoryId(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 bg-white"
                >
                  <option value="">Uncategorized</option>
                  {categories
                    .filter((c) => c.category_type === draftType)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </label>

              <label className="block space-y-1">
                <span className="font-medium text-slate-700">Merchant / Payee</span>
                <input
                  type="text"
                  value={draftMerchant}
                  onChange={(e) => setDraftMerchant(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                />
              </label>

              <label className="block space-y-1">
                <span className="font-medium text-slate-700">Date</span>
                <input
                  type="date"
                  required
                  value={draftDate}
                  onChange={(e) => setDraftDate(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
                />
              </label>
            </div>

            <label className="block space-y-1 text-xs">
              <span className="font-medium text-slate-700">Description</span>
              <input
                type="text"
                required
                value={draftDescription}
                onChange={(e) => setDraftDescription(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5"
              />
            </label>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setVoiceDraft(null)}
                className="px-3.5 py-2 rounded-xl border border-slate-300 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingDraft}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold"
              >
                {savingDraft ? 'Saving...' : 'Confirm & Save Expense'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
