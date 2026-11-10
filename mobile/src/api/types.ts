/** Shapes of the backend's JSON (see the API docs at /api/docs/). Money comes as strings like "1500.00". */

export type Tokens = { access: string; refresh: string };

export type Me = {
  id: string;
  phone: string;
  name: string;
  language: 'ur' | 'en';
  society: { id: string; name: string } | null;
  roles: string[];
};

export type FamilyMember = {
  id: string;
  full_name: string;
  relation: string;
  gender: 'male' | 'female';
  age: number | null;
  cnic_masked: string;
};

export type MyHousehold = {
  id: string;
  code: string;
  status: string;
  mohalla: string;
  address: string;
  phone: string;
  members: FamilyMember[];
};

export type ReceivedItem = { program: string; count: number; quantity: string; unit: string; amount_pkr: string | null };

export type UpcomingItem = {
  program: string;
  program_ur: string;
  person: string | null;
  due_date: string;
  quantity: string;
  unit: string;
  amount_pkr: string | null;
  status: 'planned' | 'confirmed' | 'ready';
  label: string;
  label_ur: string;
  collection_point: string;
};

export type Summary = {
  household_code: string;
  year: number;
  received: { total_cash_pkr: string; items: ReceivedItem[] };
  upcoming: UpcomingItem[];
};

export type QRCard = { household_code: string; qr_token: string };

export type LookupEntitlement = {
  id: string;
  program: string;
  person: string | null;
  cycle: string | null;
  due_date: string;
  quantity: string;
  unit: string;
  amount: string | null;
  status: string;
  can_deliver: boolean;
};

export type Lookup = {
  household_id: string;
  household_code: string;
  mohalla: string;
  members: { id: string; full_name: string; relation: string }[];
  entitlements: LookupEntitlement[];
};

export type Program = {
  id: string;
  code: string;
  name: string;
  name_ur: string;
  requires_application: boolean;
  default_amount: string | null;
};

export type Application = {
  id: string;
  household: string;
  program: string;
  program_name: string;
  description: string;
  amount_requested: string | null;
  needed_by: string | null;
  status: string;
  status_label: string;
  approved_amount: string | null;
  due_date: string | null;
  decision_note: string;
  created_at: string;
};

export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type DeliverBody = {
  entitlement: string;
  client_uuid: string;
  received_by?: string | null;
  method: 'qr' | 'manual';
  delivered_at?: string;
};
