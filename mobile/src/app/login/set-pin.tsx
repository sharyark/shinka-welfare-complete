import { router } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api';
import { useAuth } from '@/auth/AuthContext';
import { errorMessage } from '@/auth/errors';
import { loginFlow } from '@/auth/loginFlow';
import { useLang } from '@/i18n';
import { Button, ErrorText, Input, Screen, Title } from '@/ui';

/** Step 3: choose a PIN, then log in with it straight away. */
export default function SetPinScreen() {
  const { t, lang } = useLang();
  const { loginWithPin } = useAuth();
  const [pin, setPin] = useState('');
  const [repeat, setRepeat] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    if (pin !== repeat) return setError(t('pinMismatch'));
    setBusy(true);
    setError('');
    try {
      await api.setPin(loginFlow.pinToken, pin);
      loginFlow.pinToken = '';
      await loginWithPin(loginFlow.phone, pin);
      router.replace('/');
    } catch (exc) {
      setError(errorMessage(exc, lang));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t('pinSetTitle')}</Title>
      <Input value={pin} onChangeText={setPin} keyboardType="number-pad" maxLength={4} secureTextEntry autoFocus />
      <Title>{t('pinRepeat')}</Title>
      <Input value={repeat} onChangeText={setRepeat} keyboardType="number-pad" maxLength={4} secureTextEntry />
      <ErrorText>{error}</ErrorText>
      <Button label={t('savePin')} onPress={save} busy={busy} disabled={pin.length !== 4 || repeat.length !== 4} />
    </Screen>
  );
}
