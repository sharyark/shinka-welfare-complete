import { ApiError } from '../src/api/client';
import { createQueue, type PendingDelivery } from '../src/offline/queue';

function memoryStore() {
  const data: Record<string, string> = {};
  return { getItem: async (k: string) => data[k] ?? null, setItem: async (k: string, v: string) => void (data[k] = v) };
}

const item = (n: number): PendingDelivery => ({
  entitlement: `e${n}`,
  client_uuid: `u${n}`,
  method: 'qr',
  delivered_at: '2027-03-01T10:00:00Z',
  label: `SHK-000${n}`,
});

test('a delivery is only queued once per client_uuid', async () => {
  const queue = createQueue(memoryStore(), jest.fn());
  await queue.add(item(1));
  await queue.add(item(1));
  expect(await queue.list()).toHaveLength(1);
});

test('sync sends everything and empties the queue, without the label', async () => {
  const send = jest.fn(async () => ({}));
  const queue = createQueue(memoryStore(), send);
  await queue.add(item(1));
  await queue.add(item(2));
  expect(await queue.sync()).toEqual({ sent: 2, failed: 0, waiting: 0 });
  expect(await queue.list()).toEqual([]);
  expect(send).toHaveBeenCalledWith({
    entitlement: 'e1',
    client_uuid: 'u1',
    method: 'qr',
    delivered_at: '2027-03-01T10:00:00Z',
  });
});

test('still offline: stops and keeps everything for later', async () => {
  const send = jest.fn(async () => {
    throw new ApiError(0, 'network', 'offline');
  });
  const queue = createQueue(memoryStore(), send);
  await queue.add(item(1));
  await queue.add(item(2));
  expect(await queue.sync()).toEqual({ sent: 0, failed: 0, waiting: 2 });
  expect(send).toHaveBeenCalledTimes(1); // no point trying the rest
});

test('refused by the server: kept with the reason and not retried', async () => {
  const send = jest
    .fn()
    .mockRejectedValueOnce(new ApiError(409, 'already_delivered', 'Already collected.'))
    .mockResolvedValueOnce({});
  const queue = createQueue(memoryStore(), send);
  await queue.add(item(1));
  await queue.add(item(2));
  expect(await queue.sync()).toEqual({ sent: 1, failed: 1, waiting: 0 });
  const [refused] = await queue.list();
  expect(refused.error).toBe('Already collected.');
  await queue.sync();
  expect(send).toHaveBeenCalledTimes(2); // the refused one is not sent again
  await queue.remove('u1');
  expect(await queue.list()).toEqual([]);
});
