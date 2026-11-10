import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { useAuth } from '@/auth/AuthContext';
import { useLang } from '@/i18n';
import { pendingDeliveries } from '@/offline';
import { Button, Input, Muted, Screen, Title } from '@/ui';

/** Volunteer home: scan a card or type a code; see deliveries waiting to be sent (architecture 11.2). */
export default function VolunteerHome() {
  const { t } = useLang();
  const { state } = useAuth();
  const [code, setCode] = useState('');
  const [waiting, setWaiting] = useState(0);

  useFocusEffect(
    useCallback(() => {
      pendingDeliveries.sync().then((r) => setWaiting(r.waiting + r.failed)); // send anything left over
    }, []),
  );

  return (
    <Screen>
      {state.status === 'loggedIn' && <Muted>{state.me.name}</Muted>}
      <Button label={t('scanCard')} onPress={() => router.push('/volunteer/scan')} />
      <Title>{t('typeCode')}</Title>
      <Input value={code} onChangeText={setCode} autoCapitalize="characters" placeholder="SHK-0001" />
      <Button
        label={t('find')}
        kind="secondary"
        disabled={!code.trim()}
        onPress={() => router.push({ pathname: '/volunteer/household', params: { q: code.trim(), method: 'manual' } })}
      />
      {waiting > 0 && <Button label={`${t('pending')}: ${waiting}`} kind="secondary" onPress={() => router.push('/volunteer/queue')} />}
    </Screen>
  );
}
