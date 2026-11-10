import { router } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api';
import { errorMessage } from '@/auth/errors';
import { loginFlow } from '@/auth/loginFlow';
import { useLang } from '@/i18n';
import { Button, ErrorText, Input, Muted, Screen, Title } from '@/ui';

/** Step 1: phone number → an SMS code is sent (if the number is registered). */
export default function PhoneScreen() {
  const { t, lang } = useLang();
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function send() {
    setBusy(true);
    setError('');
    try {
      await api.requestCode(phone);
      loginFlow.phone = phone;
      router.push('/login/code');
    } catch (exc) {
      setError(errorMessage(exc, lang));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t('phoneTitle')}</Title>
      <Input value={phone} onChangeText={setPhone} placeholder={t('phoneHint')} keyboardType="phone-pad" autoFocus />
      <ErrorText>{error}</ErrorText>
      <Button label={t('sendCode')} onPress={send} busy={busy} disabled={phone.replace(/\D/g, '').length < 10} />
      <Button label={t('haveCode')} kind="secondary" onPress={() => router.push('/login/pin')} />
      <Muted>{t('codeSent')}</Muted>
    </Screen>
  );
}
