import { router } from 'expo-router';
import { useState } from 'react';

import { useAuth } from '@/auth/AuthContext';
import { errorMessage } from '@/auth/errors';
import { useLang } from '@/i18n';
import { Button, ErrorText, Input, Screen, Title } from '@/ui';

/** Everyday login: phone (remembered) + PIN. */
export default function PinLoginScreen() {
  const { t, lang } = useLang();
  const { loginWithPin, savedPhone } = useAuth();
  const [phone, setPhone] = useState(savedPhone ?? '');
  const [pin, setPin] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function login() {
    setBusy(true);
    setError('');
    try {
      await loginWithPin(phone, pin);
      router.replace('/');
    } catch (exc) {
      setError(errorMessage(exc, lang));
      setPin('');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t('phoneTitle')}</Title>
      <Input value={phone} onChangeText={setPhone} placeholder={t('phoneHint')} keyboardType="phone-pad" />
      <Title>{t('pinLoginTitle')}</Title>
      <Input value={pin} onChangeText={setPin} keyboardType="number-pad" maxLength={4} secureTextEntry autoFocus />
      <ErrorText>{error}</ErrorText>
      <Button label={t('login')} onPress={login} busy={busy} disabled={pin.length !== 4} />
      <Button label={t('forgotPin')} kind="secondary" onPress={() => router.push('/login')} />
    </Screen>
  );
}
