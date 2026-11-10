# Shinka Welfare — mobile app

One app for families and volunteers (Expo SDK 58, React Native, TypeScript, Expo Router). Urdu first, English optional.

| Who | What they can do |
|---|---|
| **Family** (Beneficiary account) | See help received and upcoming, show the QR card, apply for help, see their household |
| **Volunteer** (also Coordinator, President) | Scan a family's QR card (or type the code), choose who collects, mark benefits as given. Works without signal: deliveries wait on the phone and are sent later |
| Finance Secretary, Auditor | Told to use the admin panel |

## Run it

Needs Node 22 (`nvm use` reads `.nvmrc`) and the backend running (see the root README).

```bash
cd mobile
nvm use
npm install
cp .env.example .env        # set EXPO_PUBLIC_API_URL to where the phone can reach the backend
npx expo start              # press w for web, or scan the QR code with a development build
```

Scanning QR cards and secure token storage need a phone. On web (development only), tokens are kept in browser storage and the camera may not work.

**Logging in for the first time:** the account must exist (created by the society in the admin panel, with the *Beneficiary* or *Volunteer* role). Enter the phone, then the 6-digit code; in development the code is printed in the backend's log. A volunteer's phone must then be approved under **Users & roles → Devices**.

## Checks

```bash
npm run typecheck           # TypeScript
npm test                    # unit tests (__tests__/*-test.ts)
npx expo-doctor             # dependency health
```

## 🎓 Tour

1. **`src/api/client.ts`**: every request goes through one function that adds the token, refreshes it once when it expires, and turns failures into `ApiError` with the backend's `code`. It gets `fetch` passed in, so tests use a fake one.
2. **`src/auth/`**: tokens in `expo-secure-store` (encrypted on the phone); a random device id made once per install; `AuthContext` decides which home screen fits the user's roles.
3. **`src/offline/queue.ts`**: the `client_uuid` is made *before* the first try and kept on retry, so the server can recognise a repeated delivery (see `apps/distribution/services.py`).
4. **`src/app/`**: each file is a screen (Expo Router). `family/` and `volunteer/` share a layout that sends logged-out users back to login.
5. **`src/i18n/strings.ts`**: every text in Urdu and English. The Urdu wording should be checked by the committee.
