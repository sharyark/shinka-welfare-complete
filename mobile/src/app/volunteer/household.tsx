import * as Crypto from 'expo-crypto';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { api } from '@/api';
import type { LookupEntitlement } from '@/api/types';
import { ApiError } from '@/api/client';
import { errorMessage } from '@/auth/errors';
import { useLang } from '@/i18n';
import { pendingDeliveries } from '@/offline';
import { Button, Card, ErrorText, Loading, Muted, Screen, Text, Title, colors, rupees } from '@/ui';
import { useLoad } from '@/ui/useLoad';

type Outcome = { kind: 'given' | 'saved' | 'error'; text: string };

/**
 * The family found from a card or code, and what it can collect now.
 * "Mark as given" records the delivery; without signal it is queued with the
 * same client_uuid and sent later, so it can't be counted twice.
 */
export default function HouseholdScreen() {
  const { q, method } = useLocalSearchParams<{ q: string; method?: 'qr' | 'manual' }>();
  const { t, lang } = useLang();
  const { data, error, loading } = useLoad(() => api.lookup(q));
  const [receiver, setReceiver] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});

  async function deliver(ent: LookupEntitlement) {
    const body = {
      entitlement: ent.id,
      client_uuid: Crypto.randomUUID(), // made once, before the first try
      received_by: receiver,
      method: method === 'manual' ? ('manual' as const) : ('qr' as const),
      delivered_at: new Date().toISOString(),
    };
    setBusy(ent.id);
    try {
      await api.deliver(body);
      setOutcomes((o) => ({ ...o, [ent.id]: { kind: 'given', text: t('delivered') } }));
    } catch (exc) {
      if (exc instanceof ApiError && exc.isNetwork) {
        await pendingDeliveries.add({ ...body, label: `${data?.household_code} · ${ent.program}` });
        setOutcomes((o) => ({ ...o, [ent.id]: { kind: 'saved', text: t('savedOffline') } }));
      } else {
        setOutcomes((o) => ({ ...o, [ent.id]: { kind: 'error', text: errorMessage(exc, lang) } }));
      }
    } finally {
      setBusy(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (error || !data) return <Screen><ErrorText>{errorMessage(error, lang)}</ErrorText></Screen>;

  return (
    <Screen>
      <Title>{data.household_code}</Title>
      <Muted>{data.mohalla}</Muted>

      <Text style={{ fontWeight: '700' }}>{t('whoCollects')}</Text>
      <View style={{ gap: 8 }}>
        {data.members.map((m) => (
          <Button key={m.id} label={m.full_name} kind={receiver === m.id ? 'primary' : 'secondary'} onPress={() => setReceiver(m.id)} />
        ))}
      </View>

      {data.entitlements.length === 0 && <Muted>{t('nothingYet')}</Muted>}
      {data.entitlements.map((ent) => {
        const outcome = outcomes[ent.id];
        const done = ent.status === 'delivered' || outcome?.kind === 'given' || outcome?.kind === 'saved';
        return (
          <Card key={ent.id}>
            <Text style={{ fontWeight: '700' }}>{ent.program}</Text>
            {ent.person && <Text>{ent.person}</Text>}
            <Text>{ent.unit === 'cash' ? rupees(ent.amount) : `${Number(ent.quantity)} ${ent.unit}`}</Text>
            {ent.status === 'delivered' && <Text style={{ color: colors.primary }}>{t('delivered')}</Text>}
            {!ent.can_deliver && ent.status !== 'delivered' && <Muted>{t('notReady')}</Muted>}
            {outcome && (
              <Text style={{ color: outcome.kind === 'error' ? colors.danger : outcome.kind === 'saved' ? colors.warning : colors.primary }}>
                {outcome.text}
              </Text>
            )}
            {ent.can_deliver && !done && (
              <Button label={t('deliver')} onPress={() => deliver(ent)} busy={busy === ent.id} disabled={busy !== null} />
            )}
          </Card>
        );
      })}
    </Screen>
  );
}
