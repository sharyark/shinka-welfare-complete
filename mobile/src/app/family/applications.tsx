import { router } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api';
import { errorMessage } from '@/auth/errors';
import { useLang } from '@/i18n';
import { Button, Card, ErrorText, Loading, Muted, Screen, Text, Title, rupees } from '@/ui';
import { useLoad } from '@/ui/useLoad';

const OPEN = ['submitted', 'under_review'];

/** The family's applications for help (marriage, water bore, burial…). */
export default function ApplicationsScreen() {
  const { t, lang } = useLang();
  const { data, error, loading, reload } = useLoad(() => api.applications());
  const [actionError, setActionError] = useState('');

  async function withdraw(id: string) {
    try {
      await api.withdraw(id);
      reload();
    } catch (exc) {
      setActionError(errorMessage(exc, lang));
    }
  }

  if (loading && !data) return <Loading />;
  return (
    <Screen>
      <Button label={t('newApplication')} onPress={() => router.push('/family/apply')} />
      <ErrorText>{error ? errorMessage(error, lang) : actionError}</ErrorText>
      <Title>{t('myApplications')}</Title>
      {data?.results.length === 0 && <Muted>{t('nothingYet')}</Muted>}
      {data?.results.map((app) => (
        <Card key={app.id}>
          <Text style={{ fontWeight: '700' }}>{app.program_name}</Text>
          <Text>{app.status_label}</Text>
          {app.approved_amount && <Text>{`${rupees(app.approved_amount)} · ${app.due_date ?? ''}`}</Text>}
          {app.decision_note ? <Muted>{app.decision_note}</Muted> : null}
          {OPEN.includes(app.status) && <Button label={t('withdraw')} kind="secondary" onPress={() => withdraw(app.id)} />}
        </Card>
      ))}
    </Screen>
  );
}
