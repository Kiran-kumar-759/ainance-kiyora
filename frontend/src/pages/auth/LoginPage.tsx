import React from 'react';
import { AuthPortalPage } from './AuthPortalPage';
import { User } from '../../types/auth';

interface LoginPageProps {
  onNavigate: (view: string) => void;
  onSuccess?: (user?: User) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onNavigate, onSuccess }) => (
  <AuthPortalPage mode="login" onNavigate={onNavigate} onSuccess={onSuccess} />
);
