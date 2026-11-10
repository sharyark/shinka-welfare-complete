import { api } from '@/api';
import { errorMessage } from '@/auth/errors';
import { useLang } from '@/i18n';
import { Card, ErrorText, Loading, Muted, Screen, Text, Title } from '@/ui';
import { useLoad } from '@/ui/useLoad';

/** The family's registered members (CNIC shown masked). */
export default function HouseholdScreen() {
  const { t, lang } = useLang();
  const { data, error, loading } = useLoad(() => api.myHousehold());
  if (loading && !data) return <Loading />;
  return (
    <Screen>
      <ErrorText>{error ? errorMessage(error, lang) : ''}</ErrorText>
      {data && (
        <>
          <Title>{`${t('family')} · ${data.code}`}</Title>
          <Muted>{data.mohalla}</Muted>
          {data.members.map((m) => (
            <Card key={m.id}>
              <Text style={{ fontWeight: '700' }}>{m.full_name}</Text>
              <Muted>{[m.relation, m.age !== null ? `${m.age}` : '', m.cnic_masked].filter(Boolean).join(' · ')}</Muted>
            </Card>
          ))}
        </>
      )}
    </Screen>
  );
}
