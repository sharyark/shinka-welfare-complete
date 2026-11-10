import { Stack } from 'expo-router';

import { useAuth } from '@/auth/AuthContext';
import { useLang } from '@/i18n';
import { API_URL } from '@/api';
import { Button, Muted, Screen, Title } from '@/ui';

/** Finance Secretary and Auditor work in the admin panel, not the app. */
export default function Office() {
  const { t } = useLang();
  const { logout } = useAuth();
  return (
    <Screen>
      <Stack.Screen options={{ title: t('appName') }} />
      <Title>{t('officeOnly')}</Title>
      <Muted>{`${API_URL}/admin/`}</Muted>
      <Button label={t('logout')} kind="secondary" onPress={logout} />
    </Screen>
  );
}
