/**
 * Every text on screen, in Urdu and English. Urdu is the default (architecture principle 7).
 * The Urdu wording should be checked by the committee.
 */
export const strings = {
  appName: { ur: 'شنکہ ویلفیئر', en: 'Shinka Welfare' },
  // Login
  phoneTitle: { ur: 'اپنا موبائل نمبر لکھیں', en: 'Enter your mobile number' },
  phoneHint: { ur: 'مثال: 0300-1234567', en: 'e.g. 0300-1234567' },
  sendCode: { ur: 'کوڈ بھیجیں', en: 'Send code' },
  haveCode: { ur: 'میرا PIN پہلے سے ہے', en: 'I already have a PIN' },
  codeTitle: { ur: 'SMS میں آیا ہوا 6 ہندسوں کا کوڈ لکھیں', en: 'Enter the 6-digit code from the SMS' },
  codeSent: { ur: 'اگر یہ نمبر رجسٹرڈ ہے تو کوڈ بھیج دیا گیا ہے۔', en: 'If this number is registered, a code has been sent.' },
  verify: { ur: 'تصدیق کریں', en: 'Verify' },
  pinSetTitle: { ur: 'نیا 4 ہندسوں کا PIN بنائیں', en: 'Choose a new 4-digit PIN' },
  pinRepeat: { ur: 'PIN دوبارہ لکھیں', en: 'Repeat the PIN' },
  pinMismatch: { ur: 'دونوں PIN ایک جیسے نہیں ہیں۔', en: 'The two PINs are different.' },
  savePin: { ur: 'PIN محفوظ کریں', en: 'Save PIN' },
  pinLoginTitle: { ur: 'اپنا PIN لکھیں', en: 'Enter your PIN' },
  login: { ur: 'داخل ہوں', en: 'Log in' },
  forgotPin: { ur: 'PIN بھول گئے؟ نیا کوڈ منگوائیں', en: 'Forgot PIN? Get a new code' },
  logout: { ur: 'لاگ آؤٹ', en: 'Log out' },
  language: { ur: 'English', en: 'اردو' },
  // Family
  received: { ur: 'ملنے والی امداد', en: 'Help received' },
  upcoming: { ur: 'آنے والی امداد', en: 'Upcoming help' },
  nothingYet: { ur: 'ابھی کچھ نہیں', en: 'Nothing yet' },
  cashTotal: { ur: 'کل نقد رقم', en: 'Total cash' },
  myCard: { ur: 'میرا QR کارڈ', en: 'My QR card' },
  cardHint: { ur: 'امداد لیتے وقت یہ کارڈ رضاکار کو دکھائیں۔', en: 'Show this card to the volunteer when collecting help.' },
  myApplications: { ur: 'میری درخواستیں', en: 'My applications' },
  newApplication: { ur: 'نئی درخواست', en: 'New application' },
  program: { ur: 'پروگرام', en: 'Program' },
  whatNeeded: { ur: 'کیا ضرورت ہے اور کیوں؟', en: 'What is needed and why?' },
  amount: { ur: 'رقم (روپے)', en: 'Amount (Rs)' },
  neededBy: { ur: 'کب تک (YYYY-MM-DD)', en: 'Needed by (YYYY-MM-DD)' },
  submit: { ur: 'جمع کریں', en: 'Submit' },
  withdraw: { ur: 'واپس لیں', en: 'Withdraw' },
  family: { ur: 'میرا گھرانہ', en: 'My household' },
  // Volunteer
  scanCard: { ur: 'QR کارڈ اسکین کریں', en: 'Scan QR card' },
  typeCode: { ur: 'یا گھرانے کا کوڈ لکھیں (SHK-0001)', en: 'Or type the household code (SHK-0001)' },
  find: { ur: 'تلاش کریں', en: 'Find' },
  cameraNeeded: { ur: 'کارڈ اسکین کرنے کے لیے کیمرے کی اجازت دیں۔', en: 'Allow the camera to scan cards.' },
  allowCamera: { ur: 'اجازت دیں', en: 'Allow camera' },
  whoCollects: { ur: 'کون وصول کر رہا ہے؟', en: 'Who is collecting?' },
  deliver: { ur: 'دے دیا', en: 'Mark as given' },
  delivered: { ur: 'دے دیا گیا ✔', en: 'Given ✔' },
  savedOffline: { ur: 'انٹرنیٹ نہیں: محفوظ کر لیا، بعد میں بھیج دیا جائے گا۔', en: 'No internet: saved, will be sent later.' },
  notReady: { ur: 'ابھی وصولی کے لیے تیار نہیں', en: 'Not ready to collect' },
  pending: { ur: 'بھیجنے کے لیے باقی', en: 'Waiting to send' },
  sendNow: { ur: 'ابھی بھیجیں', en: 'Send now' },
  refused: { ur: 'رد ہو گیا', en: 'Refused' },
  officeOnly: { ur: 'آپ کا کام ایڈمن پینل میں ہے۔', en: 'Your work is in the admin panel.' },
} as const;

export type StringKey = keyof typeof strings;
export type Lang = 'ur' | 'en';
