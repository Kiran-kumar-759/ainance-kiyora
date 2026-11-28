import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LoginPage } from '../pages/auth/LoginPage';
import { RegisterPage } from '../pages/auth/RegisterPage';
import { ForgotPasswordPage } from '../pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/auth/ResetPasswordPage';
import { VerifyEmailPage } from '../pages/auth/VerifyEmailPage';
import { OnboardingWizard } from '../pages/onboarding/OnboardingWizard';
import { PreferencesPage } from '../pages/settings/PreferencesPage';
import { SessionsPage } from '../pages/settings/SessionsPage';
import { AuthProvider } from '../context/AuthContext';
import { authApi } from '../services/authApi';

vi.mock('../services/authApi', () => ({
  authApi: {
    getCsrf: vi.fn().mockResolvedValue('test-csrf-token'),
    getMe: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    logoutAll: vi.fn(),
    listSessions: vi.fn(),
    revokeSession: vi.fn(),
    verifyEmail: vi.fn(),
    resendVerification: vi.fn(),
    forgotPassword: vi.fn(),
    resetPassword: vi.fn(),
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    getPreferences: vi.fn(),
    updatePreferences: vi.fn(),
    getOnboarding: vi.fn(),
    updateOnboarding: vi.fn(),
    completeOnboarding: vi.fn(),
    skipOnboarding: vi.fn(),
  },
}));

describe('Frontend Authentication and User Management Pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(authApi.getCsrf).mockResolvedValue('test-csrf-token');
    vi.mocked(authApi.getMe).mockRejectedValue(new Error('Unauthorized'));
  });

  it('renders login form and handles invalid credentials', async () => {
    const onNavigate = vi.fn();
    vi.mocked(authApi.login).mockRejectedValue(new Error('Invalid email or password.'));

    render(
      <AuthProvider>
        <LoginPage onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(screen.getByText(/Welcome Back/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Enter your email address/i), { target: { value: 'user@example.in' } });
    fireEvent.change(screen.getByPlaceholderText(/Enter your password/i), { target: { value: 'wrongpass' } });

    fireEvent.click(screen.getByRole('button', { name: /Sign In/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invalid email or password/i)).toBeInTheDocument();
    });
  });

  it('renders registration form and validates first name, last name, email, and min 8-char password', async () => {
    const onNavigate = vi.fn();
    render(
      <AuthProvider>
        <RegisterPage onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(screen.getByRole('heading', { name: /Create Account/i })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/Enter your first name/i), { target: { value: 'Aarav' } });
    fireEvent.change(screen.getByPlaceholderText(/Enter your last name/i), { target: { value: 'Sharma' } });
    fireEvent.change(screen.getByPlaceholderText(/Enter your email address/i), { target: { value: 'test@example.in' } });
    fireEvent.change(screen.getByPlaceholderText(/Create a password/i), { target: { value: 'short' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Account/i }));

    await waitFor(() => {
      expect(screen.getByText(/Use at least 8 characters/i)).toBeInTheDocument();
    });
  });

  it('renders forgot password and calls API on submit', async () => {
    const onNavigate = vi.fn();
    vi.mocked(authApi.forgotPassword).mockResolvedValue({ message: 'Reset instructions sent.' });

    render(
      <AuthProvider>
        <ForgotPasswordPage onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(screen.getByText(/Reset Password/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/name@example.in/i), { target: { value: 'forgot@example.in' } });
    fireEvent.click(screen.getByRole('button', { name: /Send Reset Link/i }));

    await waitFor(() => {
      expect(authApi.forgotPassword).toHaveBeenCalledWith('forgot@example.in');
      expect(screen.getByText(/Check your email/i)).toBeInTheDocument();
    });
  });

  it('renders reset password page and validates password matching', async () => {
    const onNavigate = vi.fn();
    render(
      <AuthProvider>
        <ResetPasswordPage token="test-reset-token" onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(screen.getByText(/Set New Password/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Minimum 8 characters/i), { target: { value: 'newpassword123' } });
    fireEvent.change(screen.getByPlaceholderText(/Re-enter password/i), { target: { value: 'differentpassword' } });
    fireEvent.click(screen.getByRole('button', { name: /Update Password/i }));

    await waitFor(() => {
      expect(screen.getByText(/Passwords do not match/i)).toBeInTheDocument();
    });
  });

  it('renders verify email page and allows manual token verification', async () => {
    const onNavigate = vi.fn();
    vi.mocked(authApi.verifyEmail).mockResolvedValue({
      message: 'Email verified successfully!',
      user: {
        id: '123',
        email: 'v@example.com',
        full_name: 'Verified User',
        is_active: true,
        is_email_verified: true,
        onboarding_completed: true,
        created_at: '2026-11-24T00:00:00Z',
        last_login_at: null,
      },
      email_delivery_status: 'verified',
    });

    render(
      <AuthProvider>
        <VerifyEmailPage onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(screen.getByText(/Verify Your Email/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Paste the token from your email/i), {
      target: { value: 'sample-verify-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Verify Token/i }));

    await waitFor(() => {
      expect(authApi.verifyEmail).toHaveBeenCalledWith('sample-verify-token');
      expect(screen.getByText(/Email Verified!/i)).toBeInTheDocument();
    });
  });

  it('renders onboarding wizard and navigates through steps', async () => {
    const onComplete = vi.fn();
    vi.mocked(authApi.updateOnboarding).mockResolvedValue({
      onboarding_completed: false,
      is_email_verified: false,
      full_name: 'Test',
      preferences: {
        preferred_currency: 'INR',
        locale: 'en-IN',
        timezone: 'Asia/Kolkata',
        date_format: 'DD/MM/YYYY',
        notification_preferences: {},
      },
    });

    render(
      <AuthProvider>
        <OnboardingWizard onComplete={onComplete} />
      </AuthProvider>
    );

    expect(screen.getByText(/Welcome to AI Personal Finance Manager/i)).toBeInTheDocument();
    const continueBtn = screen.getByRole('button', { name: /Continue/i });
    fireEvent.click(continueBtn);

    await waitFor(() => {
      expect(screen.getByText(/Confirm Your Profile/i)).toBeInTheDocument();
    });
  });

  it('renders sessions page and lists active sessions', async () => {
    vi.mocked(authApi.listSessions).mockResolvedValue([
      {
        id: 'sess-1',
        created_at: '2026-11-24T10:00:00Z',
        expires_at: '2026-12-01T10:00:00Z',
        last_used_at: '2026-11-24T10:00:00Z',
        user_agent: 'Mozilla/5.0 Linux Chrome',
        ip_address: '127.0.0.1',
        is_current: true,
      },
    ]);

    render(
      <AuthProvider>
        <SessionsPage />
      </AuthProvider>
    );

    expect(screen.getByText(/Active Sessions & Security/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/Current Session/i)).toBeInTheDocument();
      expect(screen.getByText(/IP: 127.0.0.1/i)).toBeInTheDocument();
    });
  });

  it('renders preferences page with Indian defaults', async () => {
    render(
      <AuthProvider>
        <PreferencesPage />
      </AuthProvider>
    );

    expect(screen.getByText(/Regional & System Preferences/i)).toBeInTheDocument();
    expect(screen.getByText(/Preferred Currency/i)).toBeInTheDocument();
    expect(screen.getByText(/Asia\/Kolkata/i)).toBeInTheDocument();
  });
});
