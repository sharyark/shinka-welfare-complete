import { Stack } from 'expo-router';
import { Pressable, Text } from 'react-native';

import { useLang } from '@/i18n';

export default function LoginLayout() {
  const { t, toggle } = useLang();
  return (
    <Stack
      screenOptions={{
        title: t('appName'),
        headerStyle: { backgroundColor: '#047857' },
        headerTintColor: '#fff',
        headerRight: () => (
          <Pressable onPress={toggle} accessibilityRole="button" hitSlop={12}>
            <Text style={{ color: '#fff', fontSize: 16 }}>{t('language')}</Text>
          </Pressable>
        ),
      }}
    />
  );
}
