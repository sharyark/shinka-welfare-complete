/**
 * Small key-value storage for login tokens and the device id.
 *
 * On phones we use expo-secure-store (Android Keystore / iOS Keychain), so tokens
 * are encrypted at rest. SecureStore doesn't exist in a web browser, so web
 * (used only for development) falls back to AsyncStorage.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const useSecure = Platform.OS !== 'web';

export const storage = {
  getItem: (key: string) => (useSecure ? SecureStore.getItemAsync(key) : AsyncStorage.getItem(key)),
  setItem: (key: string, value: string) =>
    useSecure ? SecureStore.setItemAsync(key, value) : AsyncStorage.setItem(key, value),
  removeItem: (key: string) => (useSecure ? SecureStore.deleteItemAsync(key) : AsyncStorage.removeItem(key)),
};

const DEVICE_KEY = 'shinka.device_id';

/** A random id made once per installation; the office approves or blocks it. */
export async function getDeviceId(): Promise<string> {
  const existing = await storage.getItem(DEVICE_KEY);
  if (existing) return existing;
  const id = Crypto.randomUUID();
  await storage.setItem(DEVICE_KEY, id);
  return id;
}
