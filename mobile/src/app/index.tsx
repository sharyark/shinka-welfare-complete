import { Redirect } from 'expo-router';

import { homeFor, useAuth } from '@/auth/AuthContext';
import { Loading } from '@/ui';

/** Sends people to the right place: login, the family screens or the volunteer screens. */
export default function Start() {
  const { state, savedPhone } = useAuth();
  if (state.status === 'loading') return <Loading />;
  if (state.status === 'loggedOut') return <Redirect href={savedPhone ? '/login/pin' : '/login'} />;
  return <Redirect href={homeFor(state.me)} />;
}
