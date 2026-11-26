import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AssistantPage } from '../pages/assistant/AssistantPage';
import { assistantApi } from '../services/assistantApi';
import { financeApi } from '../services/financeApi';

vi.mock('../services/assistantApi', () => ({
  assistantApi: {
    listProviders: vi.fn(),
    getPreferences: vi.fn(),
    updatePreferences: vi.fn(),
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    getConversation: vi.fn(),
    updateConversation: vi.fn(),
    deleteConversation: vi.fn(),
    sendMessage: vi.fn(),
    reindexRag: vi.fn(),
    parseVoiceExpense: vi.fn(),
    transcribeVoice: vi.fn(),
    synthesizeSpeech: vi.fn(),
    confirmMessageAction: vi.fn(),
  },
}));

vi.mock('../services/financeApi', () => ({
  financeApi: {
    listAccounts: vi.fn(),
    listCategories: vi.fn(),
    createTransaction: vi.fn(),
  },
}));

const baseProviders = [
  {
    provider: 'langsearch' as const,
    display_name: 'LangSearch',
    description: 'LangSearch web search',
    configured: true,
    supports_full_text: true,
  },
  {
    provider: 'firecrawl' as const,
    display_name: 'Firecrawl',
    description: 'Firecrawl search + scrape',
    configured: false,
    supports_full_text: true,
  },
  {
    provider: 'tavily' as const,
    display_name: 'Tavily',
    description: 'Tavily AI search',
    configured: true,
    supports_full_text: true,
  },
];

const basePrefs = {
  default_web_provider: 'tavily' as const,
  web_search_enabled: true,
  voice_read_aloud_enabled: false,
  auto_execute_actions: false,
  updated_at: '2026-11-25T10:00:00Z',
};

const sampleConversation = {
  id: 'conv-1',
  title: 'RBI & Personal Spend',
  preferred_provider: 'tavily' as const,
  web_search_enabled: true,
  is_archived: false,
  created_at: '2026-11-25T10:00:00Z',
  updated_at: '2026-11-25T10:00:00Z',
  messages: [
    {
      id: 'm-1',
      conversation_id: 'conv-1',
      role: 'user' as const,
      content: 'Compare my spending with RBI UPI limits',
      web_search_used: false,
      tools_invoked: [],
      citations: [],
      evidence_items: [],
      status: 'completed',
      created_at: '2026-11-25T10:00:01Z',
    },
    {
      id: 'm-2',
      conversation_id: 'conv-1',
      role: 'assistant' as const,
      content:
        '## Spending Snapshot\n' +
        '| Metric | Amount |\n' +
        '|--------|--------|\n' +
        '| Food Spend | ₹1,250 [1] |\n' +
        '| RBI UPI Cap | ₹1,00,000 【2】 |\n' +
        '- Net impact tracked cleanly.',
      provider_used: 'tavily',
      llm_model: 'llama-3.3-70b-versatile',
      web_search_used: true,
      tools_invoked: ['get_spending_summary', 'web_research:tavily'],
      citations: [
        {
          citation_id: 1,
          evidence_id: 'spend_1',
          origin: 'personal_financial_record' as const,
          title: 'Monthly Spend Snapshot',
        },
        {
          citation_id: 2,
          evidence_id: 'web_1',
          origin: 'external_web' as const,
          title: 'NPCI UPI Guidelines',
          url: 'https://www.npci.org.in/upi-limits',
          domain: 'www.npci.org.in',
          provider: 'tavily',
        },
      ],
      evidence_items: [
        {
          evidence_id: 'spend_1',
          origin: 'personal_financial_record' as const,
          title: 'Monthly Spend Snapshot',
          summary: 'Expense total INR 1250.00 in Food & Dining.',
          source_reference: 'ledger_transactions',
          content_available: true,
          is_confirmed_source: true,
          meta: {},
        },
        {
          evidence_id: 'web_1',
          origin: 'external_web' as const,
          title: 'NPCI UPI Guidelines',
          summary: 'NPCI permits up to INR 1 lakh daily standard UPI transfer.',
          url: 'https://www.npci.org.in/upi-limits',
          domain: 'www.npci.org.in',
          provider: 'tavily',
          published_at: '2026-10-01',
          retrieved_at: '2026-11-25',
          excerpt: 'Official NPCI UPI daily cap details.',
          content_available: true,
          is_confirmed_source: false,
          meta: {},
        },
      ],
      status: 'completed',
      created_at: '2026-11-25T10:00:03Z',
    },
  ],
};

describe('AssistantPage (Phase 10)', () => {
  const mockNavigate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(assistantApi.listProviders).mockResolvedValue(baseProviders);
    vi.mocked(assistantApi.getPreferences).mockResolvedValue(basePrefs);
    vi.mocked(assistantApi.updatePreferences).mockResolvedValue({
      ...basePrefs,
      default_web_provider: 'firecrawl',
    });
    vi.mocked(assistantApi.listConversations).mockResolvedValue([sampleConversation]);
    vi.mocked(assistantApi.getConversation).mockResolvedValue(sampleConversation);
    vi.mocked(assistantApi.updateConversation).mockResolvedValue(sampleConversation);
  });

  it('renders providers, evidence distinction (personal vs external web), and unavailable banner on Firecrawl select', async () => {
    render(<AssistantPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('AI Personal Finance Assistant')).toBeInTheDocument();
    });

    expect(screen.getByText('Personal Financial Records & Documents')).toBeInTheDocument();
    expect(screen.getByText('External Web Research Sources')).toBeInTheDocument();
    expect(screen.getByText('www.npci.org.in')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Net impact tracked cleanly.')).toBeInTheDocument();
    expect(screen.queryByText(/•-/)).not.toBeInTheDocument();

    // Switch to unconfigured Firecrawl -> shows unavailable warning & persists preference
    fireEvent.click(screen.getByRole('button', { name: /Firecrawl/i }));

    await waitFor(() => {
      expect(assistantApi.updatePreferences).toHaveBeenCalledWith({
        default_web_provider: 'firecrawl',
      });
    });

    expect(
      screen.getByText(/Selected web provider/i)
    ).toBeInTheDocument();
  });

  it('handles voice draft parsing and requires explicit user confirmation before creating transaction', async () => {
    vi.mocked(assistantApi.parseVoiceExpense).mockResolvedValue({
      transcript: 'Spent 450 rupees on Swiggy lunch today',
      transaction_type: 'expense',
      amount: '450.00',
      currency: 'INR',
      category_id: 'cat-food',
      category_name: 'Food & Dining',
      account_id: 'acc-hdfc',
      account_name: 'HDFC Savings',
      description: 'Swiggy lunch',
      merchant_payee: 'Swiggy',
      transaction_date: '2026-11-25',
      missing_fields: [],
      requires_user_confirmation: true,
    });
    vi.mocked(financeApi.listAccounts).mockResolvedValue([
      {
        id: 'acc-hdfc',
        user_id: 'u-1',
        name: 'HDFC Savings',
        account_type: 'savings',
        opening_balance: '10000',
        current_balance: '10000',
        currency: 'INR',
        institution_name: 'HDFC',
        status: 'active',
        source: 'manual',
        created_at: '2026-11-01',
        updated_at: '2026-11-01',
      },
    ]);
    vi.mocked(financeApi.listCategories).mockResolvedValue([
      {
        id: 'cat-food',
        name: 'Food & Dining',
        category_type: 'expense',
        is_system: true,
        created_at: '2026-11-01',
      },
    ]);
    vi.mocked(financeApi.createTransaction).mockResolvedValue({
      id: 'tx-new',
      user_id: 'u-1',
      account_id: 'acc-hdfc',
      transaction_type: 'expense',
      amount: '450.00',
      currency: 'INR',
      description: 'Swiggy lunch',
      transaction_date: '2026-11-25',
      source: 'manual',
      created_at: '2026-11-25',
      updated_at: '2026-11-25',
    });

    render(<AssistantPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Ask about spending/i)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Ask about spending/i);
    fireEvent.change(input, { target: { value: 'Spent 450 rupees on Swiggy lunch today' } });

    fireEvent.click(screen.getByRole('button', { name: /Draft Expense/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /Review Voice Expense Draft/i })).toBeInTheDocument();
    });

    // Transaction NOT created until confirmed
    expect(financeApi.createTransaction).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Confirm & Save Expense/i }));

    await waitFor(() => {
      expect(financeApi.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          account_id: 'acc-hdfc',
          transaction_type: 'expense',
          amount: '450.00',
        })
      );
    });
  });

  it('sends a new message and supports creating/deleting conversations', async () => {
    vi.mocked(assistantApi.createConversation).mockResolvedValue({
      ...sampleConversation,
      id: 'conv-2',
      title: 'New Conversation',
      messages: [],
    });
    vi.mocked(assistantApi.sendMessage).mockResolvedValue(sampleConversation.messages[1]);

    render(<AssistantPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /New Chat/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /New Chat/i }));

    await waitFor(() => {
      expect(assistantApi.createConversation).toHaveBeenCalled();
    });

    const input = screen.getByPlaceholderText(/Ask about spending/i);
    fireEvent.change(input, { target: { value: 'How is my savings rate?' } });
    fireEvent.click(screen.getByRole('button', { name: /^Send$/i }));

    await waitFor(() => {
      expect(assistantApi.sendMessage).toHaveBeenCalledWith('conv-2', {
        content: 'How is my savings rate?',
        web_search_enabled: true,
        web_provider: 'tavily',
        include_personal_context: true,
        auto_execute: false,
      });
    });

    // Never auto-speak replies unless user explicitly clicks Read Aloud
    expect(assistantApi.synthesizeSpeech).not.toHaveBeenCalled();
  });

  it('plays Read Aloud via backend WAV fallback when browser speechSynthesis is absent', async () => {
    vi.mocked(assistantApi.synthesizeSpeech).mockResolvedValue(
      new Blob(['RIFF'], { type: 'audio/wav' })
    );
    const playSpy = vi.fn().mockResolvedValue(undefined);
    const pauseSpy = vi.fn();
    vi.stubGlobal(
      'Audio',
      vi.fn().mockImplementation(() => ({
        play: playSpy,
        pause: pauseSpy,
        onended: null,
        onerror: null,
      }))
    );
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => 'blob:mock-wav');
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }

    render(<AssistantPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Read Aloud/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Read Aloud/i }));

    await waitFor(() => {
      expect(assistantApi.synthesizeSpeech).toHaveBeenCalled();
      expect(playSpy).toHaveBeenCalled();
    });

    vi.unstubAllGlobals();
  });

  it('persists Bill Draft confirmation on server message and replaces button permanently with Saved state', async () => {
    const convWithBillDraft = {
      ...sampleConversation,
      messages: [
        {
          id: 'm-bill-1',
          conversation_id: 'conv-1',
          role: 'assistant' as const,
          content: "I've prepared an Electricity Bill draft for ₹1200.00.",
          web_search_used: false,
          tools_invoked: ['action_draft_parser'],
          citations: [],
          evidence_items: [],
          draft_action: {
            action_type: 'create_bill' as const,
            execution_status: 'pending_confirmation' as const,
            bill_name: 'Electricity Bill',
            bill_category: 'electricity',
            bill_type: 'one_time' as const,
            expected_amount: '1200.00',
            currency: 'INR',
            due_date: '2026-12-02',
            requires_user_confirmation: true,
          },
          status: 'completed',
          created_at: '2026-11-25T10:05:00Z',
        },
      ],
    };
    vi.mocked(assistantApi.getConversation).mockResolvedValue(convWithBillDraft);
    vi.mocked(assistantApi.confirmMessageAction).mockResolvedValue({
      ...convWithBillDraft.messages[0],
      draft_action: {
        ...convWithBillDraft.messages[0].draft_action,
        execution_status: 'executed' as const,
        execution_mode: 'confirmed' as const,
        executed_label: 'Electricity Bill (₹1200.00, due 2026-12-02)',
        requires_user_confirmation: false,
      },
    });

    render(<AssistantPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Confirm & Add Bill/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Confirm & Add Bill/i }));

    await waitFor(() => {
      expect(assistantApi.confirmMessageAction).toHaveBeenCalledWith(
        'm-bill-1',
        expect.objectContaining({
          bill_name: 'Electricity Bill',
          bill_category: 'electricity',
          expected_amount: '1200.00',
          due_date: '2026-12-02',
        })
      );
    });

    expect(screen.queryByRole('button', { name: /Confirm & Add Bill/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open Bills →/i })).toBeInTheDocument();
  });

  it('toggles Auto-Execute Actions on and renders Auto-Executed & Saved subscription status', async () => {
    vi.mocked(assistantApi.updatePreferences).mockResolvedValue({
      ...basePrefs,
      auto_execute_actions: true,
    });
    const convWithAutoSub = {
      ...sampleConversation,
      messages: [
        {
          id: 'm-sub-1',
          conversation_id: 'conv-1',
          role: 'assistant' as const,
          content: 'Done — Auto-Execute Actions added Netflix.',
          web_search_used: false,
          tools_invoked: ['action_draft_parser', 'action_auto_executor'],
          citations: [],
          evidence_items: [],
          draft_action: {
            action_type: 'create_subscription' as const,
            execution_status: 'executed' as const,
            execution_mode: 'auto' as const,
            executed_label: 'Netflix (₹649.00/monthly)',
            subscription_name: 'Netflix',
            category: 'ott_streaming',
            amount: '649.00',
            currency: 'INR',
            billing_frequency: 'monthly' as const,
            next_renewal_date: '2026-12-25',
            requires_user_confirmation: false,
          },
          status: 'completed',
          created_at: '2026-11-25T10:10:00Z',
        },
      ],
    };
    vi.mocked(assistantApi.getConversation).mockResolvedValue(convWithAutoSub);

    render(<AssistantPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Auto-Execute Actions/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/Auto-Execute Actions/i));

    await waitFor(() => {
      expect(assistantApi.updatePreferences).toHaveBeenCalledWith({
        auto_execute_actions: true,
      });
    });

    expect(screen.getByText(/Auto-Executed & Saved:/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open Subscriptions →/i })).toBeInTheDocument();
  });

  it('records audio via MediaRecorder, transcribes via Whisper API cleanly, and persists Auto-Speak toggle', async () => {
    vi.mocked(assistantApi.transcribeVoice).mockResolvedValue({
      transcript: 'Can I buy a Sony TV?',
      provider: 'groq:whisper-large-v3-turbo',
    });
    vi.mocked(assistantApi.updatePreferences).mockResolvedValue({
      ...basePrefs,
      voice_read_aloud_enabled: true,
    });

    const stopTrackSpy = vi.fn();
    vi.stubGlobal('navigator', {
      ...navigator,
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: stopTrackSpy }],
        }),
      },
    });

    class MockMediaRecorder {
      static isTypeSupported = vi.fn(() => true);
      state = 'inactive';
      mimeType = 'audio/webm;codecs=opus';
      ondataavailable: ((ev: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = 'recording';
        if (this.ondataavailable) {
          this.ondataavailable({
            data: new Blob([new Uint8Array(256)], { type: 'audio/webm' }),
          });
        }
      }
      requestData() {
        // no-op
      }
      stop() {
        this.state = 'inactive';
        if (this.onstop) this.onstop();
      }
    }
    vi.stubGlobal('MediaRecorder', MockMediaRecorder);

    render(<AssistantPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Voice$/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /^Voice$/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Stop Mic/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Stop Mic/i }));
    await waitFor(() => {
      expect(assistantApi.transcribeVoice).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Ask about spending/i)).toHaveValue(
        'Can I buy a Sony TV?'
      );
    });
    expect(stopTrackSpy).toHaveBeenCalled();

    fireEvent.click(screen.getByLabelText(/Auto-Speak/i));
    await waitFor(() => {
      expect(assistantApi.updatePreferences).toHaveBeenCalledWith({
        voice_read_aloud_enabled: true,
      });
    });

    vi.unstubAllGlobals();
  });

  it('encodes 16 kHz RIFF WAV audio cleanly from PCM float samples for Groq Whisper', async () => {
    const { encodePcmWav } = await import('../lib/voiceRecorder');
    const samples = new Float32Array(4800); // 100ms @ 48 kHz
    samples[10] = 0.25;
    const wav = encodePcmWav([samples], 48000);
    expect(wav.type).toBe('audio/wav');
    expect(wav.size).toBe(44 + 1600 * 2);
  });
});
