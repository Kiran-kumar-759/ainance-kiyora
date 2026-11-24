import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { App } from '../app/App';
import { apiClient } from '../services/apiClient';

vi.mock('../services/apiClient', () => ({
  apiClient: {
    getHealth: vi.fn(),
    getReadiness: vi.fn(),
    getPlatformInfo: vi.fn(),
  },
}));

describe('Frontend Application Shell and System Status View', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    // Return pending promise
    vi.mocked(apiClient.getHealth).mockReturnValue(new Promise(() => {}));
    vi.mocked(apiClient.getReadiness).mockReturnValue(new Promise(() => {}));
    vi.mocked(apiClient.getPlatformInfo).mockReturnValue(new Promise(() => {}));

    render(<App />);

    expect(screen.getAllByText(/AI Personal Finance Manager/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/System Foundation/i)).toBeInTheDocument();
  });

  it('renders successful backend and database connected state', async () => {
    vi.mocked(apiClient.getHealth).mockResolvedValue({
      status: 'ok',
      app: 'AI Personal Finance Manager',
      environment: 'development',
      version: '0.1.0',
      timestamp: '2026-11-24T12:00:00Z',
    });

    vi.mocked(apiClient.getReadiness).mockResolvedValue({
      status: 'ready',
      database: {
        ready: true,
        status: 'connected',
        database_name: 'pfm_dev',
        latency_ms: 1.45,
        error: null,
      },
      environment: 'development',
      timestamp: '2026-11-24T12:00:00Z',
    });

    vi.mocked(apiClient.getPlatformInfo).mockResolvedValue({
      app_name: 'AI Personal Finance Manager',
      version: '0.1.0',
      phase: 'Phase 0: Product Foundation + Functional Demo UI',
      target_market: 'India',
      primary_currency: 'INR',
      fiscal_year_cycle: 'April - March',
      environment: 'development',
      database_connected: true,
      database_name: 'pfm_dev',
      settings_count: 1,
      timestamp: '2026-11-24T12:00:00Z',
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Ready \(1.45 ms\)/i)).toBeInTheDocument();
      expect(screen.getByText(/INR \(Indian Rupee\)/i)).toBeInTheDocument();
      expect(screen.getByText(/April 1 – March 31/i)).toBeInTheDocument();
    });
  });

  it('displays honest error state when backend is unreachable', async () => {
    vi.mocked(apiClient.getHealth).mockRejectedValue(
      new Error('Failed to fetch from http://127.0.0.1:8000')
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Backend API Unreachable/i)).toBeInTheDocument();
      expect(screen.getByText(/The React frontend could not connect to FastAPI/i)).toBeInTheDocument();
    });
  });

  it('displays degraded state when PostgreSQL is disconnected', async () => {
    vi.mocked(apiClient.getHealth).mockResolvedValue({
      status: 'ok',
      app: 'AI Personal Finance Manager',
      environment: 'development',
      version: '0.1.0',
      timestamp: '2026-11-24T12:00:00Z',
    });

    vi.mocked(apiClient.getReadiness).mockResolvedValue({
      status: 'degraded',
      database: {
        ready: false,
        status: 'disconnected',
        database_name: null,
        latency_ms: 22.1,
        error: 'Database service is unavailable or unreachable',
      },
      environment: 'development',
      timestamp: '2026-11-24T12:00:00Z',
    });

    vi.mocked(apiClient.getPlatformInfo).mockResolvedValue({
      app_name: 'AI Personal Finance Manager',
      version: '0.1.0',
      phase: 'Phase 0: Product Foundation + Functional Demo UI',
      target_market: 'India',
      primary_currency: 'INR',
      fiscal_year_cycle: 'April - March',
      environment: 'development',
      database_connected: false,
      database_name: null,
      settings_count: 0,
      timestamp: '2026-11-24T12:00:00Z',
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Database Degraded \/ Unreachable/i)).toBeInTheDocument();
      expect(screen.getByText(/FastAPI is responding, but the PostgreSQL readiness check failed/i)).toBeInTheDocument();
    });
  });
});
