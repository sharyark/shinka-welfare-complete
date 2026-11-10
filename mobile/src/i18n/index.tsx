/**
 * Language choice (Urdu by default), remembered on the phone.
 * Urdu text is aligned right-to-left by the Text component in ui/.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

import { strings, type Lang, type StringKey } from './strings';

const KEY = 'shinka.language';

type Ctx = { lang: Lang; t: (key: StringKey) => string; toggle: () => void; isRTL: boolean };
const LanguageContext = createContext<Ctx>({ lang: 'ur', t: (k) => strings[k].ur, toggle: () => {}, isRTL: true });

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>('ur');

  useEffect(() => {
    AsyncStorage.getItem(KEY).then((saved) => saved === 'en' && setLang('en'));
  }, []);

  const toggle = useCallback(() => {
    setLang((current) => {
      const next = current === 'ur' ? 'en' : 'ur';
      AsyncStorage.setItem(KEY, next);
      return next;
    });
  }, []);

  const t = useCallback((key: StringKey) => strings[key][lang], [lang]);
  return <LanguageContext.Provider value={{ lang, t, toggle, isRTL: lang === 'ur' }}>{children}</LanguageContext.Provider>;
}

export const useLang = () => useContext(LanguageContext);
