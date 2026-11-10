import { CameraView, useCameraPermissions } from 'expo-camera';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useLang } from '@/i18n';
import { Button, Loading, Screen, Title } from '@/ui';

/**
 * Scans a family's QR card. The camera is only mounted while this screen is in
 * view: only one camera preview can be active at a time.
 */
export default function ScanScreen() {
  const { t } = useLang();
  const [permission, requestPermission] = useCameraPermissions();
  const [focused, setFocused] = useState(false);
  const handled = useRef(false);

  useFocusEffect(
    useCallback(() => {
      handled.current = false;
      setFocused(true);
      return () => setFocused(false);
    }, []),
  );

  if (!permission) return <Loading />;
  if (!permission.granted) {
    return (
      <Screen>
        <Title>{t('cameraNeeded')}</Title>
        <Button label={t('allowCamera')} onPress={requestPermission} />
      </Screen>
    );
  }

  return (
    <View style={styles.full}>
      {focused && (
        <CameraView
          style={styles.full}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
          onBarcodeScanned={({ data }) => {
            if (handled.current) return; // the scanner fires many times per second
            handled.current = true;
            router.replace({ pathname: '/volunteer/household', params: { q: data, method: 'qr' } });
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({ full: { flex: 1, backgroundColor: '#000' } });
