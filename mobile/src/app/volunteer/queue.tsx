import { useState } from 'react';

import { useLang } from '@/i18n';
import { pendingDeliveries } from '@/offline';
import type { PendingDelivery } from '@/offline/queue';
import { Button, Card, Loading, Muted, Screen, Text, colors } from '@/ui';
import { useLoad } from '@/ui/useLoad';

/** Deliveries recorded without signal, waiting to be sent; and any the server refused. */
export default function QueueScreen() {
  const { t } = useLang();
  const { data, loading, reload } = useLoad<PendingDelivery[]>(() => pendingDeliveries.list());
  const [busy, setBusy] = useState(false);

  async function sendNow() {
    setBusy(true);
    await pendingDeliveries.sync();
    setBusy(false);
    reload();
  }

  async function dismiss(id: string) {
    await pendingDeliveries.remove(id);
    reload();
  }

  if (loading && !data) return <Loading />;
  return (
    <Screen>
      <Button label={t('sendNow')} onPress={sendNow} busy={busy} disabled={!data?.length} />
      {data?.length === 0 && <Muted>{t('nothingYet')}</Muted>}
      {data?.map((item) => (
        <Card key={item.client_uuid}>
          <Text style={{ fontWeight: '700' }}>{item.label}</Text>
          <Muted>{new Date(item.delivered_at).toLocaleString()}</Muted>
          {item.error ? (
            <>
              <Text style={{ color: colors.danger }}>{`${t('refused')}: ${item.error}`}</Text>
              <Button label="OK" kind="secondary" onPress={() => dismiss(item.client_uuid)} />
            </>
          ) : (
            <Muted>{t('pending')}</Muted>
          )}
        </Card>
      ))}
    </Screen>
  );
}
