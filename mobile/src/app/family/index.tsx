import { router } from 'expo-router';

import { api } from '@/api';
import { errorMessage } from '@/auth/errors';
import { useLang } from '@/i18n';
import { Button, Card, ErrorText, Loading, Muted, Screen, Text, Title, rupees } from '@/ui';
import { useLoad } from '@/ui/useLoad';

/** The family's dashboard: help received this year and help coming (architecture 11.1). */
export default function FamilyHome() {
  const { t, lang } = useLang();
  const { data, error, loading } = useLoad(() => api.mySummary());

  if (loading && !data) return <Loading />;
  return (
    <Screen>
      <ErrorText>{error ? errorMessage(error, lang) : ''}</ErrorText>
      {data && (
        <>
          <Muted>{`${data.household_code} · ${data.year}`}</Muted>
          <Title>{t('upcoming')}</Title>
          {data.upcoming.length === 0 && <Muted>{t('nothingYet')}</Muted>}
          {data.upcoming.map((item, i) => (
            <Card key={`${item.program}-${item.due_date}-${i}`}>
              <Text style={{ fontWeight: '700' }}>{lang === 'ur' && item.program_ur ? item.program_ur : item.program}</Text>
              {item.person && <Text>{item.person}</Text>}
              <Text>{`${item.due_date} · ${item.unit === 'cash' ? rupees(item.amount_pkr) : `${Number(item.quantity)} ${item.unit}`}`}</Text>
              <Muted>{lang === 'ur' ? item.label_ur : item.label}</Muted>
              {item.collection_point ? <Muted>{item.collection_point}</Muted> : null}
            </Card>
          ))}

          <Title>{t('received')}</Title>
          {data.received.items.length === 0 && <Muted>{t('nothingYet')}</Muted>}
          {data.received.items.map((item) => (
            <Card key={`${item.program}-${item.unit}`}>
              <Text style={{ fontWeight: '700' }}>{item.program}</Text>
              <Text>{item.unit === 'cash' ? rupees(item.amount_pkr) : `${Number(item.quantity)} ${item.unit} (×${item.count})`}</Text>
            </Card>
          ))}
          {Number(data.received.total_cash_pkr) > 0 && <Text>{`${t('cashTotal')}: ${rupees(data.received.total_cash_pkr)}`}</Text>}
        </>
      )}
      <Button label={t('myCard')} onPress={() => router.push('/family/qr')} />
      <Button label={t('myApplications')} kind="secondary" onPress={() => router.push('/family/applications')} />
      <Button label={t('family')} kind="secondary" onPress={() => router.push('/family/household')} />
    </Screen>
  );
}
