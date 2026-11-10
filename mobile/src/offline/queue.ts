/**
 * Deliveries recorded without signal (architecture 15).
 *
 * Each delivery gets its client_uuid on the phone BEFORE it is first sent. If the
 * connection fails, it waits here with the same id. When it is sent later, the
 * server either saves it, or recognises the id and answers with the first
 * result, so a delivery can never be counted twice.
 *
 * If the server refuses one (e.g. someone else already handed it out), it is
 * kept with the reason, so the volunteer can see it, and not retried.
 */
import { ApiError } from '../api/client';
import type { DeliverBody } from '../api/types';

export type PendingDelivery = DeliverBody & {
  label: string; // shown to the volunteer, e.g. "SHK-0001 · Ramadan Food Package"
  delivered_at: string;
  error?: string; // set when the server refused it
};

type Store = { getItem(key: string): Promise<string | null>; setItem(key: string, value: string): Promise<void> };
type Send = (delivery: DeliverBody) => Promise<unknown>;

const KEY = 'shinka.pending_deliveries';

export function createQueue(store: Store, send: Send) {
  async function list(): Promise<PendingDelivery[]> {
    const raw = await store.getItem(KEY);
    return raw ? (JSON.parse(raw) as PendingDelivery[]) : [];
  }

  async function save(items: PendingDelivery[]) {
    await store.setItem(KEY, JSON.stringify(items));
  }

  async function add(item: PendingDelivery) {
    const items = await list();
    if (!items.some((i) => i.client_uuid === item.client_uuid)) items.push(item);
    await save(items);
  }

  async function remove(clientUuid: string) {
    await save((await list()).filter((i) => i.client_uuid !== clientUuid));
  }

  /** Send everything waiting. Stops at the first network failure (still offline). */
  async function sync(): Promise<{ sent: number; failed: number; waiting: number }> {
    const items = await list();
    const kept: PendingDelivery[] = [];
    let sent = 0;
    let offline = false;
    for (const item of items) {
      if (offline || item.error) {
        kept.push(item);
        continue;
      }
      const { label, error, ...body } = item;
      try {
        await send(body);
        sent += 1;
      } catch (exc) {
        if (exc instanceof ApiError && !exc.isNetwork) {
          kept.push({ ...item, error: exc.message });
        } else {
          offline = true;
          kept.push(item);
        }
      }
    }
    await save(kept);
    return { sent, failed: kept.filter((i) => i.error).length, waiting: kept.filter((i) => !i.error).length };
  }

  return { list, add, remove, sync };
}
