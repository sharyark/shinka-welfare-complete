import { View } from 'react-native';
import QRCode from 'react-native-qrcode-svg';

import { api } from '@/api';
import { errorMessage } from '@/auth/errors';
import { useLang } from '@/i18n';
import { ErrorText, Loading, Muted, Screen, Title } from '@/ui';
import { useLoad } from '@/ui/useLoad';

/** The family's QR card. Volunteers scan it on distribution day. */
export default function QRScreen() {
  const { t, lang } = useLang();
  const { data, error, loading } = useLoad(() => api.myQR());
  if (loading && !data) return <Loading />;
  return (
    <Screen>
      <ErrorText>{error ? errorMessage(error, lang) : ''}</ErrorText>
      {data && (
        <>
          <Title>{data.household_code}</Title>
          <View style={{ alignItems: 'center', padding: 24, backgroundColor: '#fff', borderRadius: 12 }}>
            <QRCode value={data.qr_token} size={260} />
          </View>
          <Muted>{t('cardHint')}</Muted>
        </>
      )}
    </Screen>
  );
}
