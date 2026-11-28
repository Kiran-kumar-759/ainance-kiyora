import React from 'react';
import { AuthPortalPage } from './AuthPortalPage';

interface RegisterPageProps {
  onNavigate: (view: string) => void;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ onNavigate }) => (
  <AuthPortalPage mode="register" onNavigate={onNavigate} />
);
