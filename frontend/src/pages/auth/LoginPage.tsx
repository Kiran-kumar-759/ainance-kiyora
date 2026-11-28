import React from 'react';
import { AuthPortalPage } from './AuthPortalPage';

interface LoginPageProps {
  onNavigate: (view: string) => void;
  onSuccess?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onNavigate, onSuccess }) => (
  <AuthPortalPage mode="login" onNavigate={onNavigate} onSuccess={onSuccess} />
);
