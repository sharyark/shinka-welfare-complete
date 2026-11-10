import { router } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api';
import { errorMessage } from '@/auth/errors';
import { loginFlow } from '@/auth/loginFlow';
import { useLang } from '@/i18n';
import { Button, ErrorText, Input, Muted, Screen, Title } from '@/ui';

/** Step 2: the 6-digit SMS code → permission to set a PIN. */
export default function CodeScreen() {
  const { t, lang } = useLang();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function verify() {
    setBusy(true);
    setError('');
    try {
      loginFlow.pinToken = (await api.verifyCode(loginFlow.phone, code)).pin_token;
      router.replace('/login/set-pin');
    } catch (exc) {
      setError(errorMessage(exc, lang));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t('codeTitle')}</Title>
      <Muted>{loginFlow.phone}</Muted>
      <Input value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={6} autoFocus textContentType="oneTimeCode" />
      <ErrorText>{error}</ErrorText>
      <Button label={t('verify')} onPress={verify} busy={busy} disabled={code.length !== 6} />
    </Screen>
  );
}
