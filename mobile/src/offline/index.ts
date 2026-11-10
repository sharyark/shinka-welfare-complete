import AsyncStorage from '@react-native-async-storage/async-storage';

import { api } from '../api';
import { createQueue } from './queue';

/** The phone's queue of deliveries waiting to be sent. */
export const pendingDeliveries = createQueue(AsyncStorage, (delivery) => api.deliver(delivery));
