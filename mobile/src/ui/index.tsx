/**
 * Shared building blocks. Big buttons and text (architecture principle 7: many
 * users are elderly or new to smartphones). Text is right-aligned in Urdu.
 */
import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text as RNText,
  TextInput,
  View,
  type TextInputProps,
  type TextProps,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useLang } from '../i18n';

export const colors = {
  primary: '#047857',
  primaryLight: '#d1fae5',
  text: '#111827',
  muted: '#6b7280',
  border: '#d1d5db',
  danger: '#b91c1c',
  warning: '#b45309',
  background: '#f9fafb',
  card: '#ffffff',
};

export function Text({ style, ...props }: TextProps) {
  const { isRTL } = useLang();
  return <RNText {...props} style={[styles.text, isRTL && styles.rtl, style]} />;
}

export function Title({ children }: { children: ReactNode }) {
  return <Text style={styles.title}>{children}</Text>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <Text style={styles.muted}>{children}</Text>;
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <Text style={styles.error}>{children}</Text>;
}

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  return (
    <SafeAreaView style={styles.screen} edges={['bottom', 'left', 'right']}>
      {scroll ? <ScrollView contentContainerStyle={styles.content}>{children}</ScrollView> : <View style={styles.content}>{children}</View>}
    </SafeAreaView>
  );
}

export function Button({
  label,
  onPress,
  kind = 'primary',
  busy = false,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  kind?: 'primary' | 'secondary' | 'danger';
  busy?: boolean;
  disabled?: boolean;
}) {
  const off = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={off}
      style={({ pressed }) => [styles.button, styles[kind], off && styles.disabled, pressed && styles.pressed]}
    >
      {busy ? (
        <ActivityIndicator color={kind === 'secondary' ? colors.primary : '#fff'} />
      ) : (
        <RNText style={[styles.buttonText, kind === 'secondary' && styles.secondaryText]}>{label}</RNText>
      )}
    </Pressable>
  );
}

export function Input(props: TextInputProps) {
  const { isRTL } = useLang();
  return <TextInput placeholderTextColor={colors.muted} {...props} style={[styles.input, isRTL && styles.rtl, props.style]} />;
}

export function Card({ children }: { children: ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

export function Loading() {
  return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color={colors.primary} />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, gap: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  text: { fontSize: 18, color: colors.text },
  rtl: { textAlign: 'right', writingDirection: 'rtl' },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 4 },
  muted: { fontSize: 16, color: colors.muted },
  error: { fontSize: 16, color: colors.danger },
  button: { minHeight: 56, borderRadius: 12, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  primary: { backgroundColor: colors.primary },
  secondary: { backgroundColor: colors.primaryLight },
  danger: { backgroundColor: colors.danger },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.8 },
  buttonText: { color: '#fff', fontSize: 20, fontWeight: '600' },
  secondaryText: { color: colors.primary },
  input: {
    minHeight: 56,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    fontSize: 20,
    backgroundColor: colors.card,
    color: colors.text,
  },
  card: { backgroundColor: colors.card, borderRadius: 12, padding: 16, gap: 6, borderWidth: 1, borderColor: '#e5e7eb' },
});

/** "1500.00" → "Rs 1,500". */
export function rupees(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '';
  return `Rs ${Math.round(Number(value)).toLocaleString('en-PK')}`;
}
