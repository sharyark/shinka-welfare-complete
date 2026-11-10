import { Redirect, Stack } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n';
import { Loading, colors } from '.';

/** Layout for the logged-in sections: guards the screens and puts language + logout in the header. */
export function SectionLayout() {
  const { state, logout } = useAuth();
  const { t, toggle } = useLang();
  if (state.status === 'loading') return <Loading />;
  if (state.status === 'loggedOut') return <Redirect href="/" />;
  return (
    <Stack
      screenOptions={{
        title: t('appName'),
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: '#fff',
        headerRight: () => (
          <View style={{ flexDirection: 'row', gap: 16 }}>
            <Pressable onPress={toggle} hitSlop={12} accessibilityRole="button">
              <Text style={{ color: '#fff', fontSize: 16 }}>{t('language')}</Text>
            </Pressable>
            <Pressable onPress={logout} hitSlop={12} accessibilityRole="button">
              <Text style={{ color: '#fff', fontSize: 16 }}>{t('logout')}</Text>
            </Pressable>
          </View>
        ),
      }}
    />
  );
}
