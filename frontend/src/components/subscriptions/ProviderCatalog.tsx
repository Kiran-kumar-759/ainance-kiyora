import React from 'react';
import {
  Cloud,
  Cpu,
  Dumbbell,
  Gamepad2,
  Layers,
  Music2,
  Newspaper,
  ShoppingBag,
  Tv,
} from 'lucide-react';
import { SubscriptionCategory } from '../../types/phase6';

export interface SubscriptionCategoryMeta {
  id: SubscriptionCategory;
  label: string;
  shortLabel: string;
  bgClass: string;
  textClass: string;
  borderClass: string;
  accentHex: string;
  Icon: React.ComponentType<{ className?: string }>;
}

export interface ProviderPreset {
  id: string;
  name: string;
  providerName: string;
  category: SubscriptionCategory;
  keywords: string[];
  suggestedPlan?: string;
  bgHex: string;
  textHex: string;
  accentHex: string;
  monogram: string;
  renderMark?: () => React.ReactNode;
}

export const SUBSCRIPTION_CATEGORY_CATALOG: SubscriptionCategoryMeta[] = [
  {
    id: 'ott_streaming',
    label: 'OTT & Video Streaming',
    shortLabel: 'OTT Streaming',
    bgClass: 'bg-rose-50',
    textClass: 'text-rose-700',
    borderClass: 'border-rose-200',
    accentHex: '#E11D48',
    Icon: Tv,
  },
  {
    id: 'music',
    label: 'Music & Audio',
    shortLabel: 'Music & Audio',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-700',
    borderClass: 'border-emerald-200',
    accentHex: '#059669',
    Icon: Music2,
  },
  {
    id: 'cloud_storage',
    label: 'Cloud Storage',
    shortLabel: 'Cloud Storage',
    bgClass: 'bg-sky-50',
    textClass: 'text-sky-700',
    borderClass: 'border-sky-200',
    accentHex: '#0284C7',
    Icon: Cloud,
  },
  {
    id: 'software_saas',
    label: 'Software & SaaS',
    shortLabel: 'Software & SaaS',
    bgClass: 'bg-indigo-50',
    textClass: 'text-indigo-700',
    borderClass: 'border-indigo-200',
    accentHex: '#4F46E5',
    Icon: Cpu,
  },
  {
    id: 'gaming',
    label: 'Gaming',
    shortLabel: 'Gaming',
    bgClass: 'bg-violet-50',
    textClass: 'text-violet-700',
    borderClass: 'border-violet-200',
    accentHex: '#7C3AED',
    Icon: Gamepad2,
  },
  {
    id: 'news_media',
    label: 'News & Digital Media',
    shortLabel: 'News & Media',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-200',
    accentHex: '#D97706',
    Icon: Newspaper,
  },
  {
    id: 'fitness',
    label: 'Fitness & Wellness',
    shortLabel: 'Fitness',
    bgClass: 'bg-lime-50',
    textClass: 'text-lime-800',
    borderClass: 'border-lime-200',
    accentHex: '#65A30D',
    Icon: Dumbbell,
  },
  {
    id: 'delivery_membership',
    label: 'Delivery Membership',
    shortLabel: 'Delivery',
    bgClass: 'bg-orange-50',
    textClass: 'text-orange-700',
    borderClass: 'border-orange-200',
    accentHex: '#EA580C',
    Icon: ShoppingBag,
  },
  {
    id: 'other',
    label: 'Other Subscription',
    shortLabel: 'Other',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-700',
    borderClass: 'border-slate-200',
    accentHex: '#475569',
    Icon: Layers,
  },
];

export const SUBSCRIPTION_PROVIDER_CATALOG: ProviderPreset[] = [
  // OTT & Video Streaming
  {
    id: 'netflix',
    name: 'Netflix',
    providerName: 'Netflix India',
    category: 'ott_streaming',
    keywords: ['netflix'],
    suggestedPlan: 'Standard HD',
    bgHex: '#141414',
    textHex: '#E50914',
    accentHex: '#E50914',
    monogram: 'N',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <path d="M9 6h5l8 24h-5z" fill="#B20710" />
        <path d="M9 6h5v24H9z" fill="#E50914" />
        <path d="M22 6h5v24h-5z" fill="#E50914" />
        <path d="M9 6h5l8 24h-5z" fill="#FF1F2B" opacity="0.9" />
      </svg>
    ),
  },
  {
    id: 'amazon_prime_video',
    name: 'Amazon Prime Video',
    providerName: 'Amazon Prime',
    category: 'ott_streaming',
    keywords: ['prime video', 'amazon prime', 'prime'],
    suggestedPlan: 'Prime Annual / Monthly',
    bgHex: '#0F172A',
    textHex: '#00A8E1',
    accentHex: '#00A8E1',
    monogram: 'PV',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <polygon points="14,10 26,17 14,24" fill="#00A8E1" />
        <path
          d="M8 26c5.5 3.4 13.5 3.4 19.5 0"
          fill="none"
          stroke="#38BDF8"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        <path d="M25.5 23.5l3 2.5-3.2 2" fill="none" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: 'jiohotstar',
    name: 'JioHotstar / Disney+',
    providerName: 'JioHotstar',
    category: 'ott_streaming',
    keywords: ['hotstar', 'jiohotstar', 'disney+'],
    suggestedPlan: 'Super / Premium',
    bgHex: '#0A1026',
    textHex: '#60A5FA',
    accentHex: '#3B82F6',
    monogram: 'JH',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <path d="M6 23c7-9 18-11 24-5" fill="none" stroke="#38BDF8" strokeWidth="2.4" strokeLinecap="round" />
        <path
          d="M18 8l2.2 5.4 5.8.4-4.4 3.7 1.4 5.6-5-3.1-5 3.1 1.4-5.6-4.4-3.7 5.8-.4z"
          fill="#EC4899"
        />
      </svg>
    ),
  },
  {
    id: 'sonyliv',
    name: 'SonyLIV',
    providerName: 'SonyLIV India',
    category: 'ott_streaming',
    keywords: ['sonyliv', 'sony liv'],
    suggestedPlan: 'LIV Premium',
    bgHex: '#1E1B4B',
    textHex: '#A78BFA',
    accentHex: '#8B5CF6',
    monogram: 'LIV',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <circle cx="18" cy="18" r="10" fill="none" stroke="#A78BFA" strokeWidth="3" />
        <polygon points="15,13 24,18 15,23" fill="#34D399" />
      </svg>
    ),
  },
  {
    id: 'zee5',
    name: 'ZEE5',
    providerName: 'ZEE Entertainment',
    category: 'ott_streaming',
    keywords: ['zee5', 'zee 5'],
    suggestedPlan: '4K / HD Premium',
    bgHex: '#2E1065',
    textHex: '#E9D5FF',
    accentHex: '#A855F7',
    monogram: 'Z5',
  },
  {
    id: 'youtube_premium',
    name: 'YouTube Premium',
    providerName: 'Google YouTube',
    category: 'ott_streaming',
    keywords: ['youtube premium', 'youtube', 'yt premium'],
    suggestedPlan: 'Individual / Family',
    bgHex: '#FF0000',
    textHex: '#FFFFFF',
    accentHex: '#FF0000',
    monogram: 'YT',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <rect x="5" y="9" width="26" height="18" rx="5" fill="#FFFFFF" />
        <polygon points="15,13 24,18 15,23" fill="#FF0000" />
      </svg>
    ),
  },
  {
    id: 'apple_tv',
    name: 'Apple TV+',
    providerName: 'Apple Services',
    category: 'ott_streaming',
    keywords: ['apple tv', 'tv+'],
    suggestedPlan: 'Apple TV+',
    bgHex: '#111827',
    textHex: '#F9FAFB',
    accentHex: '#6B7280',
    monogram: 'tv+',
  },
  {
    id: 'crunchyroll',
    name: 'Crunchyroll',
    providerName: 'Crunchyroll',
    category: 'ott_streaming',
    keywords: ['crunchyroll'],
    suggestedPlan: 'Mega Fan',
    bgHex: '#F47521',
    textHex: '#FFFFFF',
    accentHex: '#F47521',
    monogram: 'CR',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <circle cx="17" cy="19" r="9" fill="#FFFFFF" />
        <circle cx="20" cy="18" r="5" fill="#F47521" />
      </svg>
    ),
  },
  {
    id: 'jiocinema',
    name: 'JioCinema',
    providerName: 'Reliance Jio',
    category: 'ott_streaming',
    keywords: ['jiocinema', 'jio cinema'],
    suggestedPlan: 'Premium',
    bgHex: '#BE185D',
    textHex: '#FFFFFF',
    accentHex: '#EC4899',
    monogram: 'JC',
  },
  {
    id: 'sun_nxt',
    name: 'Sun NXT / Aha / Hoichoi',
    providerName: 'Regional OTT',
    category: 'ott_streaming',
    keywords: ['sun nxt', 'sunnxt', 'hoichoi', 'aha', 'lionsgate'],
    suggestedPlan: 'Annual HD',
    bgHex: '#B91C1C',
    textHex: '#FEF08A',
    accentHex: '#F59E0B',
    monogram: 'OTT',
  },

  // Music & Audio
  {
    id: 'spotify',
    name: 'Spotify',
    providerName: 'Spotify India',
    category: 'music',
    keywords: ['spotify'],
    suggestedPlan: 'Premium Individual',
    bgHex: '#1DB954',
    textHex: '#111827',
    accentHex: '#1DB954',
    monogram: 'SP',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <path d="M9 13c6-2 13-1.5 18 1.5" fill="none" stroke="#111827" strokeWidth="2.8" strokeLinecap="round" />
        <path d="M10.5 18c5-1.5 10.5-1 14.5 1.3" fill="none" stroke="#111827" strokeWidth="2.4" strokeLinecap="round" />
        <path d="M12 22.8c4-1 8-.6 11 1" fill="none" stroke="#111827" strokeWidth="2.1" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: 'apple_music',
    name: 'Apple Music',
    providerName: 'Apple Services',
    category: 'music',
    keywords: ['apple music'],
    suggestedPlan: 'Individual / Student',
    bgHex: '#FA243C',
    textHex: '#FFFFFF',
    accentHex: '#FA243C',
    monogram: 'AM',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <path
          d="M14 25V12l12-2.5V22"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="11.5" cy="25.5" r="2.8" fill="#FFFFFF" />
        <circle cx="23.5" cy="22.5" r="2.8" fill="#FFFFFF" />
      </svg>
    ),
  },
  {
    id: 'youtube_music',
    name: 'YouTube Music',
    providerName: 'Google YouTube',
    category: 'music',
    keywords: ['youtube music', 'yt music'],
    suggestedPlan: 'Music Premium',
    bgHex: '#DC2626',
    textHex: '#FFFFFF',
    accentHex: '#EF4444',
    monogram: 'YM',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <circle cx="18" cy="18" r="11" fill="#FFFFFF" />
        <circle cx="18" cy="18" r="8" fill="#DC2626" />
        <polygon points="16,14 23,18 16,22" fill="#FFFFFF" />
      </svg>
    ),
  },
  {
    id: 'jiosaavn',
    name: 'JioSaavn Pro',
    providerName: 'JioSaavn',
    category: 'music',
    keywords: ['jiosaavn', 'saavn'],
    suggestedPlan: 'Pro Monthly',
    bgHex: '#0F766E',
    textHex: '#5EEAD4',
    accentHex: '#2DD4BF',
    monogram: 'JS',
  },
  {
    id: 'gaana',
    name: 'Gaana Plus',
    providerName: 'Gaana',
    category: 'music',
    keywords: ['gaana'],
    suggestedPlan: 'Gaana Plus',
    bgHex: '#E72C30',
    textHex: '#FFFFFF',
    accentHex: '#E72C30',
    monogram: 'G+',
  },
  {
    id: 'audible',
    name: 'Audible',
    providerName: 'Amazon Audible',
    category: 'music',
    keywords: ['audible'],
    suggestedPlan: 'Monthly Credit',
    bgHex: '#F7991C',
    textHex: '#111827',
    accentHex: '#F7991C',
    monogram: 'AU',
  },

  // Cloud Storage
  {
    id: 'google_one',
    name: 'Google One',
    providerName: 'Google LLC',
    category: 'cloud_storage',
    keywords: ['google one', 'google drive', 'google storage'],
    suggestedPlan: '100 GB / 2 TB',
    bgHex: '#EFF6FF',
    textHex: '#1D4ED8',
    accentHex: '#2563EB',
    monogram: 'G1',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <path d="M18 8v20" stroke="#4285F4" strokeWidth="5" strokeLinecap="round" />
        <path d="M12 14l6-6" stroke="#EA4335" strokeWidth="5" strokeLinecap="round" />
        <circle cx="18" cy="24" r="3.5" fill="#34A853" />
      </svg>
    ),
  },
  {
    id: 'icloud',
    name: 'Apple iCloud+',
    providerName: 'Apple Services',
    category: 'cloud_storage',
    keywords: ['icloud', 'apple one'],
    suggestedPlan: '50 GB / 200 GB',
    bgHex: '#0284C7',
    textHex: '#FFFFFF',
    accentHex: '#38BDF8',
    monogram: 'iC+',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <path
          d="M11 25h14a5 5 0 0 0 1-9.9 6.5 6.5 0 0 0-12.4-1.5A4.5 4.5 0 0 0 11 25z"
          fill="#FFFFFF"
        />
      </svg>
    ),
  },
  {
    id: 'onedrive',
    name: 'Microsoft OneDrive',
    providerName: 'Microsoft',
    category: 'cloud_storage',
    keywords: ['onedrive'],
    suggestedPlan: '100 GB',
    bgHex: '#0078D4',
    textHex: '#FFFFFF',
    accentHex: '#0078D4',
    monogram: 'OD',
  },
  {
    id: 'dropbox',
    name: 'Dropbox',
    providerName: 'Dropbox Inc',
    category: 'cloud_storage',
    keywords: ['dropbox'],
    suggestedPlan: 'Plus 2 TB',
    bgHex: '#0061FF',
    textHex: '#FFFFFF',
    accentHex: '#0061FF',
    monogram: 'DB',
  },
  {
    id: 'digiboxx',
    name: 'DigiBoxx',
    providerName: 'DigiBoxx India',
    category: 'cloud_storage',
    keywords: ['digiboxx'],
    suggestedPlan: '100 GB',
    bgHex: '#1D4ED8',
    textHex: '#FFFFFF',
    accentHex: '#3B82F6',
    monogram: 'DX',
  },

  // Software & SaaS
  {
    id: 'chatgpt',
    name: 'ChatGPT Plus',
    providerName: 'OpenAI',
    category: 'software_saas',
    keywords: ['chatgpt', 'openai'],
    suggestedPlan: 'Plus / Pro',
    bgHex: '#10A37F',
    textHex: '#FFFFFF',
    accentHex: '#10A37F',
    monogram: 'GPT',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <circle cx="18" cy="18" r="9.5" fill="none" stroke="#FFFFFF" strokeWidth="2.4" strokeDasharray="5 2.5" />
        <circle cx="18" cy="18" r="3.5" fill="#FFFFFF" />
      </svg>
    ),
  },
  {
    id: 'claude_pro',
    name: 'Claude Pro',
    providerName: 'Anthropic',
    category: 'software_saas',
    keywords: ['claude', 'anthropic'],
    suggestedPlan: 'Pro',
    bgHex: '#CC785C',
    textHex: '#FFFFFF',
    accentHex: '#CC785C',
    monogram: 'CL',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <path
          d="M18 7v22M7 18h22M10.5 10.5l15 15M25.5 10.5l-15 15"
          stroke="#FFFFFF"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    id: 'microsoft_365',
    name: 'Microsoft 365',
    providerName: 'Microsoft',
    category: 'software_saas',
    keywords: ['microsoft 365', 'office 365', 'ms 365'],
    suggestedPlan: 'Personal / Family',
    bgHex: '#1E293B',
    textHex: '#F97316',
    accentHex: '#EA580C',
    monogram: '365',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <rect x="8" y="8" width="9" height="9" rx="1.5" fill="#F25022" />
        <rect x="19" y="8" width="9" height="9" rx="1.5" fill="#7FBA00" />
        <rect x="8" y="19" width="9" height="9" rx="1.5" fill="#00A4EF" />
        <rect x="19" y="19" width="9" height="9" rx="1.5" fill="#FFB900" />
      </svg>
    ),
  },
  {
    id: 'adobe_cc',
    name: 'Adobe Creative Cloud',
    providerName: 'Adobe',
    category: 'software_saas',
    keywords: ['adobe', 'photoshop', 'lightroom', 'creative cloud'],
    suggestedPlan: 'Photography / All Apps',
    bgHex: '#DC2626',
    textHex: '#FFFFFF',
    accentHex: '#EF4444',
    monogram: 'Cc',
  },
  {
    id: 'canva_pro',
    name: 'Canva Pro',
    providerName: 'Canva',
    category: 'software_saas',
    keywords: ['canva'],
    suggestedPlan: 'Pro',
    bgHex: '#0891B2',
    textHex: '#FFFFFF',
    accentHex: '#06B6D4',
    monogram: 'Cv',
  },
  {
    id: 'notion',
    name: 'Notion',
    providerName: 'Notion Labs',
    category: 'software_saas',
    keywords: ['notion'],
    suggestedPlan: 'Plus',
    bgHex: '#111827',
    textHex: '#FFFFFF',
    accentHex: '#374151',
    monogram: 'N',
  },
  {
    id: 'github_copilot',
    name: 'GitHub Copilot',
    providerName: 'GitHub',
    category: 'software_saas',
    keywords: ['github', 'copilot'],
    suggestedPlan: 'Pro',
    bgHex: '#1F2937',
    textHex: '#FFFFFF',
    accentHex: '#4B5563',
    monogram: 'GH',
  },

  // Gaming
  {
    id: 'ps_plus',
    name: 'PlayStation Plus',
    providerName: 'Sony PlayStation',
    category: 'gaming',
    keywords: ['playstation', 'ps plus', 'ps+'],
    suggestedPlan: 'Essential / Extra',
    bgHex: '#003791',
    textHex: '#FACC15',
    accentHex: '#2563EB',
    monogram: 'PS+',
  },
  {
    id: 'xbox_game_pass',
    name: 'Xbox Game Pass',
    providerName: 'Microsoft Xbox',
    category: 'gaming',
    keywords: ['xbox', 'game pass', 'gamepass'],
    suggestedPlan: 'Ultimate',
    bgHex: '#107C10',
    textHex: '#FFFFFF',
    accentHex: '#16A34A',
    monogram: 'XB',
  },
  {
    id: 'discord_nitro',
    name: 'Discord Nitro',
    providerName: 'Discord',
    category: 'gaming',
    keywords: ['discord', 'nitro'],
    suggestedPlan: 'Nitro',
    bgHex: '#5865F2',
    textHex: '#FFFFFF',
    accentHex: '#5865F2',
    monogram: 'DC',
  },
  {
    id: 'nintendo_online',
    name: 'Nintendo Switch Online',
    providerName: 'Nintendo',
    category: 'gaming',
    keywords: ['nintendo', 'switch'],
    suggestedPlan: 'Individual / Family',
    bgHex: '#E60012',
    textHex: '#FFFFFF',
    accentHex: '#E60012',
    monogram: 'NS',
  },
  {
    id: 'ea_play',
    name: 'EA Play',
    providerName: 'Electronic Arts',
    category: 'gaming',
    keywords: ['ea play'],
    suggestedPlan: 'Monthly',
    bgHex: '#1E293B',
    textHex: '#F87171',
    accentHex: '#EF4444',
    monogram: 'EA',
  },

  // News & Media
  {
    id: 'the_hindu',
    name: 'The Hindu',
    providerName: 'The Hindu Group',
    category: 'news_media',
    keywords: ['the hindu', 'hindu'],
    suggestedPlan: 'Digital All Access',
    bgHex: '#1E3A8A',
    textHex: '#FFFFFF',
    accentHex: '#1D4ED8',
    monogram: 'TH',
  },
  {
    id: 'et_prime',
    name: 'ET Prime',
    providerName: 'Economic Times',
    category: 'news_media',
    keywords: ['et prime', 'economic times'],
    suggestedPlan: 'Annual Digital',
    bgHex: '#92400E',
    textHex: '#FEF3C7',
    accentHex: '#D97706',
    monogram: 'ET',
  },
  {
    id: 'indian_express',
    name: 'The Indian Express',
    providerName: 'Indian Express',
    category: 'news_media',
    keywords: ['indian express'],
    suggestedPlan: 'Digital',
    bgHex: '#991B1B',
    textHex: '#FFFFFF',
    accentHex: '#DC2626',
    monogram: 'IE',
  },
  {
    id: 'medium',
    name: 'Medium',
    providerName: 'Medium',
    category: 'news_media',
    keywords: ['medium'],
    suggestedPlan: 'Member',
    bgHex: '#111827',
    textHex: '#FFFFFF',
    accentHex: '#111827',
    monogram: 'M',
    renderMark: () => (
      <svg viewBox="0 0 36 36" className="w-full h-full" aria-hidden="true">
        <ellipse cx="11.5" cy="18" rx="5.5" ry="6" fill="#FFFFFF" />
        <ellipse cx="21" cy="18" rx="3" ry="5.5" fill="#FFFFFF" />
        <ellipse cx="26.5" cy="18" rx="1.4" ry="5" fill="#FFFFFF" />
      </svg>
    ),
  },
  {
    id: 'substack',
    name: 'Substack',
    providerName: 'Substack',
    category: 'news_media',
    keywords: ['substack'],
    suggestedPlan: 'Newsletter',
    bgHex: '#FF6719',
    textHex: '#FFFFFF',
    accentHex: '#FF6719',
    monogram: 'SB',
  },

  // Fitness & Wellness
  {
    id: 'cult_fit',
    name: 'Cult.fit',
    providerName: 'Cure.fit',
    category: 'fitness',
    keywords: ['cult.fit', 'cultfit', 'cure.fit'],
    suggestedPlan: 'Cultpass Elite',
    bgHex: '#111827',
    textHex: '#F43F5E',
    accentHex: '#F43F5E',
    monogram: 'cult',
  },
  {
    id: 'healthifyme',
    name: 'HealthifyMe',
    providerName: 'HealthifyMe',
    category: 'fitness',
    keywords: ['healthify', 'healthifyme'],
    suggestedPlan: 'Pro Plan',
    bgHex: '#16A34A',
    textHex: '#FFFFFF',
    accentHex: '#22C55E',
    monogram: 'HM',
  },
  {
    id: 'strava',
    name: 'Strava',
    providerName: 'Strava',
    category: 'fitness',
    keywords: ['strava'],
    suggestedPlan: 'Subscriber',
    bgHex: '#FC4C02',
    textHex: '#FFFFFF',
    accentHex: '#FC4C02',
    monogram: 'ST',
  },
  {
    id: 'headspace',
    name: 'Headspace',
    providerName: 'Headspace',
    category: 'fitness',
    keywords: ['headspace', 'calm'],
    suggestedPlan: 'Annual Plus',
    bgHex: '#F97316',
    textHex: '#FFFFFF',
    accentHex: '#FB923C',
    monogram: 'HS',
  },

  // Delivery Membership
  {
    id: 'swiggy_one',
    name: 'Swiggy One',
    providerName: 'Swiggy',
    category: 'delivery_membership',
    keywords: ['swiggy'],
    suggestedPlan: 'Swiggy One 3M',
    bgHex: '#FC8019',
    textHex: '#FFFFFF',
    accentHex: '#FC8019',
    monogram: 'SW',
  },
  {
    id: 'zomato_gold',
    name: 'Zomato Gold',
    providerName: 'Zomato',
    category: 'delivery_membership',
    keywords: ['zomato'],
    suggestedPlan: 'Gold',
    bgHex: '#E23744',
    textHex: '#FFFFFF',
    accentHex: '#E23744',
    monogram: 'ZG',
  },
  {
    id: 'flipkart_vip',
    name: 'Flipkart VIP',
    providerName: 'Flipkart',
    category: 'delivery_membership',
    keywords: ['flipkart'],
    suggestedPlan: 'VIP Annual',
    bgHex: '#2874F0',
    textHex: '#FDE047',
    accentHex: '#2874F0',
    monogram: 'FK',
  },
  {
    id: 'zepto_pass',
    name: 'Zepto Pass / Blinkit',
    providerName: 'Zepto',
    category: 'delivery_membership',
    keywords: ['zepto', 'blinkit', 'bigbasket'],
    suggestedPlan: 'Delivery Pass',
    bgHex: '#5B21B6',
    textHex: '#FDE047',
    accentHex: '#7C3AED',
    monogram: 'ZP',
  },

  // Other Subscriptions
  {
    id: 'linkedin_premium',
    name: 'LinkedIn Premium',
    providerName: 'LinkedIn',
    category: 'other',
    keywords: ['linkedin'],
    suggestedPlan: 'Career / Business',
    bgHex: '#0A66C2',
    textHex: '#FFFFFF',
    accentHex: '#0A66C2',
    monogram: 'in',
  },
  {
    id: 'truecaller',
    name: 'Truecaller Premium',
    providerName: 'Truecaller',
    category: 'other',
    keywords: ['truecaller'],
    suggestedPlan: 'Gold / Family',
    bgHex: '#0087FF',
    textHex: '#FFFFFF',
    accentHex: '#0087FF',
    monogram: 'TC',
  },
];

export function getCategoryMeta(category: SubscriptionCategory): SubscriptionCategoryMeta {
  return (
    SUBSCRIPTION_CATEGORY_CATALOG.find((c) => c.id === category) ||
    SUBSCRIPTION_CATEGORY_CATALOG[SUBSCRIPTION_CATEGORY_CATALOG.length - 1]
  );
}

export function getProvidersForCategory(category: SubscriptionCategory): ProviderPreset[] {
  return SUBSCRIPTION_PROVIDER_CATALOG.filter((p) => p.category === category);
}

export function matchProviderPreset(
  subscriptionName?: string | null,
  providerName?: string | null
): ProviderPreset | null {
  const haystack = `${providerName || ''} ${subscriptionName || ''}`.trim().toLowerCase();
  if (!haystack) return null;
  for (const preset of SUBSCRIPTION_PROVIDER_CATALOG) {
    if (preset.keywords.some((kw) => haystack.includes(kw))) {
      return preset;
    }
  }
  return null;
}

function getInitials(label?: string | null): string {
  const words = (label || '')
    .trim()
    .split(/[\s\-_/]+/)
    .filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

interface ProviderLogoProps {
  category: SubscriptionCategory;
  subscriptionName?: string | null;
  providerName?: string | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const ProviderLogo: React.FC<ProviderLogoProps> = ({
  category,
  subscriptionName,
  providerName,
  size = 'md',
  className = '',
}) => {
  const preset = matchProviderPreset(subscriptionName, providerName);
  const catMeta = getCategoryMeta(category);
  const CategoryIcon = catMeta.Icon;

  const boxSize =
    size === 'sm'
      ? 'w-8 h-8 rounded-lg text-[10px]'
      : size === 'lg'
        ? 'w-12 h-12 rounded-xl text-sm'
        : 'w-10 h-10 rounded-xl text-xs';

  const cornerBadgeSize =
    size === 'sm' ? 'w-3.5 h-3.5 -bottom-1 -right-1' : 'w-4.5 h-4.5 -bottom-1 -right-1 p-0.5';

  if (preset) {
    return (
      <div
        className={`relative flex-shrink-0 flex items-center justify-center font-extrabold shadow-sm border border-black/10 select-none ${boxSize} ${className}`}
        style={{ backgroundColor: preset.bgHex, color: preset.textHex }}
        title={preset.name}
      >
        {preset.renderMark ? (
          <div className="w-[74%] h-[74%] flex items-center justify-center">
            {preset.renderMark()}
          </div>
        ) : (
          <span className="tracking-tight leading-none">{preset.monogram}</span>
        )}
        <span
          className={`absolute rounded-full bg-white border border-gray-200 shadow-xs flex items-center justify-center ${cornerBadgeSize}`}
          title={catMeta.label}
        >
          <CategoryIcon className="w-2.5 h-2.5 text-gray-700" />
        </span>
      </div>
    );
  }

  const label = providerName || subscriptionName;
  const initials = label ? getInitials(label) : null;

  return (
    <div
      className={`relative flex-shrink-0 flex items-center justify-center font-bold border shadow-xs select-none ${boxSize} ${catMeta.bgClass} ${catMeta.textClass} ${catMeta.borderClass} ${className}`}
      title={label || catMeta.label}
    >
      {initials ? (
        <span className="leading-none">{initials}</span>
      ) : (
        <CategoryIcon className="w-5 h-5" />
      )}
      {initials && (
        <span
          className={`absolute rounded-full bg-white border border-gray-200 shadow-xs flex items-center justify-center ${cornerBadgeSize}`}
          title={catMeta.label}
        >
          <CategoryIcon className="w-2.5 h-2.5 text-gray-700" />
        </span>
      )}
    </div>
  );
};

export const CategoryPictureBadge: React.FC<{ category: SubscriptionCategory }> = ({ category }) => {
  const meta = getCategoryMeta(category);
  const Icon = meta.Icon;
  return (
    <span
      className={`inline-flex items-center space-x-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${meta.bgClass} ${meta.textClass} ${meta.borderClass}`}
    >
      <Icon className="w-3 h-3 flex-shrink-0" />
      <span>{meta.shortLabel}</span>
    </span>
  );
};
