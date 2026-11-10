import { router } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api';
import { errorMessage } from '@/auth/errors';
import { useLang } from '@/i18n';
import { Button, ErrorText, Input, Loading, Screen, Title } from '@/ui';
import { useLoad } from '@/ui/useLoad';

/** A new application. Only programs that take applications are offered. */
export default function ApplyScreen() {
  const { t, lang } = useLang();
  const { data, loading } = useLoad(async () => {
    const [household, programs] = await Promise.all([api.myHousehold(), api.programs()]);
    return { household, programs: programs.filter((p) => p.requires_application) };
  });
  const [program, setProgram] = useState('');
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [neededBy, setNeededBy] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit() {
    if (!data) return;
    setBusy(true);
    setError('');
    try {
      await api.apply({
        household: data.household.id,
        program,
        description,
        ...(amount ? { amount_requested: amount } : {}),
        ...(neededBy ? { needed_by: neededBy } : {}),
      });
      router.back();
    } catch (exc) {
      setError(errorMessage(exc, lang));
    } finally {
      setBusy(false);
    }
  }

  if (loading || !data) return <Loading />;
  return (
    <Screen>
      <Title>{t('program')}</Title>
      {data.programs.map((p) => (
        <Button
          key={p.id}
          label={lang === 'ur' && p.name_ur ? p.name_ur : p.name}
          kind={program === p.id ? 'primary' : 'secondary'}
          onPress={() => setProgram(p.id)}
        />
      ))}
      <Title>{t('whatNeeded')}</Title>
      <Input value={description} onChangeText={setDescription} multiline style={{ minHeight: 100 }} />
      <Title>{t('amount')}</Title>
      <Input value={amount} onChangeText={setAmount} keyboardType="number-pad" />
      <Title>{t('neededBy')}</Title>
      <Input value={neededBy} onChangeText={setNeededBy} placeholder="2027-02-12" />
      <ErrorText>{error}</ErrorText>
      <Button label={t('submit')} onPress={submit} busy={busy} disabled={!program || !description.trim()} />
    </Screen>
  );
}
