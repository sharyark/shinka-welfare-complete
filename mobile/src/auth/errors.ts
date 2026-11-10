import { ApiError } from '../api/client';
import type { Lang } from '../i18n/strings';

/** Friendly Urdu/English text for the backend's error codes. Anything else shows the server's message. */
const MESSAGES: Record<string, Record<Lang, string>> = {
  network: { ur: 'انٹرنیٹ نہیں ہے۔ دوبارہ کوشش کریں۔', en: 'No internet connection. Try again.' },
  bad_code: { ur: 'کوڈ غلط ہے یا اس کا وقت ختم ہو گیا ہے۔ نیا کوڈ منگوائیں۔', en: 'The code is wrong or expired. Ask for a new one.' },
  bad_pin: { ur: 'نمبر یا PIN غلط ہے۔', en: 'Wrong phone number or PIN.' },
  pin_locked: { ur: 'بہت زیادہ غلط PIN۔ نیا SMS کوڈ منگوائیں۔', en: 'Too many wrong PINs. Get a new SMS code.' },
  weak_pin: { ur: 'یہ PIN بہت آسان ہے۔ کوئی اور چنیں۔', en: 'That PIN is too easy. Choose another.' },
  bad_token: { ur: 'وقت ختم ہو گیا۔ نیا کوڈ منگوائیں۔', en: 'This step expired. Get a new code.' },
  device_pending: {
    ur: 'یہ فون ابھی منظور نہیں ہوا۔ سوسائٹی کے دفتر سے منظوری لیں۔',
    en: 'This phone must be approved by the society office first.',
  },
  device_blocked: { ur: 'یہ فون بلاک ہے۔ دفتر سے رابطہ کریں۔', en: 'This phone is blocked. Contact the office.' },
  already_delivered: { ur: 'یہ پہلے ہی وصول ہو چکا ہے۔', en: 'Already collected.' },
  not_ready: { ur: 'ابھی وصولی کے لیے تیار نہیں۔', en: 'Not ready to collect yet.' },
  conflict_of_interest: {
    ur: 'آپ اپنے خاندان کو امداد نہیں دے سکتے۔ کسی اور رضاکار سے کہیں۔',
    en: "You can't hand out help to your own family. Ask another volunteer.",
  },
  already_open: { ur: 'اس کے لیے درخواست پہلے سے موجود ہے۔', en: 'There is already an open application for this.' },
};

export function errorMessage(error: unknown, lang: Lang): string {
  if (error instanceof ApiError) return MESSAGES[error.code]?.[lang] ?? error.message;
  return lang === 'ur' ? 'کچھ غلط ہو گیا۔' : 'Something went wrong.';
}
